"""Security, multi-tenant isolation, IDOR, authorization, status guards, and tamper protection tests for Sub-module 11.11: Compliance & Regulatory Management.

Security aspects tested:
1. Multi-Tenant IDOR Isolation:
   - Detail view, edit view (GET & POST), delete view (POST), and workflow transitions (start, complete, renew, resolve, close)
     return HTTP 404 when an authenticated tenant user accesses another tenant's records (both A -> B and B -> A).
   - List views for Tenant A contain ONLY Tenant A records, and Tenant B list views contain ONLY Tenant B records.
   - Cross-tenant foreign-key injection via form POST is rejected by reject_foreign validation.
2. Authentication & Authorization:
   - All 25 view URLs redirect unauthenticated requests to /accounts/login/ (HTTP 302).
   - All delete views enforce @tenant_admin_required (HTTP 403 Forbidden for regular authenticated tenant users without admin privileges).
   - All destructive actions and workflow transitions enforce @require_POST (HTTP 405 Method Not Allowed on GET requests).
3. Mass Assignment Protection:
   - ModelForms ignore/reject manipulation of tenant, number, created_at, updated_at.
   - Form status manipulation cannot set terminal states (completed, resolved, closed).
4. Status & Business Invariant Guards:
   - Deleting a completed audit is blocked in view logic.
   - Editing a completed audit is blocked in view logic.
   - Deleting an incident with assessed fines is blocked in view logic.
   - Editing a settled incident with assessed fines is blocked in view logic.
   - Renewing a revoked or suspended permit is blocked in view logic.
   - Transitioning an audit or incident from invalid state is blocked with warning message.
   - Deleting a framework with linked audits is protected against cascade deletion.
5. Audit Trail Verification:
   - Every mutation (create, edit, delete, complete, renew, resolve, close) records an AuditLog entry
     with the correct acting user and tenant.
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.assets.forms.AssetCompliance import (
    AssetComplianceAuditForm,
    AssetComplianceFrameworkForm,
    AssetComplianceIncidentForm,
    AssetPermitLicenseForm,
)
from apps.assets.models import (
    AssetCategory,
    AssetComplianceAudit,
    AssetComplianceFramework,
    AssetComplianceIncident,
    AssetPermitLicense,
)
from apps.core.models import AuditLog, Party
from apps.scm.models import Asset

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (strictly prefixed with _compliance_*)
# ==============================================================================


def _compliance_get_flash_messages(response):
    """Extract list of flash message strings from response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _compliance_framework_payload(**overrides):
    """Build a valid payload for AssetComplianceFrameworkForm."""
    today = timezone.now().date()
    data = {
        "name": "OSHA 1910.119 Process Safety Management",
        "code": "OSHA-1910-SEC",
        "framework_type": "regulatory",
        "effective_date": today.isoformat(),
        "revision": "2024 Edition",
        "mandatory_audit_cycle_months": "12",
        "readiness_score": "95",
        "description": "Standard for managing hazards of highly hazardous chemicals.",
        "status": "active",
    }
    data.update(overrides)
    return data


def _compliance_audit_payload(framework, **overrides):
    """Build a valid payload for AssetComplianceAuditForm."""
    today = timezone.now().date()
    data = {
        "title": "Annual Machine Guarding Safety Audit",
        "framework": str(framework.pk),
        "audit_type": "internal",
        "audit_date": today.isoformat(),
        "scope_description": "Evaluation of interlocks and emergency stop systems.",
        "total_checkpoints": "30",
        "passed_checkpoints": "28",
        "minor_findings_count": "2",
        "major_findings_count": "0",
        "critical_findings_count": "0",
        "compliance_rating": "minor_deficiencies",
        "summary_findings": "All machine guards inspected and functional.",
        "status": "scheduled",
    }
    data.update(overrides)
    return data


def _compliance_permit_payload(asset, issuing_authority=None, **overrides):
    """Build a valid payload for AssetPermitLicenseForm."""
    today = timezone.now().date()
    data = {
        "permit_name": "Stationary Source Operating Permit",
        "permit_number": "EPA-AIR-2026-SEC",
        "permit_type": "environmental_emissions",
        "asset": str(asset.pk),
        "issue_date": (today - timezone.timedelta(days=30)).isoformat(),
        "effective_date": (today - timezone.timedelta(days=30)).isoformat(),
        "expiration_date": (today + timezone.timedelta(days=335)).isoformat(),
        "renewal_lead_days": "60",
        "renewal_fee": "1250.00",
        "operating_conditions": "Continuous monitoring of particulate exhaust.",
        "status": "active",
    }
    if issuing_authority is not None:
        data["issuing_authority"] = str(issuing_authority.pk)
    data.update(overrides)
    return data


