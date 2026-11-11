"""Integration view test suite for Sub-module 11.11: Asset Compliance & Regulatory Management.

Tests cover all 4 entities across all standard and transition workflows:
1. AssetComplianceFramework:
   - asset_compliance_framework_list (200, context keys, search q, filters, pagination, tenant isolation)
   - asset_compliance_framework_create (GET form, POST valid -> 302 with AuditLog, POST invalid -> 200, reject_foreign)
   - asset_compliance_framework_detail (GET 200 with framework/audits/incidents, cross-tenant IDOR 404)
   - asset_compliance_framework_edit (GET 200 with is_edit=True, POST valid -> 302 with AuditLog, cross-tenant 404)
   - asset_compliance_framework_delete (POST 302 unlinked delete, ProtectedError on linked audits -> redirect to detail with error, require_POST 405, tenant_admin_required 403, cross-tenant 404)

2. AssetComplianceAudit:
   - asset_compliance_audit_list (200, context keys, filters by q/status/type/rating/framework, pagination, tenant isolation)
   - asset_compliance_audit_create (GET form with initial framework, POST valid -> 302 with AuditLog, checkpoint validation, status guard, reject_foreign)
   - asset_compliance_audit_detail (GET 200 with audit/incidents, cross-tenant IDOR 404)
   - asset_compliance_audit_edit (GET 200 with is_edit=True, POST valid -> 302 with AuditLog, status guard on completed audit, cross-tenant 404)
   - asset_compliance_audit_start (POST 302 scheduled -> in_progress with AuditLog, status guard on non-scheduled, require_POST 405, cross-tenant 404)
   - asset_compliance_audit_complete (POST 302 in_progress -> completed with completed_at timestamp and AuditLog, already closed guard, require_POST 405, cross-tenant 404)
   - asset_compliance_audit_delete (POST 302 delete scheduled with AuditLog, completed audit guard, require_POST 405, tenant_admin_required 403, cross-tenant 404)

3. AssetPermitLicense:
   - asset_compliance_permit_license_list (200, context keys, filters by q/status/type/authority, pagination, tenant isolation)
   - asset_compliance_permit_license_create (GET form with initial asset, POST valid -> 302 with AuditLog, expiration date validation, reject_foreign)
   - asset_compliance_permit_license_detail (GET 200 with permit/incidents, cross-tenant IDOR 404)
   - asset_compliance_permit_license_edit (GET 200 with is_edit=True, POST valid -> 302 with AuditLog, cross-tenant 404)
   - asset_compliance_permit_license_renew (POST 302 active -> pending_renewal with AuditLog, revoked/suspended status guard, require_POST 405, cross-tenant 404)
   - asset_compliance_permit_license_delete (POST 302 delete with AuditLog, require_POST 405, tenant_admin_required 403, cross-tenant 404)

4. AssetComplianceIncident:
   - asset_compliance_incident_list (200, context keys, filters by q/status/severity/type/agency, pagination, tenant isolation)
   - asset_compliance_incident_create (GET form with initial params, POST valid -> 302 with AuditLog, fine amount validation, status guard, reject_foreign)
   - asset_compliance_incident_detail (GET 200 with incident, cross-tenant IDOR 404)
   - asset_compliance_incident_edit (GET 200 with is_edit=True, POST valid -> 302 with AuditLog, status guard on settled incident with fines, cross-tenant 404)
   - asset_compliance_incident_resolve (POST 302 open -> resolved with actual_resolution_date and AuditLog, non-resolvable status guard, require_POST 405, cross-tenant 404)
   - asset_compliance_incident_close (POST 302 resolved -> closed with AuditLog, unresolved status guard, require_POST 405, cross-tenant 404)
   - asset_compliance_incident_delete (POST 302 delete open with AuditLog, settled incident with fines guard, require_POST 405, tenant_admin_required 403, cross-tenant 404)

5. Security:
   - Unauthenticated requests redirect to login for all endpoints.
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

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
        "code": "OSHA-1910-PSM-01",
        "framework_type": "regulatory",
        "effective_date": today.isoformat(),
        "revision": "2024 Edition",
        "mandatory_audit_cycle_months": "12",
        "readiness_score": "95",
        "description": "Standard for managing hazards associated with highly hazardous chemicals.",
        "status": "active",
    }
    data.update(overrides)
    return data


def _compliance_audit_payload(framework, asset=None, **overrides):
    """Build a valid payload for AssetComplianceAuditForm."""
    today = timezone.now().date()
    data = {
        "title": "Annual Machine Guarding Safety Audit",
        "framework": str(framework.pk),
        "audit_type": "internal",
        "audit_date": today.isoformat(),
        "scope_description": "Evaluation of physical interlocks and emergency stop systems.",
        "total_checkpoints": "30",
        "passed_checkpoints": "28",
        "minor_findings_count": "2",
        "major_findings_count": "0",
        "critical_findings_count": "0",
        "compliance_rating": "minor_deficiencies",
        "summary_findings": "Two labeling tags replaced on bay 4 disconnect panels.",
        "status": "scheduled",
    }
    if asset is not None:
        data["asset"] = str(asset.pk)
    data.update(overrides)
    return data


def _compliance_permit_payload(asset, issuing_authority=None, **overrides):
    """Build a valid payload for AssetPermitLicenseForm."""
    today = timezone.now().date()
    data = {
        "permit_name": "Stationary Source Air Emissions Operating Permit",
        "permit_number": "EPA-AIR-2026-9042",
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


def _compliance_incident_payload(asset, **overrides):
    """Build a valid payload for AssetComplianceIncidentForm."""
    today = timezone.now().date()
    now_dt = timezone.now().strftime("%Y-%m-%dT%H:%M")
    data = {
        "title": "Temporary Coolant Sump Overflow",
        "incident_date": now_dt,
        "discovery_date": today.isoformat(),
        "incident_type": "unpermitted_discharge",
        "severity": "other_than_serious",
        "asset": str(asset.pk),
        "citation_reference": "EPA-NOV-2026-004",
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
# 1. Framework Views Tests
# ==============================================================================

def test_compliance_view_framework_list_success(client_a, compliance_framework_a):
    """Framework list renders 200 with required context keys and metrics."""
    url = reverse("assets:asset_compliance_framework_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "frameworks" in resp.context
    assert compliance_framework_a in resp.context["frameworks"]
    assert "status_choices" in resp.context
    assert "type_choices" in resp.context
    assert "category_list" in resp.context
    assert "total_frameworks" in resp.context
    assert "active_count" in resp.context
    assert "avg_readiness_score" in resp.context
    assert resp.context["total_frameworks"] >= 1
    assert resp.context["active_count"] >= 1


def test_compliance_view_framework_list_tenant_isolation(client_a, client_b, compliance_framework_a, compliance_framework_b):
    """Client A sees only Tenant A frameworks; Client B sees only Tenant B frameworks."""
    url = reverse("assets:asset_compliance_framework_list")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["frameworks"])
    assert compliance_framework_a in items_a
    assert compliance_framework_b not in items_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["frameworks"])
    assert compliance_framework_b in items_b
    assert compliance_framework_a not in items_b


def test_compliance_view_framework_list_filters(client_a, compliance_framework_a, category_a, tenant_a):
    """Search query, status, framework_type, and category filters operate accurately."""
    url = reverse("assets:asset_compliance_framework_list")

    # Search filter matching
    resp = client_a.get(f"{url}?q=OSHA")
    assert resp.status_code == 200
    assert compliance_framework_a in resp.context["frameworks"]

    # Search filter non-matching
    resp_empty = client_a.get(f"{url}?q=NONEXISTENT_QUERY_XYZ")
    assert resp_empty.status_code == 200
    assert compliance_framework_a not in resp_empty.context["frameworks"]

    # Status filter
    resp_active = client_a.get(f"{url}?status=active")
    assert compliance_framework_a in resp_active.context["frameworks"]
    resp_archived = client_a.get(f"{url}?status=archived")
    assert compliance_framework_a not in resp_archived.context["frameworks"]

    # Framework type filter
    resp_reg = client_a.get(f"{url}?framework_type=regulatory")
    assert compliance_framework_a in resp_reg.context["frameworks"]
    resp_vol = client_a.get(f"{url}?framework_type=voluntary_standard")
    assert compliance_framework_a not in resp_vol.context["frameworks"]

    # Category filter
    resp_cat = client_a.get(f"{url}?category={category_a.pk}")
    assert compliance_framework_a in resp_cat.context["frameworks"]
    resp_cat_junk = client_a.get(f"{url}?category=999999")
    assert compliance_framework_a not in resp_cat_junk.context["frameworks"]


def test_compliance_view_framework_list_pagination(client_a, tenant_a):
    """Pagination divides recordsets correctly across page thresholds."""
    url = reverse("assets:asset_compliance_framework_list")
    today = timezone.now().date()
    # Create 26 frameworks to exceed 25 per-page limit
    created = []
    for i in range(26):
        fw = AssetComplianceFramework.objects.create(
            tenant=tenant_a,
            name=f"Standard Framework {i:02d}",
            code=f"STD-FW-{i:02d}",
            framework_type="statutory",
            effective_date=today,
            mandatory_audit_cycle_months=12,
            readiness_score=85,
            status="active",
        )
        created.append(fw)

    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["frameworks"]) == 25
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(f"{url}?page=2")
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["frameworks"]) >= 1
    assert resp_p2.context["page_obj"].has_previous()


def test_compliance_view_framework_detail_success(client_a, compliance_framework_a, compliance_audit_a, compliance_incident_a):
    """Detail view renders 200 with framework, linked audits, and linked incidents."""
    url = reverse("assets:asset_compliance_framework_detail", kwargs={"pk": compliance_framework_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["framework"] == compliance_framework_a
    assert compliance_audit_a in resp.context["audits"]
    assert compliance_incident_a in resp.context["incidents"]


def test_compliance_view_framework_detail_foreign_tenant_404(client_a, compliance_framework_b):
    """Cross-tenant access to framework detail yields HTTP 404."""
    url = reverse("assets:asset_compliance_framework_detail", kwargs={"pk": compliance_framework_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_compliance_view_framework_create_get(client_a):
    """GET create renders form with is_edit=False and empty framework context."""
    url = reverse("assets:asset_compliance_framework_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["framework"] is None


def test_compliance_view_framework_create_post_valid(client_a, tenant_a, category_a, vendor_party_a):
    """Valid POST creates framework, logs audit entry, sets success message, and redirects to detail."""
    url = reverse("assets:asset_compliance_framework_create")
    payload = _compliance_framework_payload(
        code="OSHA-1910-NEW",
        name="Process Safety Management Revision C",
        applicable_category=str(category_a.pk),
        regulatory_agency=str(vendor_party_a.pk),
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 302

    created = AssetComplianceFramework.objects.get(code="OSHA-1910-NEW", tenant=tenant_a)
    assert resp.url == reverse("assets:asset_compliance_framework_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.applicable_category == category_a
    assert created.regulatory_agency == vendor_party_a

    # Verify audit log creation
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        target_object_id=str(created.pk),
    ).exists()


def test_compliance_view_framework_create_post_invalid(client_a):
    """Invalid POST with missing required fields renders 200 with form errors."""
    url = reverse("assets:asset_compliance_framework_create")
    resp = client_a.post(url, {})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert "name" in resp.context["form"].errors
    assert "code" in resp.context["form"].errors


def test_compliance_view_framework_create_reject_foreign(client_a, tenant_a, category_b, vendor_party_b):
    """Form rejects foreign tenant category and regulatory agency via reject_foreign."""
    url = reverse("assets:asset_compliance_framework_create")
    payload = _compliance_framework_payload(
        code="OSHA-CROSS-TENANT",
        applicable_category=str(category_b.pk),
        regulatory_agency=str(vendor_party_b.pk),
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert not AssetComplianceFramework.objects.filter(code="OSHA-CROSS-TENANT").exists()


def test_compliance_view_framework_edit_get(client_a, compliance_framework_a):
    """GET edit renders form populated with framework and is_edit=True."""
    url = reverse("assets:asset_compliance_framework_edit", kwargs={"pk": compliance_framework_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["framework"] == compliance_framework_a


def test_compliance_view_framework_edit_post_valid(client_a, tenant_a, compliance_framework_a):
    """Valid POST updates framework, logs audit entry, and redirects to detail."""
    url = reverse("assets:asset_compliance_framework_edit", kwargs={"pk": compliance_framework_a.pk})
    payload = _compliance_framework_payload(
        name="OSHA 1910.119 Updated Safety Plan",
        code=compliance_framework_a.code,
        readiness_score="98",
        status="active",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_framework_detail", kwargs={"pk": compliance_framework_a.pk})

    compliance_framework_a.refresh_from_db()
    assert compliance_framework_a.name == "OSHA 1910.119 Updated Safety Plan"
    assert compliance_framework_a.readiness_score == 98

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target_object_id=str(compliance_framework_a.pk),
    ).exists()


def test_compliance_view_framework_edit_foreign_tenant_404(client_a, compliance_framework_b):
    """Cross-tenant framework edit returns 404."""
    url = reverse("assets:asset_compliance_framework_edit", kwargs={"pk": compliance_framework_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_compliance_view_framework_delete_post_unlinked(client_a, tenant_a):
    """POST on unlinked framework deletes record, creates AuditLog, and redirects to list."""
    today = timezone.now().date()
    fw = AssetComplianceFramework.objects.create(
        tenant=tenant_a,
        name="Unlinked EPA Standard",
        code="EPA-UNLINKED-01",
        framework_type="environmental",
        effective_date=today,
        status="active",
    )
    url = reverse("assets:asset_compliance_framework_delete", kwargs={"pk": fw.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_framework_list")
    assert not AssetComplianceFramework.objects.filter(pk=fw.pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        target_object_id=str(fw.pk),
    ).exists()


def test_compliance_view_framework_delete_post_protected_with_audits(client_a, compliance_framework_a, compliance_audit_a):
    """Deleting framework with linked audits triggers ProtectedError handling and redirects to detail with flash message."""
    url = reverse("assets:asset_compliance_framework_delete", kwargs={"pk": compliance_framework_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_framework_detail", kwargs={"pk": compliance_framework_a.pk})
    assert AssetComplianceFramework.objects.filter(pk=compliance_framework_a.pk).exists()

    msgs = _compliance_get_flash_messages(resp)
    assert any("Cannot delete compliance framework" in m for m in msgs)


def test_compliance_view_framework_delete_get_405(client_a, compliance_framework_a):
    """GET on framework delete returns 405 Method Not Allowed."""
    url = reverse("assets:asset_compliance_framework_delete", kwargs={"pk": compliance_framework_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_compliance_view_framework_delete_member_forbidden(member_client, compliance_framework_a):
    """Non-admin user cannot delete framework and receives 403 Forbidden."""
    url = reverse("assets:asset_compliance_framework_delete", kwargs={"pk": compliance_framework_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_compliance_view_framework_delete_foreign_tenant_404(client_a, compliance_framework_b):
    """Cross-tenant framework delete returns 404."""
    url = reverse("assets:asset_compliance_framework_delete", kwargs={"pk": compliance_framework_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 2. Audit Views Tests
# ==============================================================================

def test_compliance_view_audit_list_success(client_a, compliance_audit_a):
    """Audit list view renders 200 with required context keys and metrics."""
    url = reverse("assets:asset_compliance_audit_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "audits" in resp.context
    assert compliance_audit_a in resp.context["audits"]
    assert "status_choices" in resp.context
    assert "type_choices" in resp.context
    assert "rating_choices" in resp.context
    assert "framework_list" in resp.context
    assert "total_audits" in resp.context
    assert "in_progress_count" in resp.context
    assert "completed_count" in resp.context
    assert "breaches_count" in resp.context
    assert resp.context["total_audits"] >= 1


def test_compliance_view_audit_list_tenant_isolation(client_a, client_b, compliance_audit_a, compliance_audit_b):
    """Client A sees only Tenant A audits; Client B sees only Tenant B audits."""
    url = reverse("assets:asset_compliance_audit_list")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    audits_a = list(resp_a.context["audits"])
    assert compliance_audit_a in audits_a
    assert compliance_audit_b not in audits_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    audits_b = list(resp_b.context["audits"])
    assert compliance_audit_b in audits_b
    assert compliance_audit_a not in audits_b


def test_compliance_view_audit_list_filters(client_a, compliance_audit_a, compliance_framework_a):
    """Search, status, audit_type, compliance_rating, and framework filters filter accurately."""
    url = reverse("assets:asset_compliance_audit_list")

    # Search filter matching
    resp = client_a.get(f"{url}?q=Machine")
    assert resp.status_code == 200
    assert compliance_audit_a in resp.context["audits"]

    # Search filter non-matching
    resp_empty = client_a.get(f"{url}?q=UNKNOWN_NONEXISTENT_XYZ")
    assert resp_empty.status_code == 200
    assert compliance_audit_a not in resp_empty.context["audits"]

    # Status filter
    resp_comp = client_a.get(f"{url}?status=completed")
    assert compliance_audit_a in resp_comp.context["audits"]
    resp_sched = client_a.get(f"{url}?status=scheduled")
    assert compliance_audit_a not in resp_sched.context["audits"]

    # Type filter
    resp_int = client_a.get(f"{url}?audit_type=internal")
    assert compliance_audit_a in resp_int.context["audits"]
    resp_ext = client_a.get(f"{url}?audit_type=external_regulatory")
    assert compliance_audit_a not in resp_ext.context["audits"]

    # Rating filter
    resp_fc = client_a.get(f"{url}?compliance_rating=fully_compliant")
    assert compliance_audit_a in resp_fc.context["audits"]
    resp_nonc = client_a.get(f"{url}?compliance_rating=major_non_conformance")
    assert compliance_audit_a not in resp_nonc.context["audits"]

    # Framework filter
    resp_fw = client_a.get(f"{url}?framework={compliance_framework_a.pk}")
    assert compliance_audit_a in resp_fw.context["audits"]
    resp_fw_junk = client_a.get(f"{url}?framework=999999")
    assert compliance_audit_a not in resp_fw_junk.context["audits"]


def test_compliance_view_audit_list_pagination(client_a, tenant_a, compliance_framework_a):
    """Audit list handles pagination across 25+ records."""
    url = reverse("assets:asset_compliance_audit_list")
    today = timezone.now().date()
    for i in range(26):
        AssetComplianceAudit.objects.create(
            tenant=tenant_a,
            framework=compliance_framework_a,
            title=f"Bulk Audit Record {i:02d}",
            audit_type="internal",
            audit_date=today,
            status="scheduled",
        )

    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["audits"]) == 25
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(f"{url}?page=2")
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["audits"]) >= 1


def test_compliance_view_audit_detail_success(client_a, compliance_audit_a, compliance_incident_a):
    """Detail view renders 200 with audit instance and linked incidents."""
    url = reverse("assets:asset_compliance_audit_detail", kwargs={"pk": compliance_audit_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["audit"] == compliance_audit_a
    assert compliance_incident_a in resp.context["incidents"]


def test_compliance_view_audit_detail_foreign_tenant_404(client_a, compliance_audit_b):
    """Cross-tenant audit detail yields 404."""
    url = reverse("assets:asset_compliance_audit_detail", kwargs={"pk": compliance_audit_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_compliance_view_audit_create_get(client_a, compliance_framework_a):
    """GET create renders form with initial framework argument pre-filled."""
    url = reverse("assets:asset_compliance_audit_create")
    resp = client_a.get(f"{url}?framework={compliance_framework_a.pk}")
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].initial.get("framework") == compliance_framework_a.pk


def test_compliance_view_audit_create_post_valid(client_a, tenant_a, compliance_framework_a, operational_asset_a, admin_user, vendor_party_a):
    """Valid POST creates audit, writes AuditLog, flashes success, and redirects to detail."""
    url = reverse("assets:asset_compliance_audit_create")
    payload = _compliance_audit_payload(
        framework=compliance_framework_a,
        asset=operational_asset_a,
        title="Quarterly PSM Pressure Valve Inspection",
        lead_auditor_user=str(admin_user.pk),
        auditor_party=str(vendor_party_a.pk),
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 302

    created = AssetComplianceAudit.objects.get(title="Quarterly PSM Pressure Valve Inspection", tenant=tenant_a)
    assert resp.url == reverse("assets:asset_compliance_audit_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.status == "scheduled"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        target_object_id=str(created.pk),
    ).exists()


def test_compliance_view_audit_create_post_checkpoint_validation(client_a, compliance_framework_a):
    """POST with passed_checkpoints > total_checkpoints returns 200 with validation error."""
    url = reverse("assets:asset_compliance_audit_create")
    payload = _compliance_audit_payload(
        framework=compliance_framework_a,
        total_checkpoints="10",
        passed_checkpoints="15",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert "passed_checkpoints" in resp.context["form"].errors


def test_compliance_view_audit_create_post_completed_status_forbidden(client_a, compliance_framework_a):
    """Cannot set status='completed' directly via form submission."""
    url = reverse("assets:asset_compliance_audit_create")
    payload = _compliance_audit_payload(
        framework=compliance_framework_a,
        status="completed",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert "status" in resp.context["form"].errors


def test_compliance_view_audit_create_reject_foreign(client_a, compliance_framework_b, operational_asset_b, admin_b, vendor_party_b):
    """Cross-tenant foreign keys are rejected by audit creation."""
    url = reverse("assets:asset_compliance_audit_create")
    payload = _compliance_audit_payload(
        framework=compliance_framework_b,
        asset=operational_asset_b,
        lead_auditor_user=str(admin_b.pk),
        auditor_party=str(vendor_party_b.pk),
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert not AssetComplianceAudit.objects.filter(title="Annual Machine Guarding Safety Audit", framework=compliance_framework_b).exists()


def test_compliance_view_audit_edit_get(client_a, tenant_a, compliance_framework_a):
    """GET edit renders form populated with existing scheduled audit."""
    today = timezone.now().date()
    audit = AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        framework=compliance_framework_a,
        title="Draft Scheduled Audit for Bay 1",
        audit_type="internal",
        audit_date=today,
        status="scheduled",
    )
    url = reverse("assets:asset_compliance_audit_edit", kwargs={"pk": audit.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["audit"] == audit


def test_compliance_view_audit_edit_completed_status_guard(client_a, compliance_audit_a):
    """Completed audit cannot be edited; redirects to detail with error message."""
    assert compliance_audit_a.status == "completed"
    url = reverse("assets:asset_compliance_audit_edit", kwargs={"pk": compliance_audit_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_audit_detail", kwargs={"pk": compliance_audit_a.pk})

    msgs = _compliance_get_flash_messages(resp)
    assert any("cannot be edited" in m for m in msgs)


def test_compliance_view_audit_edit_post_valid(client_a, tenant_a, compliance_framework_a):
    """Valid POST updates editable audit, logs AuditLog, and redirects to detail."""
    today = timezone.now().date()
    audit = AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        framework=compliance_framework_a,
        title="Draft Electrical Guarding Audit",
        audit_type="internal",
        audit_date=today,
        status="scheduled",
    )
    url = reverse("assets:asset_compliance_audit_edit", kwargs={"pk": audit.pk})
    payload = _compliance_audit_payload(
        framework=compliance_framework_a,
        title="Updated Electrical Guarding Audit",
        minor_findings_count="3",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_audit_detail", kwargs={"pk": audit.pk})

    audit.refresh_from_db()
    assert audit.title == "Updated Electrical Guarding Audit"
    assert audit.minor_findings_count == 3

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target_object_id=str(audit.pk),
    ).exists()


def test_compliance_view_audit_edit_foreign_tenant_404(client_a, compliance_audit_b):
    """Cross-tenant audit edit returns 404."""
    url = reverse("assets:asset_compliance_audit_edit", kwargs={"pk": compliance_audit_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_compliance_view_audit_start_success(client_a, tenant_a, compliance_framework_a):
    """POST on scheduled audit starts fieldwork, sets status='in_progress', and writes AuditLog."""
    today = timezone.now().date()
    audit = AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        framework=compliance_framework_a,
        title="Fieldwork Starter Audit",
        audit_type="internal",
        audit_date=today,
        status="scheduled",
    )
    url = reverse("assets:asset_compliance_audit_start", kwargs={"pk": audit.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_audit_detail", kwargs={"pk": audit.pk})

    audit.refresh_from_db()
    assert audit.status == "in_progress"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target_object_id=str(audit.pk),
    ).exists()


def test_compliance_view_audit_start_invalid_status_guard(client_a, compliance_audit_a):
    """Starting an audit that is already completed flashes warning and does not alter status."""
    assert compliance_audit_a.status == "completed"
    url = reverse("assets:asset_compliance_audit_start", kwargs={"pk": compliance_audit_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    compliance_audit_a.refresh_from_db()
    assert compliance_audit_a.status == "completed"

    msgs = _compliance_get_flash_messages(resp)
    assert any("cannot be started" in m for m in msgs)


def test_compliance_view_audit_start_get_405(client_a, compliance_audit_a):
    """GET on audit start returns 405."""
    url = reverse("assets:asset_compliance_audit_start", kwargs={"pk": compliance_audit_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_compliance_view_audit_start_foreign_tenant_404(client_a, compliance_audit_b):
    """Cross-tenant audit start returns 404."""
    url = reverse("assets:asset_compliance_audit_start", kwargs={"pk": compliance_audit_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


def test_compliance_view_audit_complete_success(client_a, tenant_a, compliance_framework_a):
    """POST on in_progress audit transitions to completed, records completed_at and AuditLog."""
    today = timezone.now().date()
    audit = AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        framework=compliance_framework_a,
        title="Fieldwork In-Progress Audit",
        audit_type="internal",
        audit_date=today,
        status="in_progress",
    )
    url = reverse("assets:asset_compliance_audit_complete", kwargs={"pk": audit.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_audit_detail", kwargs={"pk": audit.pk})

    audit.refresh_from_db()
    assert audit.status == "completed"
    assert audit.completed_at is not None

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target_object_id=str(audit.pk),
    ).exists()


def test_compliance_view_audit_complete_already_closed_guard(client_a, tenant_a, compliance_framework_a):
    """Completing an already cancelled audit flashes warning and preserves cancelled status."""
    today = timezone.now().date()
    audit = AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        framework=compliance_framework_a,
        title="Cancelled Audit",
        audit_type="internal",
        audit_date=today,
        status="cancelled",
    )
    url = reverse("assets:asset_compliance_audit_complete", kwargs={"pk": audit.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    audit.refresh_from_db()
    assert audit.status == "cancelled"

    msgs = _compliance_get_flash_messages(resp)
    assert any("already closed or cancelled" in m for m in msgs)


def test_compliance_view_audit_complete_get_405(client_a, compliance_audit_a):
    """GET on audit complete returns 405."""
    url = reverse("assets:asset_compliance_audit_complete", kwargs={"pk": compliance_audit_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_compliance_view_audit_complete_foreign_tenant_404(client_a, compliance_audit_b):
    """Cross-tenant audit complete returns 404."""
    url = reverse("assets:asset_compliance_audit_complete", kwargs={"pk": compliance_audit_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


def test_compliance_view_audit_delete_scheduled_success(client_a, tenant_a, compliance_framework_a):
    """Scheduled audit deletes cleanly, creates AuditLog entry, and redirects to list."""
    today = timezone.now().date()
    audit = AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        framework=compliance_framework_a,
        title="Scheduled Audit to Delete",
        audit_type="internal",
        audit_date=today,
        status="scheduled",
    )
    url = reverse("assets:asset_compliance_audit_delete", kwargs={"pk": audit.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_audit_list")
    assert not AssetComplianceAudit.objects.filter(pk=audit.pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        target_object_id=str(audit.pk),
    ).exists()


def test_compliance_view_audit_delete_completed_guard(client_a, compliance_audit_a):
    """Completed audit cannot be deleted; redirects to detail with error message."""
    assert compliance_audit_a.status == "completed"
    url = reverse("assets:asset_compliance_audit_delete", kwargs={"pk": compliance_audit_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_audit_detail", kwargs={"pk": compliance_audit_a.pk})
    assert AssetComplianceAudit.objects.filter(pk=compliance_audit_a.pk).exists()

    msgs = _compliance_get_flash_messages(resp)
    assert any("cannot be deleted" in m for m in msgs)


def test_compliance_view_audit_delete_get_405(client_a, compliance_audit_a):
    """GET on audit delete returns 405."""
    url = reverse("assets:asset_compliance_audit_delete", kwargs={"pk": compliance_audit_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_compliance_view_audit_delete_member_forbidden(member_client, compliance_audit_a):
    """Non-admin member cannot delete audit; receives 403."""
    url = reverse("assets:asset_compliance_audit_delete", kwargs={"pk": compliance_audit_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_compliance_view_audit_delete_foreign_tenant_404(client_a, compliance_audit_b):
    """Cross-tenant audit delete returns 404."""
    url = reverse("assets:asset_compliance_audit_delete", kwargs={"pk": compliance_audit_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 3. Permit Views Tests
# ==============================================================================

def test_compliance_view_permit_list_success(client_a, permit_license_a):
    """Permit list view renders 200 with required context keys and metrics."""
    url = reverse("assets:asset_permit_license_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "permits" in resp.context
    assert permit_license_a in resp.context["permits"]
    assert "status_choices" in resp.context
    assert "type_choices" in resp.context
    assert "authority_list" in resp.context
    assert "total_permits" in resp.context
    assert "active_count" in resp.context
    assert "expiring_soon_count" in resp.context
    assert "expired_count" in resp.context
    assert resp.context["total_permits"] >= 1


def test_compliance_view_permit_list_tenant_isolation(client_a, client_b, permit_license_a, permit_license_b):
    """Client A sees only Tenant A permits; Client B sees only Tenant B permits."""
    url = reverse("assets:asset_permit_license_list")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    permits_a = list(resp_a.context["permits"])
    assert permit_license_a in permits_a
    assert permit_license_b not in permits_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    permits_b = list(resp_b.context["permits"])
    assert permit_license_b in permits_b
    assert permit_license_a not in permits_b


def test_compliance_view_permit_list_filters(client_a, permit_license_a, vendor_party_a):
    """Search, status, permit_type, and issuing authority filters filter accurately."""
    url = reverse("assets:asset_permit_license_list")

    # Search filter matching
    resp = client_a.get(f"{url}?q=BOILER")
    assert resp.status_code == 200
    assert permit_license_a in resp.context["permits"]

    # Search filter non-matching
    resp_empty = client_a.get(f"{url}?q=UNKNOWN_NONEXISTENT_XYZ")
    assert resp_empty.status_code == 200
    assert permit_license_a not in resp_empty.context["permits"]

    # Status filter
    resp_act = client_a.get(f"{url}?status=active")
    assert permit_license_a in resp_act.context["permits"]
    resp_exp = client_a.get(f"{url}?status=expired")
    assert permit_license_a not in resp_exp.context["permits"]

    # Type filter
    resp_pv = client_a.get(f"{url}?permit_type=pressure_vessel")
    assert permit_license_a in resp_pv.context["permits"]
    resp_env = client_a.get(f"{url}?permit_type=environmental_emissions")
    assert permit_license_a not in resp_env.context["permits"]

    # Authority filter
    resp_auth = client_a.get(f"{url}?authority={vendor_party_a.pk}")
    assert permit_license_a in resp_auth.context["permits"]
    resp_auth_junk = client_a.get(f"{url}?authority=999999")
    assert permit_license_a not in resp_auth_junk.context["permits"]


def test_compliance_view_permit_list_pagination(client_a, tenant_a, operational_asset_a):
    """Permit list handles pagination across 25+ records."""
    url = reverse("assets:asset_permit_license_list")
    today = timezone.now().date()
    for i in range(26):
        AssetPermitLicense.objects.create(
            tenant=tenant_a,
            asset=operational_asset_a,
            permit_name=f"Standard Operating Permit {i:02d}",
            permit_number=f"PERM-STD-{i:02d}",
            permit_type="operational_safety",
            issue_date=today,
            effective_date=today,
            expiration_date=today + timezone.timedelta(days=365),
            status="active",
        )

    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["permits"]) == 25
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(f"{url}?page=2")
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["permits"]) >= 1


def test_compliance_view_permit_detail_success(client_a, permit_license_a, compliance_incident_a):
    """Permit detail renders 200 with permit and linked incidents."""
    url = reverse("assets:asset_permit_license_detail", kwargs={"pk": permit_license_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["permit"] == permit_license_a
    assert compliance_incident_a in resp.context["incidents"]


def test_compliance_view_permit_detail_foreign_tenant_404(client_a, permit_license_b):
    """Cross-tenant permit detail returns 404."""
    url = reverse("assets:asset_permit_license_detail", kwargs={"pk": permit_license_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_compliance_view_permit_create_get(client_a, operational_asset_a):
    """GET create renders form with initial asset pre-filled if provided."""
    url = reverse("assets:asset_permit_license_create")
    resp = client_a.get(f"{url}?asset={operational_asset_a.pk}")
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].initial.get("asset") == operational_asset_a.pk


def test_compliance_view_permit_create_post_valid(client_a, tenant_a, operational_asset_a, vendor_party_a):
    """Valid POST creates permit, writes AuditLog, and redirects to detail."""
    url = reverse("assets:asset_permit_license_create")
    payload = _compliance_permit_payload(
        asset=operational_asset_a,
        issuing_authority=vendor_party_a,
        permit_number="EPA-AIR-2026-CREATE",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 302

    created = AssetPermitLicense.objects.get(permit_number="EPA-AIR-2026-CREATE", tenant=tenant_a)
    assert resp.url == reverse("assets:asset_permit_license_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.status == "active"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        target_object_id=str(created.pk),
    ).exists()


def test_compliance_view_permit_create_post_expiration_date_validation(client_a, operational_asset_a):
    """POST with expiration_date earlier than effective_date returns 200 with form error."""
    url = reverse("assets:asset_permit_license_create")
    today = timezone.now().date()
    payload = _compliance_permit_payload(
        asset=operational_asset_a,
        effective_date=today.isoformat(),
        expiration_date=(today - timezone.timedelta(days=1)).isoformat(),
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert "expiration_date" in resp.context["form"].errors


def test_compliance_view_permit_create_reject_foreign(client_a, operational_asset_b, vendor_party_b):
    """Cross-tenant asset and issuing authority are rejected by permit form."""
    url = reverse("assets:asset_permit_license_create")
    payload = _compliance_permit_payload(
        asset=operational_asset_b,
        issuing_authority=vendor_party_b,
        permit_number="CROSS-PERMIT-01",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert not AssetPermitLicense.objects.filter(permit_number="CROSS-PERMIT-01").exists()


def test_compliance_view_permit_edit_get(client_a, permit_license_a):
    """GET edit renders form populated with permit instance and is_edit=True."""
    url = reverse("assets:asset_permit_license_edit", kwargs={"pk": permit_license_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["permit"] == permit_license_a


def test_compliance_view_permit_edit_post_valid(client_a, tenant_a, permit_license_a, operational_asset_a):
    """Valid POST updates permit, logs AuditLog, and redirects to detail."""
    url = reverse("assets:asset_permit_license_edit", kwargs={"pk": permit_license_a.pk})
    payload = _compliance_permit_payload(
        asset=operational_asset_a,
        permit_name="High-Pressure Steam Boiler Operating Certificate - Amended",
        permit_number=permit_license_a.permit_number,
        renewal_fee="950.00",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_permit_license_detail", kwargs={"pk": permit_license_a.pk})

    permit_license_a.refresh_from_db()
    assert permit_license_a.permit_name == "High-Pressure Steam Boiler Operating Certificate - Amended"
    assert permit_license_a.renewal_fee == Decimal("950.00")

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target_object_id=str(permit_license_a.pk),
    ).exists()


def test_compliance_view_permit_edit_foreign_tenant_404(client_a, permit_license_b):
    """Cross-tenant permit edit returns 404."""
    url = reverse("assets:asset_permit_license_edit", kwargs={"pk": permit_license_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_compliance_view_permit_renew_success(client_a, tenant_a, permit_license_a):
    """POST renew transitions active permit to pending_renewal and creates AuditLog."""
    assert permit_license_a.status == "active"
    url = reverse("assets:asset_permit_license_renew", kwargs={"pk": permit_license_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_permit_license_detail", kwargs={"pk": permit_license_a.pk})

    permit_license_a.refresh_from_db()
    assert permit_license_a.status == "pending_renewal"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target_object_id=str(permit_license_a.pk),
    ).exists()


def test_compliance_view_permit_renew_status_guard(client_a, tenant_a, operational_asset_a):
    """Cannot renew revoked or suspended permit; flashes error and preserves status."""
    today = timezone.now().date()
    permit = AssetPermitLicense.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        permit_name="Revoked Chemical Discharge License",
        permit_number="REVOKED-LIC-01",
        permit_type="hazardous_materials",
        issue_date=today,
        effective_date=today,
        expiration_date=today + timezone.timedelta(days=100),
        status="revoked",
    )
    url = reverse("assets:asset_permit_license_renew", kwargs={"pk": permit.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    permit.refresh_from_db()
    assert permit.status == "revoked"

    msgs = _compliance_get_flash_messages(resp)
    assert any("cannot be renewed while revoked" in m.lower() for m in msgs)


def test_compliance_view_permit_renew_get_405(client_a, permit_license_a):
    """GET on permit renew returns 405."""
    url = reverse("assets:asset_permit_license_renew", kwargs={"pk": permit_license_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_compliance_view_permit_renew_foreign_tenant_404(client_a, permit_license_b):
    """Cross-tenant permit renew returns 404."""
    url = reverse("assets:asset_permit_license_renew", kwargs={"pk": permit_license_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


def test_compliance_view_permit_delete_success(client_a, tenant_a, operational_asset_a):
    """Permit delete deletes record, creates AuditLog entry, and redirects to list."""
    today = timezone.now().date()
    permit = AssetPermitLicense.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        permit_name="Temporary Noise Exemption Permit",
        permit_number="NOISE-TEMP-01",
        permit_type="operational_safety",
        issue_date=today,
        effective_date=today,
        expiration_date=today + timezone.timedelta(days=30),
        status="active",
    )
    url = reverse("assets:asset_permit_license_delete", kwargs={"pk": permit.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_permit_license_list")
    assert not AssetPermitLicense.objects.filter(pk=permit.pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        target_object_id=str(permit.pk),
    ).exists()


def test_compliance_view_permit_delete_get_405(client_a, permit_license_a):
    """GET on permit delete returns 405."""
    url = reverse("assets:asset_permit_license_delete", kwargs={"pk": permit_license_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_compliance_view_permit_delete_member_forbidden(member_client, permit_license_a):
    """Non-admin user cannot delete permit; receives 403."""
    url = reverse("assets:asset_permit_license_delete", kwargs={"pk": permit_license_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_compliance_view_permit_delete_foreign_tenant_404(client_a, permit_license_b):
    """Cross-tenant permit delete returns 404."""
    url = reverse("assets:asset_permit_license_delete", kwargs={"pk": permit_license_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 4. Incident Views Tests
# ==============================================================================

def test_compliance_view_incident_list_success(client_a, compliance_incident_a):
    """Incident list view renders 200 with required context keys and metrics."""
    url = reverse("assets:asset_compliance_incident_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "incidents" in resp.context
    assert compliance_incident_a in resp.context["incidents"]
    assert "status_choices" in resp.context
    assert "severity_choices" in resp.context
    assert "type_choices" in resp.context
    assert "agency_list" in resp.context
    assert "total_incidents" in resp.context
    assert "open_count" in resp.context
    assert "critical_severity_count" in resp.context
    assert "total_fines_assessed" in resp.context
    assert "total_fines_paid" in resp.context
    assert resp.context["total_incidents"] >= 1


def test_compliance_view_incident_list_tenant_isolation(client_a, client_b, compliance_incident_a, compliance_incident_b):
    """Client A sees only Tenant A incidents; Client B sees only Tenant B incidents."""
    url = reverse("assets:asset_compliance_incident_list")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    incidents_a = list(resp_a.context["incidents"])
    assert compliance_incident_a in incidents_a
    assert compliance_incident_b not in incidents_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    incidents_b = list(resp_b.context["incidents"])
    assert compliance_incident_b in incidents_b
    assert compliance_incident_a not in incidents_b


def test_compliance_view_incident_list_filters(client_a, compliance_incident_a, vendor_party_a):
    """Search, status, severity, incident_type, and agency filters operate accurately."""
    url = reverse("assets:asset_compliance_incident_list")

    # Search filter matching
    resp = client_a.get(f"{url}?q=NOX")
    assert resp.status_code == 200
    assert compliance_incident_a in resp.context["incidents"]

    # Search filter non-matching
    resp_empty = client_a.get(f"{url}?q=UNKNOWN_NONEXISTENT_XYZ")
    assert resp_empty.status_code == 200
    assert compliance_incident_a not in resp_empty.context["incidents"]

    # Status filter
    resp_res = client_a.get(f"{url}?status=resolved")
    assert compliance_incident_a in resp_res.context["incidents"]
    resp_open = client_a.get(f"{url}?status=open")
    assert compliance_incident_a not in resp_open.context["incidents"]

    # Severity filter
    resp_ser = client_a.get(f"{url}?severity=serious")
    assert compliance_incident_a in resp_ser.context["incidents"]
    resp_ots = client_a.get(f"{url}?severity=other_than_serious")
    assert compliance_incident_a not in resp_ots.context["incidents"]

    # Type filter
    resp_em = client_a.get(f"{url}?incident_type=emissions_exceedance")
    assert compliance_incident_a in resp_em.context["incidents"]
    resp_unp = client_a.get(f"{url}?incident_type=unpermitted_discharge")
    assert compliance_incident_a not in resp_unp.context["incidents"]

    # Agency filter
    resp_ag = client_a.get(f"{url}?agency={vendor_party_a.pk}")
    assert compliance_incident_a in resp_ag.context["incidents"]
    resp_ag_junk = client_a.get(f"{url}?agency=999999")
    assert compliance_incident_a not in resp_ag_junk.context["incidents"]


def test_compliance_view_incident_list_pagination(client_a, tenant_a, operational_asset_a):
    """Incident list handles pagination across 25+ records."""
    url = reverse("assets:asset_compliance_incident_list")
    today = timezone.now().date()
    now_dt = timezone.now()
    for i in range(26):
        AssetComplianceIncident.objects.create(
            tenant=tenant_a,
            asset=operational_asset_a,
            title=f"Bulk Incident Report {i:02d}",
            incident_date=now_dt,
            discovery_date=today,
            incident_type="equipment_safety_guard_bypass",
            severity="other_than_serious",
            status="open",
        )

    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["incidents"]) == 25
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(f"{url}?page=2")
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["incidents"]) >= 1


def test_compliance_view_incident_detail_success(client_a, compliance_incident_a):
    """Incident detail renders 200 with incident instance."""
    url = reverse("assets:asset_compliance_incident_detail", kwargs={"pk": compliance_incident_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["incident"] == compliance_incident_a


def test_compliance_view_incident_detail_foreign_tenant_404(client_a, compliance_incident_b):
    """Cross-tenant incident detail returns 404."""
    url = reverse("assets:asset_compliance_incident_detail", kwargs={"pk": compliance_incident_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_compliance_view_incident_create_get(client_a, operational_asset_a, permit_license_a, compliance_audit_a):
    """GET create renders form with initial asset/permit/audit pre-filled if provided."""
    url = reverse("assets:asset_compliance_incident_create")
    resp = client_a.get(f"{url}?asset={operational_asset_a.pk}&permit={permit_license_a.pk}&audit={compliance_audit_a.pk}")
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].initial.get("asset") == operational_asset_a.pk
    assert resp.context["form"].initial.get("permit") == permit_license_a.pk
    assert resp.context["form"].initial.get("audit") == compliance_audit_a.pk


def test_compliance_view_incident_create_post_valid(client_a, tenant_a, operational_asset_a, permit_license_a, compliance_audit_a, vendor_party_a, admin_user):
    """Valid POST creates incident, writes AuditLog, and redirects to detail."""
    url = reverse("assets:asset_compliance_incident_create")
    payload = _compliance_incident_payload(
        asset=operational_asset_a,
        permit=str(permit_license_a.pk),
        audit=str(compliance_audit_a.pk),
        enforcement_agency=str(vendor_party_a.pk),
        assigned_investigator=str(admin_user.pk),
        title="Hydraulic Coolant Line Rupture in Bay 3",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 302

    created = AssetComplianceIncident.objects.get(title="Hydraulic Coolant Line Rupture in Bay 3", tenant=tenant_a)
    assert resp.url == reverse("assets:asset_compliance_incident_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.status == "under_investigation"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        target_object_id=str(created.pk),
    ).exists()


def test_compliance_view_incident_create_post_fine_validation(client_a, operational_asset_a):
    """POST with fine_paid > fine_assessed returns 200 with form error."""
    url = reverse("assets:asset_compliance_incident_create")
    payload = _compliance_incident_payload(
        asset=operational_asset_a,
        fine_assessed="1000.00",
        fine_paid="1500.00",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert "fine_paid" in resp.context["form"].errors


def test_compliance_view_incident_create_post_resolved_status_forbidden(client_a, operational_asset_a):
    """Cannot set status='resolved' directly in form submission."""
    url = reverse("assets:asset_compliance_incident_create")
    payload = _compliance_incident_payload(
        asset=operational_asset_a,
        status="resolved",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert "status" in resp.context["form"].errors


def test_compliance_view_incident_create_reject_foreign(client_a, operational_asset_b, permit_license_b, compliance_audit_b, vendor_party_b, admin_b):
    """Cross-tenant asset, permit, audit, agency, and investigator are rejected."""
    url = reverse("assets:asset_compliance_incident_create")
    payload = _compliance_incident_payload(
        asset=operational_asset_b,
        permit=str(permit_license_b.pk),
        audit=str(compliance_audit_b.pk),
        enforcement_agency=str(vendor_party_b.pk),
        assigned_investigator=str(admin_b.pk),
        title="Cross Tenant Incident",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert not AssetComplianceIncident.objects.filter(title="Cross Tenant Incident").exists()


def test_compliance_view_incident_edit_get(client_a, tenant_a, operational_asset_a):
    """GET edit renders form populated with incident instance and is_edit=True."""
    today = timezone.now().date()
    now_dt = timezone.now()
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        title="Open Editable Incident",
        incident_date=now_dt,
        discovery_date=today,
        incident_type="equipment_safety_guard_bypass",
        severity="other_than_serious",
        status="open",
    )
    url = reverse("assets:asset_compliance_incident_edit", kwargs={"pk": incident.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["incident"] == incident


def test_compliance_view_incident_edit_settled_guard(client_a, tenant_a, operational_asset_a):
    """Settled closed incident with assessed fines cannot be edited; redirects to detail with error."""
    today = timezone.now().date()
    now_dt = timezone.now()
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        title="Settled EPA Incident",
        incident_date=now_dt,
        discovery_date=today,
        incident_type="emissions_exceedance",
        severity="serious",
        fine_assessed=Decimal("5000.00"),
        fine_paid=Decimal("5000.00"),
        status="closed",
    )
    url = reverse("assets:asset_compliance_incident_edit", kwargs={"pk": incident.pk})
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_incident_detail", kwargs={"pk": incident.pk})

    msgs = _compliance_get_flash_messages(resp)
    assert any("cannot be edited" in m for m in msgs)


def test_compliance_view_incident_edit_post_valid(client_a, tenant_a, operational_asset_a):
    """Valid POST updates editable incident, logs AuditLog, and redirects to detail."""
    today = timezone.now().date()
    now_dt = timezone.now()
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        title="Initial Investigation Incident",
        incident_date=now_dt,
        discovery_date=today,
        incident_type="unpermitted_discharge",
        severity="other_than_serious",
        status="open",
    )
    url = reverse("assets:asset_compliance_incident_edit", kwargs={"pk": incident.pk})
    payload = _compliance_incident_payload(
        asset=operational_asset_a,
        title="Amended Investigation Incident",
        severity="serious",
        status="under_investigation",
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_incident_detail", kwargs={"pk": incident.pk})

    incident.refresh_from_db()
    assert incident.title == "Amended Investigation Incident"
    assert incident.severity == "serious"
    assert incident.status == "under_investigation"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target_object_id=str(incident.pk),
    ).exists()


def test_compliance_view_incident_edit_foreign_tenant_404(client_a, compliance_incident_b):
    """Cross-tenant incident edit returns 404."""
    url = reverse("assets:asset_compliance_incident_edit", kwargs={"pk": compliance_incident_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_compliance_view_incident_resolve_success(client_a, tenant_a, operational_asset_a):
    """POST resolve transitions incident to resolved, sets actual_resolution_date, and writes AuditLog."""
    today = timezone.now().date()
    now_dt = timezone.now()
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        title="Incident Ready for Resolution",
        incident_date=now_dt,
        discovery_date=today,
        incident_type="unpermitted_discharge",
        severity="other_than_serious",
        status="capa_in_progress",
    )
    url = reverse("assets:asset_compliance_incident_resolve", kwargs={"pk": incident.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_incident_detail", kwargs={"pk": incident.pk})

    incident.refresh_from_db()
    assert incident.status == "resolved"
    assert incident.actual_resolution_date == timezone.now().date()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target_object_id=str(incident.pk),
    ).exists()


def test_compliance_view_incident_resolve_status_guard(client_a, tenant_a, operational_asset_a):
    """Resolving an already closed incident flashes warning and does not alter status."""
    today = timezone.now().date()
    now_dt = timezone.now()
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        title="Closed Incident Guard",
        incident_date=now_dt,
        discovery_date=today,
        incident_type="unpermitted_discharge",
        severity="other_than_serious",
        status="closed",
    )
    url = reverse("assets:asset_compliance_incident_resolve", kwargs={"pk": incident.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    incident.refresh_from_db()
    assert incident.status == "closed"

    msgs = _compliance_get_flash_messages(resp)
    assert any("cannot be marked as resolved" in m for m in msgs)


def test_compliance_view_incident_resolve_get_405(client_a, compliance_incident_a):
    """GET on incident resolve returns 405."""
    url = reverse("assets:asset_compliance_incident_resolve", kwargs={"pk": compliance_incident_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_compliance_view_incident_resolve_foreign_tenant_404(client_a, compliance_incident_b):
    """Cross-tenant incident resolve returns 404."""
    url = reverse("assets:asset_compliance_incident_resolve", kwargs={"pk": compliance_incident_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


def test_compliance_view_incident_close_success(client_a, compliance_incident_a, tenant_a):
    """POST close on resolved incident transitions to closed and writes AuditLog."""
    assert compliance_incident_a.status == "resolved"
    url = reverse("assets:asset_compliance_incident_close", kwargs={"pk": compliance_incident_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_incident_detail", kwargs={"pk": compliance_incident_a.pk})

    compliance_incident_a.refresh_from_db()
    assert compliance_incident_a.status == "closed"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target_object_id=str(compliance_incident_a.pk),
    ).exists()


def test_compliance_view_incident_close_unresolved_guard(client_a, tenant_a, operational_asset_a):
    """Closing an unresolved open incident flashes warning that incident must be resolved first."""
    today = timezone.now().date()
    now_dt = timezone.now()
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        title="Unresolved Open Incident",
        incident_date=now_dt,
        discovery_date=today,
        incident_type="unpermitted_discharge",
        severity="other_than_serious",
        status="open",
    )
    url = reverse("assets:asset_compliance_incident_close", kwargs={"pk": incident.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    incident.refresh_from_db()
    assert incident.status == "open"

    msgs = _compliance_get_flash_messages(resp)
    assert any("must be resolved before closing" in m for m in msgs)


def test_compliance_view_incident_close_get_405(client_a, compliance_incident_a):
    """GET on incident close returns 405."""
    url = reverse("assets:asset_compliance_incident_close", kwargs={"pk": compliance_incident_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_compliance_view_incident_close_foreign_tenant_404(client_a, compliance_incident_b):
    """Cross-tenant incident close returns 404."""
    url = reverse("assets:asset_compliance_incident_close", kwargs={"pk": compliance_incident_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


def test_compliance_view_incident_delete_open_success(client_a, tenant_a, operational_asset_a):
    """Open incident deletes cleanly, writes AuditLog, and redirects to list."""
    today = timezone.now().date()
    now_dt = timezone.now()
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        title="Disposable Open Incident",
        incident_date=now_dt,
        discovery_date=today,
        incident_type="equipment_safety_guard_bypass",
        severity="other_than_serious",
        status="open",
    )
    url = reverse("assets:asset_compliance_incident_delete", kwargs={"pk": incident.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_incident_list")
    assert not AssetComplianceIncident.objects.filter(pk=incident.pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        target_object_id=str(incident.pk),
    ).exists()


def test_compliance_view_incident_delete_settled_guard(client_a, tenant_a, operational_asset_a):
    """Settled closed incident with fines cannot be deleted; flashes error message."""
    today = timezone.now().date()
    now_dt = timezone.now()
    incident = AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        title="Settled Locked Incident",
        incident_date=now_dt,
        discovery_date=today,
        incident_type="emissions_exceedance",
        severity="serious",
        fine_assessed=Decimal("7500.00"),
        fine_paid=Decimal("7500.00"),
        status="closed",
    )
    url = reverse("assets:asset_compliance_incident_delete", kwargs={"pk": incident.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_compliance_incident_detail", kwargs={"pk": incident.pk})
    assert AssetComplianceIncident.objects.filter(pk=incident.pk).exists()

    msgs = _compliance_get_flash_messages(resp)
    assert any("cannot be deleted" in m for m in msgs)


def test_compliance_view_incident_delete_get_405(client_a, compliance_incident_a):
    """GET on incident delete returns 405."""
    url = reverse("assets:asset_compliance_incident_delete", kwargs={"pk": compliance_incident_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_compliance_view_incident_delete_member_forbidden(member_client, compliance_incident_a):
    """Non-admin user cannot delete incident; receives 403."""
    url = reverse("assets:asset_compliance_incident_delete", kwargs={"pk": compliance_incident_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_compliance_view_incident_delete_foreign_tenant_404(client_a, compliance_incident_b):
    """Cross-tenant incident delete returns 404."""
    url = reverse("assets:asset_compliance_incident_delete", kwargs={"pk": compliance_incident_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 5. Security & Unauthenticated Access Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name,uses_pk",
    [
        ("assets:asset_compliance_framework_list", False),
        ("assets:asset_compliance_framework_create", False),
        ("assets:asset_compliance_framework_detail", True),
        ("assets:asset_compliance_framework_edit", True),
        ("assets:asset_compliance_audit_list", False),
        ("assets:asset_compliance_audit_create", False),
        ("assets:asset_compliance_audit_detail", True),
        ("assets:asset_compliance_audit_edit", True),
        ("assets:asset_permit_license_list", False),
        ("assets:asset_permit_license_create", False),
        ("assets:asset_permit_license_detail", True),
        ("assets:asset_permit_license_edit", True),
        ("assets:asset_compliance_incident_list", False),
        ("assets:asset_compliance_incident_create", False),
        ("assets:asset_compliance_incident_detail", True),
        ("assets:asset_compliance_incident_edit", True),
    ],
)
def test_compliance_view_unauthenticated_redirects(url_name, uses_pk, compliance_framework_a, compliance_audit_a, permit_license_a, compliance_incident_a):
    """Unauthenticated access redirects to login."""
    anon_client = Client()
    if uses_pk:
        if "framework" in url_name:
            target_pk = compliance_framework_a.pk
        elif "audit" in url_name:
            target_pk = compliance_audit_a.pk
        elif "permit" in url_name:
            target_pk = permit_license_a.pk
        else:
            target_pk = compliance_incident_a.pk
        url = reverse(url_name, kwargs={"pk": target_pk})
    else:
        url = reverse(url_name)

    resp = anon_client.get(url)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url