def _compliance_incident_payload(**overrides):
    """Build a valid payload for AssetComplianceIncidentForm."""
    today = timezone.now().date()
    now_dt = timezone.now().strftime("%Y-%m-%dT%H:%M")
    data = {
        "title": "Temporary Coolant Sump Overflow",
        "incident_date": now_dt,
        "discovery_date": today.isoformat(),
        "incident_type": "unpermitted_discharge",
        "severity": "other_than_serious",
        "citation_reference": "EPA-NOV-2026-SEC",
        "fine_assessed": "2500.00",
        "fine_paid": "2500.00",
        "fine_payment_date": today.isoformat(),
        "root_cause": "mechanical_failure",
        "root_cause_analysis": "Float sensor failed to actuate valve closure.",
        "corrective_action_plan": "Replaced float sensor with redundant ultrasonic monitor.",
        "target_resolution_date": (today + timezone.timedelta(days=14)).isoformat(),
        "status": "under_investigation",
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. Multi-Tenant IDOR Isolation Tests
# ==============================================================================


def test_compliance_security_idor_detail_and_edit_blocked_tenant_b_to_a(
    client_b, compliance_framework_a, compliance_audit_a, permit_license_a, compliance_incident_a
):
    """Tenant B user accessing Tenant A records on detail and edit views receives HTTP 404."""
    routes = [
        ("assets:asset_compliance_framework_detail", compliance_framework_a.pk),
        ("assets:asset_compliance_framework_edit", compliance_framework_a.pk),
        ("assets:asset_compliance_audit_detail", compliance_audit_a.pk),
        ("assets:asset_compliance_audit_edit", compliance_audit_a.pk),
        ("assets:asset_permit_license_detail", permit_license_a.pk),
        ("assets:asset_permit_license_edit", permit_license_a.pk),
        ("assets:asset_compliance_incident_detail", compliance_incident_a.pk),
        ("assets:asset_compliance_incident_edit", compliance_incident_a.pk),
    ]
    for url_name, pk in routes:
        # GET request blocked with 404
        resp_get = client_b.get(reverse(url_name, kwargs={"pk": pk}))
        assert resp_get.status_code == 404, f"IDOR GET vulnerability on {url_name} for pk={pk}"

        # POST request to edit views also blocked with 404
        if "edit" in url_name:
            resp_post = client_b.post(reverse(url_name, kwargs={"pk": pk}), {"title": "IDOR Attack"})
            assert resp_post.status_code == 404, f"IDOR POST vulnerability on {url_name} for pk={pk}"


def test_compliance_security_idor_detail_and_edit_blocked_tenant_a_to_b(
    client_a, compliance_framework_b, compliance_audit_b, permit_license_b, compliance_incident_b
):
    """Tenant A user accessing Tenant B records on detail and edit views receives HTTP 404."""
    routes = [
        ("assets:asset_compliance_framework_detail", compliance_framework_b.pk),
        ("assets:asset_compliance_framework_edit", compliance_framework_b.pk),
        ("assets:asset_compliance_audit_detail", compliance_audit_b.pk),
        ("assets:asset_compliance_audit_edit", compliance_audit_b.pk),
        ("assets:asset_permit_license_detail", permit_license_b.pk),
        ("assets:asset_permit_license_edit", permit_license_b.pk),
        ("assets:asset_compliance_incident_detail", compliance_incident_b.pk),
        ("assets:asset_compliance_incident_edit", compliance_incident_b.pk),
    ]
    for url_name, pk in routes:
        resp_get = client_a.get(reverse(url_name, kwargs={"pk": pk}))
        assert resp_get.status_code == 404, f"IDOR GET vulnerability on {url_name} for pk={pk}"

        if "edit" in url_name:
            resp_post = client_a.post(reverse(url_name, kwargs={"pk": pk}), {"title": "IDOR Attack"})
            assert resp_post.status_code == 404, f"IDOR POST vulnerability on {url_name} for pk={pk}"


def test_compliance_security_idor_destructive_and_transitions_blocked_tenant_b_to_a(
    client_b, compliance_framework_a, compliance_audit_a, permit_license_a, compliance_incident_a
):
    """Tenant B user triggering destructive or transition actions on Tenant A records receives HTTP 404."""
    actions = [
        ("assets:asset_compliance_framework_delete", compliance_framework_a.pk),
        ("assets:asset_compliance_audit_delete", compliance_audit_a.pk),
        ("assets:asset_compliance_audit_start", compliance_audit_a.pk),
        ("assets:asset_compliance_audit_complete", compliance_audit_a.pk),
        ("assets:asset_permit_license_delete", permit_license_a.pk),
        ("assets:asset_permit_license_renew", permit_license_a.pk),
        ("assets:asset_compliance_incident_delete", compliance_incident_a.pk),
        ("assets:asset_compliance_incident_resolve", compliance_incident_a.pk),
        ("assets:asset_compliance_incident_close", compliance_incident_a.pk),
    ]
    for url_name, pk in actions:
        resp = client_b.post(reverse(url_name, kwargs={"pk": pk}))
        assert resp.status_code == 404, f"IDOR action vulnerability on {url_name} for pk={pk}"


def test_compliance_security_idor_destructive_and_transitions_blocked_tenant_a_to_b(
    client_a, compliance_framework_b, compliance_audit_b, permit_license_b, compliance_incident_b
):
    """Tenant A user triggering destructive or transition actions on Tenant B records receives HTTP 404."""
    actions = [
        ("assets:asset_compliance_framework_delete", compliance_framework_b.pk),
        ("assets:asset_compliance_audit_delete", compliance_audit_b.pk),
        ("assets:asset_compliance_audit_start", compliance_audit_b.pk),
        ("assets:asset_compliance_audit_complete", compliance_audit_b.pk),
        ("assets:asset_permit_license_delete", permit_license_b.pk),
        ("assets:asset_permit_license_renew", permit_license_b.pk),
        ("assets:asset_compliance_incident_delete", compliance_incident_b.pk),
        ("assets:asset_compliance_incident_resolve", compliance_incident_b.pk),
        ("assets:asset_compliance_incident_close", compliance_incident_b.pk),
    ]
    for url_name, pk in actions:
        resp = client_a.post(reverse(url_name, kwargs={"pk": pk}))
        assert resp.status_code == 404, f"IDOR action vulnerability on {url_name} for pk={pk}"


def test_compliance_security_list_views_tenant_isolation(
    client_a,
    client_b,
    compliance_framework_a,
    compliance_framework_b,
    compliance_audit_a,
    compliance_audit_b,
    permit_license_a,
    permit_license_b,
    compliance_incident_a,
    compliance_incident_b,
):
    """List views for Tenant A contain ONLY Tenant A records, and Tenant B list views contain ONLY Tenant B records."""
    # 1. Framework list isolation
    resp_frm_a = client_a.get(reverse("assets:asset_compliance_framework_list"))
    assert compliance_framework_a in resp_frm_a.context["frameworks"]
    assert compliance_framework_b not in resp_frm_a.context["frameworks"]

    resp_frm_b = client_b.get(reverse("assets:asset_compliance_framework_list"))
    assert compliance_framework_b in resp_frm_b.context["frameworks"]
    assert compliance_framework_a not in resp_frm_b.context["frameworks"]

    # 2. Audit list isolation
    resp_aud_a = client_a.get(reverse("assets:asset_compliance_audit_list"))
    assert compliance_audit_a in resp_aud_a.context["audits"]
    assert compliance_audit_b not in resp_aud_a.context["audits"]

    resp_aud_b = client_b.get(reverse("assets:asset_compliance_audit_list"))
    assert compliance_audit_b in resp_aud_b.context["audits"]
    assert compliance_audit_a not in resp_aud_b.context["audits"]

    # 3. Permit list isolation
    resp_per_a = client_a.get(reverse("assets:asset_permit_license_list"))
    assert permit_license_a in resp_per_a.context["permits"]
    assert permit_license_b not in resp_per_a.context["permits"]

    resp_per_b = client_b.get(reverse("assets:asset_permit_license_list"))
    assert permit_license_b in resp_per_b.context["permits"]
    assert permit_license_a not in resp_per_b.context["permits"]

    # 4. Incident list isolation
    resp_inc_a = client_a.get(reverse("assets:asset_compliance_incident_list"))
    assert compliance_incident_a in resp_inc_a.context["incidents"]
    assert compliance_incident_b not in resp_inc_a.context["incidents"]

    resp_inc_b = client_b.get(reverse("assets:asset_compliance_incident_list"))
    assert compliance_incident_b in resp_inc_b.context["incidents"]
    assert compliance_incident_a not in resp_inc_b.context["incidents"]


def test_compliance_security_cross_tenant_fk_injection_framework(
    client_a, tenant_a, category_b, vendor_party_b
):
    """Submitting foreign regulatory_agency or applicable_category from Tenant B is rejected."""
    create_url = reverse("assets:asset_compliance_framework_create")

    # Injected regulatory agency from Tenant B
    payload_agency = _compliance_framework_payload(
        code="INJ-AGENCY-01",
        regulatory_agency=str(vendor_party_b.pk),
    )
    resp_agency = client_a.post(create_url, payload_agency)
    assert resp_agency.status_code == 200
    assert not AssetComplianceFramework.objects.filter(tenant=tenant_a, code="INJ-AGENCY-01").exists()

    # Injected applicable category from Tenant B
    payload_cat = _compliance_framework_payload(
        code="INJ-CAT-01",
        applicable_category=str(category_b.pk),
    )
    resp_cat = client_a.post(create_url, payload_cat)
    assert resp_cat.status_code == 200
    assert not AssetComplianceFramework.objects.filter(tenant=tenant_a, code="INJ-CAT-01").exists()


def test_compliance_security_cross_tenant_fk_injection_audit(
    client_a, tenant_a, compliance_framework_a, compliance_framework_b, operational_asset_b, vendor_party_b, admin_b
):
    """Submitting foreign framework, asset, auditor_party, or lead_auditor_user from Tenant B is rejected."""
    create_url = reverse("assets:asset_compliance_audit_create")

    # 1. Foreign framework
    p1 = _compliance_audit_payload(compliance_framework_b, title="Audit Foreign Framework")
    r1 = client_a.post(create_url, p1)
    assert r1.status_code == 200
    assert not AssetComplianceAudit.objects.filter(tenant=tenant_a, title="Audit Foreign Framework").exists()

    # 2. Foreign asset
    p2 = _compliance_audit_payload(compliance_framework_a, title="Audit Foreign Asset", asset=str(operational_asset_b.pk))
    r2 = client_a.post(create_url, p2)
    assert r2.status_code == 200
    assert not AssetComplianceAudit.objects.filter(tenant=tenant_a, title="Audit Foreign Asset").exists()

    # 3. Foreign auditor party
    p3 = _compliance_audit_payload(compliance_framework_a, title="Audit Foreign Party", auditor_party=str(vendor_party_b.pk))
    r3 = client_a.post(create_url, p3)
    assert r3.status_code == 200
    assert not AssetComplianceAudit.objects.filter(tenant=tenant_a, title="Audit Foreign Party").exists()

    # 4. Foreign lead auditor user
    p4 = _compliance_audit_payload(compliance_framework_a, title="Audit Foreign User", lead_auditor_user=str(admin_b.pk))
    r4 = client_a.post(create_url, p4)
    assert r4.status_code == 200
    assert not AssetComplianceAudit.objects.filter(tenant=tenant_a, title="Audit Foreign User").exists()


def test_compliance_security_cross_tenant_fk_injection_permit(
    client_a, tenant_a, operational_asset_a, operational_asset_b, vendor_party_b
):
    """Submitting foreign asset or issuing_authority from Tenant B is rejected."""
    create_url = reverse("assets:asset_permit_license_create")

    # Foreign asset
    p1 = _compliance_permit_payload(operational_asset_b, permit_number="PERMIT-FOR-AST")
    r1 = client_a.post(create_url, p1)
    assert r1.status_code == 200
    assert not AssetPermitLicense.objects.filter(tenant=tenant_a, permit_number="PERMIT-FOR-AST").exists()

    # Foreign issuing authority
    p2 = _compliance_permit_payload(operational_asset_a, issuing_authority=vendor_party_b, permit_number="PERMIT-FOR-AUTH")
    r2 = client_a.post(create_url, p2)
    assert r2.status_code == 200
    assert not AssetPermitLicense.objects.filter(tenant=tenant_a, permit_number="PERMIT-FOR-AUTH").exists()


def test_compliance_security_cross_tenant_fk_injection_incident(
    client_a, tenant_a, operational_asset_a, operational_asset_b, permit_license_b, compliance_audit_b, vendor_party_b, admin_b
):
    """Submitting foreign asset, permit, audit, enforcement_agency, or assigned_investigator is rejected."""
    create_url = reverse("assets:asset_compliance_incident_create")

    # 1. Foreign asset
    p1 = _compliance_incident_payload(asset=str(operational_asset_b.pk), title="Incident Foreign Asset")
    r1 = client_a.post(create_url, p1)
    assert r1.status_code == 200
    assert not AssetComplianceIncident.objects.filter(tenant=tenant_a, title="Incident Foreign Asset").exists()

    # 2. Foreign permit
    p2 = _compliance_incident_payload(asset=str(operational_asset_a.pk), permit=str(permit_license_b.pk), title="Incident Foreign Permit")
    r2 = client_a.post(create_url, p2)
    assert r2.status_code == 200
    assert not AssetComplianceIncident.objects.filter(tenant=tenant_a, title="Incident Foreign Permit").exists()

    # 3. Foreign audit
    p3 = _compliance_incident_payload(asset=str(operational_asset_a.pk), audit=str(compliance_audit_b.pk), title="Incident Foreign Audit")
    r3 = client_a.post(create_url, p3)
    assert r3.status_code == 200
    assert not AssetComplianceIncident.objects.filter(tenant=tenant_a, title="Incident Foreign Audit").exists()

    # 4. Foreign enforcement agency
    p4 = _compliance_incident_payload(asset=str(operational_asset_a.pk), enforcement_agency=str(vendor_party_b.pk), title="Incident Foreign Agency")
    r4 = client_a.post(create_url, p4)
    assert r4.status_code == 200
    assert not AssetComplianceIncident.objects.filter(tenant=tenant_a, title="Incident Foreign Agency").exists()

    # 5. Foreign assigned investigator
    p5 = _compliance_incident_payload(asset=str(operational_asset_a.pk), assigned_investigator=str(admin_b.pk), title="Incident Foreign User")
    r5 = client_a.post(create_url, p5)
    assert r5.status_code == 200
    assert not AssetComplianceIncident.objects.filter(tenant=tenant_a, title="Incident Foreign User").exists()


# ==============================================================================
# 2. Authentication & Authorization Enforcement Tests
# ==============================================================================


def test_compliance_security_login_required_unauthenticated_redirect(
    client, compliance_framework_a, compliance_audit_a, permit_license_a, compliance_incident_a
):
    """All 25 compliance view URLs redirect unauthenticated requests to login."""
    urls = [
        # Frameworks (5)
        reverse("assets:asset_compliance_framework_list"),
        reverse("assets:asset_compliance_framework_create"),
        reverse("assets:asset_compliance_framework_detail", kwargs={"pk": compliance_framework_a.pk}),
        reverse("assets:asset_compliance_framework_edit", kwargs={"pk": compliance_framework_a.pk}),
        reverse("assets:asset_compliance_framework_delete", kwargs={"pk": compliance_framework_a.pk}),
        # Audits (7)
        reverse("assets:asset_compliance_audit_list"),
        reverse("assets:asset_compliance_audit_create"),
        reverse("assets:asset_compliance_audit_detail", kwargs={"pk": compliance_audit_a.pk}),
        reverse("assets:asset_compliance_audit_edit", kwargs={"pk": compliance_audit_a.pk}),
        reverse("assets:asset_compliance_audit_delete", kwargs={"pk": compliance_audit_a.pk}),
        reverse("assets:asset_compliance_audit_start", kwargs={"pk": compliance_audit_a.pk}),
        reverse("assets:asset_compliance_audit_complete", kwargs={"pk": compliance_audit_a.pk}),
        # Permits (6)
        reverse("assets:asset_permit_license_list"),
        reverse("assets:asset_permit_license_create"),
        reverse("assets:asset_permit_license_detail", kwargs={"pk": permit_license_a.pk}),
        reverse("assets:asset_permit_license_edit", kwargs={"pk": permit_license_a.pk}),
        reverse("assets:asset_permit_license_delete", kwargs={"pk": permit_license_a.pk}),
        reverse("assets:asset_permit_license_renew", kwargs={"pk": permit_license_a.pk}),
        # Incidents (7)
        reverse("assets:asset_compliance_incident_list"),
        reverse("assets:asset_compliance_incident_create"),
        reverse("assets:asset_compliance_incident_detail", kwargs={"pk": compliance_incident_a.pk}),
        reverse("assets:asset_compliance_incident_edit", kwargs={"pk": compliance_incident_a.pk}),
        reverse("assets:asset_compliance_incident_delete", kwargs={"pk": compliance_incident_a.pk}),
        reverse("assets:asset_compliance_incident_resolve", kwargs={"pk": compliance_incident_a.pk}),
        reverse("assets:asset_compliance_incident_close", kwargs={"pk": compliance_incident_a.pk}),
    ]
    assert len(urls) == 25
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 on unauthenticated GET for {url}"
        assert "/accounts/login" in resp.url or "login" in resp.url


def test_compliance_security_delete_views_require_tenant_admin(
    member_client, compliance_framework_a, compliance_audit_a, permit_license_a, compliance_incident_a
):
    """Delete endpoints return HTTP 403 Forbidden for authenticated non-admin members."""
    deletes = [
        reverse("assets:asset_compliance_framework_delete", kwargs={"pk": compliance_framework_a.pk}),
        reverse("assets:asset_compliance_audit_delete", kwargs={"pk": compliance_audit_a.pk}),
        reverse("assets:asset_permit_license_delete", kwargs={"pk": permit_license_a.pk}),
        reverse("assets:asset_compliance_incident_delete", kwargs={"pk": compliance_incident_a.pk}),
    ]
    for url in deletes:
        resp = member_client.post(url)
        assert resp.status_code == 403, f"Expected 403 on non-admin delete for {url}"

    # Confirm objects still exist in DB
    assert AssetComplianceFramework.objects.filter(pk=compliance_framework_a.pk).exists()
    assert AssetComplianceAudit.objects.filter(pk=compliance_audit_a.pk).exists()
    assert AssetPermitLicense.objects.filter(pk=permit_license_a.pk).exists()
    assert AssetComplianceIncident.objects.filter(pk=compliance_incident_a.pk).exists()


def test_compliance_security_destructive_and_transitions_require_post(
    client_a, compliance_framework_a, compliance_audit_a, permit_license_a, compliance_incident_a
):
    """GET requests on all 9 destructive and workflow transition endpoints return HTTP 405 Method Not Allowed."""
    post_only_urls = [
        reverse("assets:asset_compliance_framework_delete", kwargs={"pk": compliance_framework_a.pk}),
        reverse("assets:asset_compliance_audit_delete", kwargs={"pk": compliance_audit_a.pk}),
        reverse("assets:asset_compliance_audit_start", kwargs={"pk": compliance_audit_a.pk}),
        reverse("assets:asset_compliance_audit_complete", kwargs={"pk": compliance_audit_a.pk}),
        reverse("assets:asset_permit_license_delete", kwargs={"pk": permit_license_a.pk}),
        reverse("assets:asset_permit_license_renew", kwargs={"pk": permit_license_a.pk}),
        reverse("assets:asset_compliance_incident_delete", kwargs={"pk": compliance_incident_a.pk}),
        reverse("assets:asset_compliance_incident_resolve", kwargs={"pk": compliance_incident_a.pk}),
        reverse("assets:asset_compliance_incident_close", kwargs={"pk": compliance_incident_a.pk}),
    ]
    assert len(post_only_urls) == 9
    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 on GET for {url}"


# ==============================================================================
# 3. Mass Assignment & Tamper Protection Tests
# ==============================================================================


def test_compliance_security_mass_assignment_tenant_and_number_tamper_resistant(
    client_a, tenant_a, tenant_b, compliance_framework_a, operational_asset_a
):
    """ModelForms and views ignore or reject attempts to manipulate tenant, number, created_at, or updated_at."""
    # 1. Framework: attempting to inject tenant_b and custom number
    f_payload = _compliance_framework_payload(
        code="MASS-FRM-01",
        tenant=str(tenant_b.pk),
        number="CMP-FRM-999999",
        created_at="2020-01-01T00:00:00",
    )
    r_frm = client_a.post(reverse("assets:asset_compliance_framework_create"), f_payload)
    assert r_frm.status_code == 302
    created_frm = AssetComplianceFramework.objects.get(tenant=tenant_a, code="MASS-FRM-01")
    assert created_frm.tenant == tenant_a
    assert created_frm.number != "CMP-FRM-999999"
    assert not AssetComplianceFramework.objects.filter(tenant=tenant_b, code="MASS-FRM-01").exists()

    # 2. Audit: attempting to inject tenant_b and custom number
    a_payload = _compliance_audit_payload(
        compliance_framework_a,
        title="Mass Audit Check",
        tenant=str(tenant_b.pk),
        number="CMP-AUD-999999",
        created_at="2020-01-01T00:00:00",
    )
    r_aud = client_a.post(reverse("assets:asset_compliance_audit_create"), a_payload)
    assert r_aud.status_code == 302
    created_aud = AssetComplianceAudit.objects.get(tenant=tenant_a, title="Mass Audit Check")
    assert created_aud.tenant == tenant_a
    assert created_aud.number != "CMP-AUD-999999"
    assert not AssetComplianceAudit.objects.filter(tenant=tenant_b, title="Mass Audit Check").exists()

    # 3. Permit: attempting to inject tenant_b and custom number
    p_payload = _compliance_permit_payload(
        operational_asset_a,
        permit_number="MASS-PERMIT-01",
        tenant=str(tenant_b.pk),
        number="CMP-LIC-999999",
    )
    r_per = client_a.post(reverse("assets:asset_permit_license_create"), p_payload)
    assert r_per.status_code == 302
    created_per = AssetPermitLicense.objects.get(tenant=tenant_a, permit_number="MASS-PERMIT-01")
    assert created_per.tenant == tenant_a
    assert created_per.number != "CMP-LIC-999999"
    assert not AssetPermitLicense.objects.filter(tenant=tenant_b, permit_number="MASS-PERMIT-01").exists()

    # 4. Incident: attempting to inject tenant_b and custom number
    i_payload = _compliance_incident_payload(
        asset=str(operational_asset_a.pk),
        title="Mass Incident Check",
        tenant=str(tenant_b.pk),
        number="CMP-INC-999999",
    )
    r_inc = client_a.post(reverse("assets:asset_compliance_incident_create"), i_payload)
    assert r_inc.status_code == 302
    created_inc = AssetComplianceIncident.objects.get(tenant=tenant_a, title="Mass Incident Check")
    assert created_inc.tenant == tenant_a
    assert created_inc.number != "CMP-INC-999999"
    assert not AssetComplianceIncident.objects.filter(tenant=tenant_b, title="Mass Incident Check").exists()


def test_compliance_security_audit_form_status_manipulation_terminal_state_blocked(
    client_a, tenant_a, compliance_framework_a
):
    """Submitting status='completed' in AssetComplianceAuditForm is blocked with validation error."""
    # 1. Direct Form Validation - choice rejected from available choices or clean_status
    data = _compliance_audit_payload(compliance_framework_a, status="completed")
    form = AssetComplianceAuditForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    status_errs = " ".join(str(e) for e in form.errors["status"])
    assert "not one of the available choices" in status_errs or "Status cannot be set to Completed directly" in status_errs

    # 2. View POST create attempt
    resp = client_a.post(reverse("assets:asset_compliance_audit_create"), data)
    assert resp.status_code == 200
    assert not AssetComplianceAudit.objects.filter(tenant=tenant_a, title=data["title"]).exists()


def test_compliance_security_incident_form_status_manipulation_terminal_state_blocked(
    client_a, tenant_a, operational_asset_a
):
    """Submitting status='resolved' or 'closed' in AssetComplianceIncidentForm is blocked with validation error."""
    # 1. Attempt 'resolved'
    data_res = _compliance_incident_payload(asset=str(operational_asset_a.pk), status="resolved")
    form_res = AssetComplianceIncidentForm(data=data_res, tenant=tenant_a)
    assert not form_res.is_valid()
    assert "status" in form_res.errors
    errs_res = " ".join(str(e) for e in form_res.errors["status"])
    assert "not one of the available choices" in errs_res or "Status cannot be set to Resolved or Closed directly" in errs_res

    resp_res = client_a.post(reverse("assets:asset_compliance_incident_create"), data_res)
    assert resp_res.status_code == 200
    assert not AssetComplianceIncident.objects.filter(tenant=tenant_a, title=data_res["title"]).exists()

    # 2. Attempt 'closed'
    data_cls = _compliance_incident_payload(asset=str(operational_asset_a.pk), status="closed")
    form_cls = AssetComplianceIncidentForm(data=data_cls, tenant=tenant_a)
    assert not form_cls.is_valid()
    assert "status" in form_cls.errors
    errs_cls = " ".join(str(e) for e in form_cls.errors["status"])
    assert "not one of the available choices" in errs_cls or "Status cannot be set to Resolved or Closed directly" in errs_cls

    resp_cls = client_a.post(reverse("assets:asset_compliance_incident_create"), data_cls)
    assert resp_cls.status_code == 200
    assert not AssetComplianceIncident.objects.filter(tenant=tenant_a, title=data_cls["title"]).exists()


# ==============================================================================
# 4. Status & Business Invariant Guards
# ==============================================================================


def test_compliance_security_delete_completed_audit_blocked(client_a, compliance_audit_a):
    """Deleting a completed compliance audit is blocked in view logic and flashes an error message."""
    assert compliance_audit_a.status == "completed"
    url = reverse("assets:asset_compliance_audit_delete", kwargs={"pk": compliance_audit_a.pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_audit_detail", kwargs={"pk": compliance_audit_a.pk})

    messages = _compliance_get_flash_messages(resp)
    assert any("completed compliance audit" in m.lower() and "cannot be deleted" in m.lower() for m in messages)

    compliance_audit_a.refresh_from_db()
    assert compliance_audit_a.status == "completed"
    assert AssetComplianceAudit.objects.filter(pk=compliance_audit_a.pk).exists()


def test_compliance_security_edit_completed_audit_blocked(client_a, compliance_audit_a, compliance_framework_a):
    """Editing a completed compliance audit is blocked in view logic and redirects to detail."""
    assert compliance_audit_a.status == "completed"
    url = reverse("assets:asset_compliance_audit_edit", kwargs={"pk": compliance_audit_a.pk})

    # GET redirect
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("assets:asset_compliance_audit_detail", kwargs={"pk": compliance_audit_a.pk})

    # POST redirect
    payload = _compliance_audit_payload(compliance_framework_a, title="Tampered Completed Title")
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:asset_compliance_audit_detail", kwargs={"pk": compliance_audit_a.pk})

    compliance_audit_a.refresh_from_db()
    assert compliance_audit_a.title != "Tampered Completed Title"


def test_compliance_security_delete_incident_with_fines_blocked(
    client_a, tenant_a, operational_asset_a
):
    """Deleting a closed compliance incident with assessed fines is blocked in view logic."""
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        title="Settled Incident With Fine",
        incident_date=timezone.now() - timezone.timedelta(days=20),
        discovery_date=timezone.now().date() - timezone.timedelta(days=19),
        incident_type="emissions_exceedance",
        severity="serious",
        asset=operational_asset_a,
        fine_assessed=Decimal("15000.00"),
        fine_paid=Decimal("15000.00"),
        status="closed",
    )
    url = reverse("assets:asset_compliance_incident_delete", kwargs={"pk": incident.pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_incident_detail", kwargs={"pk": incident.pk})

    messages = _compliance_get_flash_messages(resp)
    assert any("settled compliance incident" in m.lower() and "cannot be deleted" in m.lower() for m in messages)

    assert AssetComplianceIncident.objects.filter(pk=incident.pk).exists()


def test_compliance_security_edit_incident_with_fines_blocked(
    client_a, tenant_a, operational_asset_a
):
    """Editing a closed compliance incident with assessed fines is blocked in view logic."""
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        title="Settled Incident Cannot Edit",
        incident_date=timezone.now() - timezone.timedelta(days=20),
        discovery_date=timezone.now().date() - timezone.timedelta(days=19),
        incident_type="emissions_exceedance",
        severity="serious",
        asset=operational_asset_a,
        fine_assessed=Decimal("10000.00"),
        fine_paid=Decimal("10000.00"),
        status="closed",
    )
    url = reverse("assets:asset_compliance_incident_edit", kwargs={"pk": incident.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("assets:asset_compliance_incident_detail", kwargs={"pk": incident.pk})

    payload = _compliance_incident_payload(asset=str(operational_asset_a.pk), title="Tampered Closed Incident")
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:asset_compliance_incident_detail", kwargs={"pk": incident.pk})

    incident.refresh_from_db()
    assert incident.title != "Tampered Closed Incident"


def test_compliance_security_renew_revoked_or_suspended_permit_blocked(
    client_a, tenant_a, operational_asset_a
):
    """Renewing a revoked or suspended permit/license is blocked in view logic."""
    permit = AssetPermitLicense.objects.create(
        tenant=tenant_a,
        permit_name="Permit Guard Verification",
        permit_number="PERM-GUARD-01",
        permit_type="environmental_emissions",
        asset=operational_asset_a,
        issue_date=timezone.now().date() - timezone.timedelta(days=100),
        effective_date=timezone.now().date() - timezone.timedelta(days=100),
        expiration_date=timezone.now().date() + timezone.timedelta(days=265),
        status="revoked",
    )
    url = reverse("assets:asset_permit_license_renew", kwargs={"pk": permit.pk})

    # 1. Attempt while revoked
    resp_rev = client_a.post(url)
    assert resp_rev.status_code == 302
    permit.refresh_from_db()
    assert permit.status == "revoked"
    messages_rev = _compliance_get_flash_messages(resp_rev)
    assert any("cannot be renewed while revoked" in m.lower() for m in messages_rev)

    # 2. Attempt while suspended
    permit.status = "suspended"
    permit.save(update_fields=["status"])
    resp_susp = client_a.post(url)
    assert resp_susp.status_code == 302
    permit.refresh_from_db()
    assert permit.status == "suspended"
    messages_susp = _compliance_get_flash_messages(resp_susp)
    assert any("cannot be renewed while suspended" in m.lower() for m in messages_susp)


def test_compliance_security_audit_workflow_status_invariants(
    client_a, tenant_a, compliance_framework_a
):
    """Audit start enforces scheduled state, and complete enforces active fieldwork."""
    audit = AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        framework=compliance_framework_a,
        title="Audit Workflow Transition Guard",
        audit_type="internal",
        audit_date=timezone.now().date(),
        status="in_progress",
    )
    # Start on already in_progress audit is blocked
    resp_start = client_a.post(reverse("assets:asset_compliance_audit_start", kwargs={"pk": audit.pk}))
    assert resp_start.status_code == 302
    messages_start = _compliance_get_flash_messages(resp_start)
    assert any("cannot be started from status" in m.lower() for m in messages_start)

    # Transition to cancelled
    audit.status = "cancelled"
    audit.save(update_fields=["status"])
    resp_comp = client_a.post(reverse("assets:asset_compliance_audit_complete", kwargs={"pk": audit.pk}))
    assert resp_comp.status_code == 302
    messages_comp = _compliance_get_flash_messages(resp_comp)
    assert any("already closed or cancelled" in m.lower() for m in messages_comp)
    audit.refresh_from_db()
    assert audit.status == "cancelled"


def test_compliance_security_incident_workflow_status_invariants(
    client_a, tenant_a, operational_asset_a
):
    """Incident close requires resolved status, and resolve blocks cancelled/closed incidents."""
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        title="Incident Invariant Guard",
        incident_date=timezone.now() - timezone.timedelta(days=5),
        discovery_date=timezone.now().date() - timezone.timedelta(days=4),
        incident_type="unpermitted_discharge",
        severity="minor",
        asset=operational_asset_a,
        status="open",
    )
    # Attempting to close an open incident without resolving
    resp_close = client_a.post(reverse("assets:asset_compliance_incident_close", kwargs={"pk": incident.pk}))
    assert resp_close.status_code == 302
    messages_close = _compliance_get_flash_messages(resp_close)
    assert any("must be resolved before closing" in m.lower() for m in messages_close)
    incident.refresh_from_db()
    assert incident.status == "open"

    # Set to closed directly and attempt to resolve
    incident.status = "closed"
    incident.save(update_fields=["status"])
    resp_res = client_a.post(reverse("assets:asset_compliance_incident_resolve", kwargs={"pk": incident.pk}))
    assert resp_res.status_code == 302
    messages_res = _compliance_get_flash_messages(resp_res)
    assert any("cannot be marked as resolved" in m.lower() for m in messages_res)


def test_compliance_security_framework_delete_protected_on_linked_audits(
    client_a, compliance_framework_a, compliance_audit_a
):
    """Deleting a framework with linked audit records is intercepted by ProtectedError with user flash message."""
    url = reverse("assets:asset_compliance_framework_delete", kwargs={"pk": compliance_framework_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_framework_detail", kwargs={"pk": compliance_framework_a.pk})

    messages = _compliance_get_flash_messages(resp)
    assert any("cannot delete compliance framework" in m.lower() and "related audit records exist" in m.lower() for m in messages)

    assert AssetComplianceFramework.objects.filter(pk=compliance_framework_a.pk).exists()


# ==============================================================================
# 5. Audit Trail Verification Tests
# ==============================================================================


def test_compliance_security_audit_log_framework_lifecycle(client_a, tenant_a, admin_user):
    """Framework create, update, and delete record AuditLog rows with acting user and tenant."""
    # 1. Create
    create_url = reverse("assets:asset_compliance_framework_create")
    payload = _compliance_framework_payload(code="AUD-FRM-01", name="Audit Log Framework")
    client_a.post(create_url, payload)
    frm = AssetComplianceFramework.objects.get(tenant=tenant_a, code="AUD-FRM-01")
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="create", object_id=frm.pk).exists()

    # 2. Update
    edit_url = reverse("assets:asset_compliance_framework_edit", kwargs={"pk": frm.pk})
    payload["name"] = "Audit Log Framework Updated"
    client_a.post(edit_url, payload)
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="update", object_id=frm.pk).exists()

    # 3. Delete
    pk = frm.pk
    delete_url = reverse("assets:asset_compliance_framework_delete", kwargs={"pk": pk})
    client_a.post(delete_url)
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="delete", object_id=pk).exists()


def test_compliance_security_audit_log_audit_lifecycle_and_transitions(
    client_a, tenant_a, admin_user, compliance_framework_a
):
    """Audit create, update, start, complete, and delete record AuditLog rows with acting user and tenant."""
    # 1. Create
    create_url = reverse("assets:asset_compliance_audit_create")
    payload = _compliance_audit_payload(compliance_framework_a, title="Audit Log Trace Audit")
    client_a.post(create_url, payload)
    aud = AssetComplianceAudit.objects.get(tenant=tenant_a, title="Audit Log Trace Audit")
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="create", object_id=aud.pk).exists()

    # 2. Update
    edit_url = reverse("assets:asset_compliance_audit_edit", kwargs={"pk": aud.pk})
    payload["title"] = "Audit Log Trace Audit Updated"
    client_a.post(edit_url, payload)
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="update", object_id=aud.pk).exists()

    # 3. Start
    start_url = reverse("assets:asset_compliance_audit_start", kwargs={"pk": aud.pk})
    client_a.post(start_url)
    assert AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="update", object_id=aud.pk, changes__details__icontains="started fieldwork"
    ).exists()

    # 4. Complete
    complete_url = reverse("assets:asset_compliance_audit_complete", kwargs={"pk": aud.pk})
    client_a.post(complete_url)
    assert AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="update", object_id=aud.pk, changes__details__icontains="completed and signed off"
    ).exists()

    # 5. Delete scheduled audit
    del_aud = AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        framework=compliance_framework_a,
        title="Audit To Delete For Log Trace",
        audit_type="internal",
        audit_date=timezone.now().date(),
        status="scheduled",
    )
    del_pk = del_aud.pk
    delete_url = reverse("assets:asset_compliance_audit_delete", kwargs={"pk": del_pk})
    client_a.post(delete_url)
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="delete", object_id=del_pk).exists()


def test_compliance_security_audit_log_permit_lifecycle_and_transitions(
    client_a, tenant_a, admin_user, operational_asset_a
):
    """Permit create, update, renew, and delete record AuditLog rows with acting user and tenant."""
    # 1. Create
    create_url = reverse("assets:asset_permit_license_create")
    payload = _compliance_permit_payload(operational_asset_a, permit_number="PERM-AUD-LOG-01")
    client_a.post(create_url, payload)
    permit = AssetPermitLicense.objects.get(tenant=tenant_a, permit_number="PERM-AUD-LOG-01")
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="create", object_id=permit.pk).exists()

    # 2. Update
    edit_url = reverse("assets:asset_permit_license_edit", kwargs={"pk": permit.pk})
    payload["permit_name"] = "Permit Trace Updated"
    client_a.post(edit_url, payload)
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="update", object_id=permit.pk).exists()

    # 3. Renew
    renew_url = reverse("assets:asset_permit_license_renew", kwargs={"pk": permit.pk})
    client_a.post(renew_url)
    assert AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="update", object_id=permit.pk, changes__details__icontains="pending renewal"
    ).exists()

    # 4. Delete
    pk = permit.pk
    delete_url = reverse("assets:asset_permit_license_delete", kwargs={"pk": pk})
    client_a.post(delete_url)
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="delete", object_id=pk).exists()


def test_compliance_security_audit_log_incident_lifecycle_and_transitions(
    client_a, tenant_a, admin_user, operational_asset_a
):
    """Incident create, update, resolve, close, and delete record AuditLog rows with acting user and tenant."""
    # 1. Create
    create_url = reverse("assets:asset_compliance_incident_create")
    payload = _compliance_incident_payload(asset=str(operational_asset_a.pk), title="Incident Audit Trace")
    client_a.post(create_url, payload)
    inc = AssetComplianceIncident.objects.get(tenant=tenant_a, title="Incident Audit Trace")
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="create", object_id=inc.pk).exists()

    # 2. Update
    edit_url = reverse("assets:asset_compliance_incident_edit", kwargs={"pk": inc.pk})
    payload["title"] = "Incident Audit Trace Updated"
    client_a.post(edit_url, payload)
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="update", object_id=inc.pk).exists()

    # 3. Resolve
    resolve_url = reverse("assets:asset_compliance_incident_resolve", kwargs={"pk": inc.pk})
    client_a.post(resolve_url)
    assert AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="update", object_id=inc.pk, changes__details__icontains="resolved compliance incident"
    ).exists()

    # 4. Close
    close_url = reverse("assets:asset_compliance_incident_close", kwargs={"pk": inc.pk})
    client_a.post(close_url)
    assert AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="update", object_id=inc.pk, changes__details__icontains="closed compliance incident"
    ).exists()

    # 5. Delete an incident with no fines
    del_inc = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        title="Incident To Delete For Log Trace",
        incident_date=timezone.now(),
        discovery_date=timezone.now().date(),
        incident_type="unpermitted_discharge",
        severity="minor",
        fine_assessed=Decimal("0.00"),
        status="open",
    )
    del_pk = del_inc.pk
    delete_url = reverse("assets:asset_compliance_incident_delete", kwargs={"pk": del_pk})
    client_a.post(delete_url)
    assert AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="delete", object_id=del_pk).exists()
