"""Security, multi-tenant isolation (IDOR), and authorization tests for Sub-module 12.20 Data Integrity & Electronic Records.

Covers:
1. Unauthenticated Protection:
   - GET on dashboard and all 4 model list, create, detail, edit views redirect to login (HTTP 302).
   - POST on create, edit, delete mutating views redirects to login (HTTP 302).
2. Cross-Tenant IDOR Attack Defense:
   - Tenant A user accessing Tenant B's policy detail, edit, delete returns HTTP 404.
   - Tenant A user accessing Tenant B's assessment detail, edit, delete returns HTTP 404.
   - Tenant A user accessing Tenant B's audit review detail, edit, delete returns HTTP 404.
   - Tenant A user accessing Tenant B's change control detail, edit, delete returns HTTP 404.
   - Symmetric IDOR: Tenant B user accessing Tenant A's objects returns HTTP 404.
   - Tenant A user cannot view Tenant B's records in list queries or dashboard.
3. Cross-Tenant Foreign Key Tampering:
   - Tenant A user submitting form containing Tenant B's foreign keys is rejected via reject_foreign.
   - Direct cleaned_data verification and bound form validation across all 4 models.
4. Authorization & Method Security:
   - GET request to any of the 4 delete endpoints returns HTTP 405 Method Not Allowed (@require_POST).
   - Non-admin user attempting to POST delete is rejected with HTTP 403 Forbidden (@tenant_admin_required).
5. Legal Hold & Regulatory Protection:
   - Policy with legal_hold=True cannot be deleted even by tenant admin; deletion is blocked and policy remains in DB.
   - Policy with legal_hold=False can be deleted by tenant admin.
6. Audit Logging Verification:
   - Successful create, update, delete operations on all 4 models generate AuditLog entries with matching actor, tenant, action verb, and content_type.
"""
from datetime import timedelta
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.core.models import AuditLog, OrgUnit
from apps.quality.forms._common import reject_foreign
from apps.quality.forms.DataIntegrity.AuditTrailReviews import AuditTrailReviewForm
from apps.quality.forms.DataIntegrity.DataIntegrityAssessments import DataIntegrityAssessmentForm
from apps.quality.forms.DataIntegrity.ElectronicRecordPolicies import ElectronicRecordPolicyForm
from apps.quality.forms.DataIntegrity.SystemChangeControls import SystemChangeControlForm
from apps.quality.models import (
    ElectronicRecordPolicy,
    DataIntegrityAssessment,
    AuditTrailReview,
    SystemChangeControl,
)


# ==============================================================================
# Module Helpers (Prefixed with _dataintegrity_)
# ==============================================================================

def _dataintegrity_verify_audit_log(tenant, model_cls, object_id, action, actor=None):
    """Verify that an AuditLog entry exists for the given model, object_id, action, and optional actor."""
    ct = ContentType.objects.get_for_model(model_cls)
    qs = AuditLog.objects.filter(
        tenant=tenant,
        content_type=ct,
        object_id=str(object_id),
        action=action,
    )
    if actor:
        qs = qs.filter(user=actor)
    return qs.exists()


def _dataintegrity_policy_payload(system=None, governing_sop=None, system_owner=None, qa_approver=None, **overrides):
    """Generate valid POST payload for ElectronicRecordPolicyForm."""
    data = {
        "title": "Security Test Policy Title",
        "record_type_name": "Security Test Record Stream",
        "record_category": "production_batch",
        "target_model_name": "BatchRecord",
        "system": system.pk if system else "",
        "governing_sop": governing_sop.pk if governing_sop else "",
        "is_part_11_regulated": True,
        "is_annex_11_regulated": True,
        "signature_requirement": "dual_peer_review",
        "reauthentication_required": True,
        "dual_signature_required": False,
        "audit_trail_mandatory": True,
        "retention_period_years": 7,
        "storage_format": "database_relational",
        "backup_frequency": "daily_snapshot",
        "legal_hold": False,
        "status": "active",
        "system_owner": system_owner.pk if system_owner else "",
        "qa_approver": qa_approver.pk if qa_approver else "",
        "approval_date": "2026-11-22",
        "description": "Electronic records security test governance policy.",
    }
    data.update(overrides)
    return data


def _dataintegrity_assessment_payload(system=None, org_unit=None, lead_assessor=None, qa_reviewer=None, **overrides):
    """Generate valid POST payload for DataIntegrityAssessmentForm."""
    data = {
        "title": "Security ALCOA+ Audit Plan",
        "assessment_scope": "Packaging Vision System",
        "system": system.pk if system else "",
        "org_unit": org_unit.pk if org_unit else "",
        "lead_assessor": lead_assessor.pk if lead_assessor else "",
        "qa_reviewer": qa_reviewer.pk if qa_reviewer else "",
        "assessment_date": "2026-11-22",
        "next_review_due": "2027-11-22",
        "attributable_rating": "fully_compliant",
        "legible_rating": "fully_compliant",
        "contemporaneous_rating": "fully_compliant",
        "original_rating": "fully_compliant",
        "accurate_rating": "fully_compliant",
        "complete_rating": "fully_compliant",
        "consistent_rating": "fully_compliant",
        "enduring_rating": "fully_compliant",
        "available_rating": "fully_compliant",
        "overall_risk_level": "low",
        "vulnerabilities_summary": "Zero critical security vulnerabilities detected.",
        "remediation_plan": "Scheduled routine verification cycle.",
        "status": "draft",
        "comments": "Baseline security assessment.",
    }
    data.update(overrides)
    return data


def _dataintegrity_audit_review_payload(system=None, reviewer=None, qa_approver=None, **overrides):
    """Generate valid POST payload for AuditTrailReviewForm."""
    data = {
        "title": "Security Audit Trail Review Cycle",
        "system": system.pk if system else "",
        "review_type": "periodic_system",
        "audit_source": "database_audit_log",
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "reviewer": reviewer.pk if reviewer else "",
        "qa_approver": qa_approver.pk if qa_approver else "",
        "review_date": "2026-11-01",
        "records_sampled_count": 250,
        "anomalies_detected_count": 0,
        "anomaly_severity": "none",
        "findings_summary": "250 transactions checked. Zero anomalies found.",
        "disposition": "approved_clean",
        "status": "scheduled",
        "qa_comments": "Audit trail verified intact.",
    }
    data.update(overrides)
    return data


def _dataintegrity_change_control_payload(system=None, requestor=None, system_owner=None, qa_lead=None, org_unit=None, **overrides):
    """Generate valid POST payload for SystemChangeControlForm."""
    data = {
        "title": "Security Firmware Patch Upgrade",
        "system": system.pk if system else "",
        "change_type": "software_patch",
        "change_priority": "routine",
        "gxp_impact": "direct_gxp",
        "requestor": requestor.pk if requestor else "",
        "system_owner": system_owner.pk if system_owner else "",
        "qa_lead": qa_lead.pk if qa_lead else "",
        "org_unit": org_unit.pk if org_unit else "",
        "description": "Apply security firmware patch.",
        "business_justification": "Mitigate network CVE.",
        "data_integrity_risk": "Low risk; zero schema changes.",
        "validation_deliverables": "IQ test script.",
        "rollback_plan": "Revert firmware snapshot.",
        "target_date": "2026-12-01",
        "post_review_due_date": "2027-03-01",
        "status": "draft",
        "testing_successful": False,
        "data_backup_verified": False,
        "ccb_approved": False,
        "closure_summary": "",
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. Unauthenticated Protection Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_unauthenticated_get_protection(
    client,
    electronic_record_policy_a,
    data_integrity_assessment_a,
    audit_trail_review_a,
    system_change_control_a,
):
    """Verify unauthenticated GET requests to dashboard, list, create, detail, edit endpoints redirect to login (HTTP 302)."""
    urls = [
        reverse("quality:data_integrity_dashboard"),
        reverse("quality:electronic_record_policy_list"),
        reverse("quality:electronic_record_policy_create"),
        reverse("quality:electronic_record_policy_detail", kwargs={"pk": electronic_record_policy_a.pk}),
        reverse("quality:electronic_record_policy_edit", kwargs={"pk": electronic_record_policy_a.pk}),
        reverse("quality:data_integrity_assessment_list"),
        reverse("quality:data_integrity_assessment_create"),
        reverse("quality:data_integrity_assessment_detail", kwargs={"pk": data_integrity_assessment_a.pk}),
        reverse("quality:data_integrity_assessment_edit", kwargs={"pk": data_integrity_assessment_a.pk}),
        reverse("quality:audit_trail_review_list"),
        reverse("quality:audit_trail_review_create"),
        reverse("quality:audit_trail_review_detail", kwargs={"pk": audit_trail_review_a.pk}),
        reverse("quality:audit_trail_review_edit", kwargs={"pk": audit_trail_review_a.pk}),
        reverse("quality:system_change_control_list"),
        reverse("quality:system_change_control_create"),
        reverse("quality:system_change_control_detail", kwargs={"pk": system_change_control_a.pk}),
        reverse("quality:system_change_control_edit", kwargs={"pk": system_change_control_a.pk}),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "login" in resp.url


@pytest.mark.django_db
def test_dataintegrity_unauthenticated_post_protection(
    client,
    electronic_record_policy_a,
    data_integrity_assessment_a,
    audit_trail_review_a,
    system_change_control_a,
):
    """Verify unauthenticated POST requests to mutating endpoints redirect to login (HTTP 302)."""
    post_targets = [
        reverse("quality:electronic_record_policy_create"),
        reverse("quality:electronic_record_policy_edit", kwargs={"pk": electronic_record_policy_a.pk}),
        reverse("quality:electronic_record_policy_delete", kwargs={"pk": electronic_record_policy_a.pk}),
        reverse("quality:data_integrity_assessment_create"),
        reverse("quality:data_integrity_assessment_edit", kwargs={"pk": data_integrity_assessment_a.pk}),
        reverse("quality:data_integrity_assessment_delete", kwargs={"pk": data_integrity_assessment_a.pk}),
        reverse("quality:audit_trail_review_create"),
        reverse("quality:audit_trail_review_edit", kwargs={"pk": audit_trail_review_a.pk}),
        reverse("quality:audit_trail_review_delete", kwargs={"pk": audit_trail_review_a.pk}),
        reverse("quality:system_change_control_create"),
        reverse("quality:system_change_control_edit", kwargs={"pk": system_change_control_a.pk}),
        reverse("quality:system_change_control_delete", kwargs={"pk": system_change_control_a.pk}),
    ]
    for url in post_targets:
        resp = client.post(url, {})
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "login" in resp.url


# ==============================================================================
# 2. Cross-Tenant IDOR Attack Defense Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_idor_policy_access_denied(
    client,
    admin_user,
    admin_b,
    electronic_record_policy_a,
    electronic_record_policy_b,
):
    """Verify cross-tenant IDOR access to ElectronicRecordPolicy returns HTTP 404 in both directions."""
    # Tenant A user accessing Tenant B policy
    client.force_login(admin_user)
    detail_b = reverse("quality:electronic_record_policy_detail", kwargs={"pk": electronic_record_policy_b.pk})
    edit_b = reverse("quality:electronic_record_policy_edit", kwargs={"pk": electronic_record_policy_b.pk})
    delete_b = reverse("quality:electronic_record_policy_delete", kwargs={"pk": electronic_record_policy_b.pk})

    assert client.get(detail_b).status_code == 404
    assert client.get(edit_b).status_code == 404
    assert client.post(edit_b, {"title": "IDOR Tamper Attack"}).status_code == 404
    assert client.post(delete_b).status_code == 404

    # Symmetric: Tenant B user accessing Tenant A policy
    client.force_login(admin_b)
    detail_a = reverse("quality:electronic_record_policy_detail", kwargs={"pk": electronic_record_policy_a.pk})
    edit_a = reverse("quality:electronic_record_policy_edit", kwargs={"pk": electronic_record_policy_a.pk})
    delete_a = reverse("quality:electronic_record_policy_delete", kwargs={"pk": electronic_record_policy_a.pk})

    assert client.get(detail_a).status_code == 404
    assert client.get(edit_a).status_code == 404
    assert client.post(edit_a, {"title": "IDOR Tamper Attack"}).status_code == 404
    assert client.post(delete_a).status_code == 404


@pytest.mark.django_db
def test_dataintegrity_idor_assessment_access_denied(
    client,
    admin_user,
    admin_b,
    data_integrity_assessment_a,
    data_integrity_assessment_b,
):
    """Verify cross-tenant IDOR access to DataIntegrityAssessment returns HTTP 404 in both directions."""
    # Tenant A user accessing Tenant B assessment
    client.force_login(admin_user)
    detail_b = reverse("quality:data_integrity_assessment_detail", kwargs={"pk": data_integrity_assessment_b.pk})
    edit_b = reverse("quality:data_integrity_assessment_edit", kwargs={"pk": data_integrity_assessment_b.pk})
    delete_b = reverse("quality:data_integrity_assessment_delete", kwargs={"pk": data_integrity_assessment_b.pk})

    assert client.get(detail_b).status_code == 404
    assert client.get(edit_b).status_code == 404
    assert client.post(edit_b, {"title": "IDOR Tamper Attack"}).status_code == 404
    assert client.post(delete_b).status_code == 404

    # Symmetric: Tenant B user accessing Tenant A assessment
    client.force_login(admin_b)
    detail_a = reverse("quality:data_integrity_assessment_detail", kwargs={"pk": data_integrity_assessment_a.pk})
    edit_a = reverse("quality:data_integrity_assessment_edit", kwargs={"pk": data_integrity_assessment_a.pk})
    delete_a = reverse("quality:data_integrity_assessment_delete", kwargs={"pk": data_integrity_assessment_a.pk})

    assert client.get(detail_a).status_code == 404
    assert client.get(edit_a).status_code == 404
    assert client.post(edit_a, {"title": "IDOR Tamper Attack"}).status_code == 404
    assert client.post(delete_a).status_code == 404


@pytest.mark.django_db
def test_dataintegrity_idor_audit_review_access_denied(
    client,
    admin_user,
    admin_b,
    audit_trail_review_a,
    audit_trail_review_b,
):
    """Verify cross-tenant IDOR access to AuditTrailReview returns HTTP 404 in both directions."""
    # Tenant A user accessing Tenant B review
    client.force_login(admin_user)
    detail_b = reverse("quality:audit_trail_review_detail", kwargs={"pk": audit_trail_review_b.pk})
    edit_b = reverse("quality:audit_trail_review_edit", kwargs={"pk": audit_trail_review_b.pk})
    delete_b = reverse("quality:audit_trail_review_delete", kwargs={"pk": audit_trail_review_b.pk})

    assert client.get(detail_b).status_code == 404
    assert client.get(edit_b).status_code == 404
    assert client.post(edit_b, {"title": "IDOR Tamper Attack"}).status_code == 404
    assert client.post(delete_b).status_code == 404

    # Symmetric: Tenant B user accessing Tenant A review
    client.force_login(admin_b)
    detail_a = reverse("quality:audit_trail_review_detail", kwargs={"pk": audit_trail_review_a.pk})
    edit_a = reverse("quality:audit_trail_review_edit", kwargs={"pk": audit_trail_review_a.pk})
    delete_a = reverse("quality:audit_trail_review_delete", kwargs={"pk": audit_trail_review_a.pk})

    assert client.get(detail_a).status_code == 404
    assert client.get(edit_a).status_code == 404
    assert client.post(edit_a, {"title": "IDOR Tamper Attack"}).status_code == 404
    assert client.post(delete_a).status_code == 404


@pytest.mark.django_db
def test_dataintegrity_idor_change_control_access_denied(
    client,
    admin_user,
    admin_b,
    system_change_control_a,
    system_change_control_b,
):
    """Verify cross-tenant IDOR access to SystemChangeControl returns HTTP 404 in both directions."""
    # Tenant A user accessing Tenant B change control
    client.force_login(admin_user)
    detail_b = reverse("quality:system_change_control_detail", kwargs={"pk": system_change_control_b.pk})
    edit_b = reverse("quality:system_change_control_edit", kwargs={"pk": system_change_control_b.pk})
    delete_b = reverse("quality:system_change_control_delete", kwargs={"pk": system_change_control_b.pk})

    assert client.get(detail_b).status_code == 404
    assert client.get(edit_b).status_code == 404
    assert client.post(edit_b, {"title": "IDOR Tamper Attack"}).status_code == 404
    assert client.post(delete_b).status_code == 404

    # Symmetric: Tenant B user accessing Tenant A change control
    client.force_login(admin_b)
    detail_a = reverse("quality:system_change_control_detail", kwargs={"pk": system_change_control_a.pk})
    edit_a = reverse("quality:system_change_control_edit", kwargs={"pk": system_change_control_a.pk})
    delete_a = reverse("quality:system_change_control_delete", kwargs={"pk": system_change_control_a.pk})

    assert client.get(detail_a).status_code == 404
    assert client.get(edit_a).status_code == 404
    assert client.post(edit_a, {"title": "IDOR Tamper Attack"}).status_code == 404
    assert client.post(delete_a).status_code == 404


@pytest.mark.django_db
def test_dataintegrity_list_queries_tenant_isolation(
    client,
    admin_user,
    admin_b,
    electronic_record_policy_a,
    electronic_record_policy_b,
    data_integrity_assessment_a,
    data_integrity_assessment_b,
    audit_trail_review_a,
    audit_trail_review_b,
    system_change_control_a,
    system_change_control_b,
):
    """Verify Tenant A list queries never leak Tenant B records, and vice versa."""
    # Tenant A view
    client.force_login(admin_user)

    # 1. Policies
    resp_pol = client.get(reverse("quality:electronic_record_policy_list"))
    assert resp_pol.status_code == 200
    assert electronic_record_policy_a in resp_pol.context["policies"]
    assert electronic_record_policy_b not in resp_pol.context["policies"]
    assert escape(electronic_record_policy_a.title).encode() in resp_pol.content
    assert escape(electronic_record_policy_b.title).encode() not in resp_pol.content

    # 2. Assessments
    resp_ass = client.get(reverse("quality:data_integrity_assessment_list"))
    assert resp_ass.status_code == 200
    assert data_integrity_assessment_a in resp_ass.context["assessments"]
    assert data_integrity_assessment_b not in resp_ass.context["assessments"]
    assert escape(data_integrity_assessment_a.title).encode() in resp_ass.content
    assert escape(data_integrity_assessment_b.title).encode() not in resp_ass.content

    # 3. Audit Reviews
    resp_rev = client.get(reverse("quality:audit_trail_review_list"))
    assert resp_rev.status_code == 200
    assert audit_trail_review_a in resp_rev.context["reviews"]
    assert audit_trail_review_b not in resp_rev.context["reviews"]
    assert escape(audit_trail_review_a.title).encode() in resp_rev.content
    assert escape(audit_trail_review_b.title).encode() not in resp_rev.content

    # 4. Change Controls
    resp_cc = client.get(reverse("quality:system_change_control_list"))
    assert resp_cc.status_code == 200
    assert system_change_control_a in resp_cc.context["changes"]
    assert system_change_control_b not in resp_cc.context["changes"]
    assert escape(system_change_control_a.title).encode() in resp_cc.content
    assert escape(system_change_control_b.title).encode() not in resp_cc.content

    # Symmetric: Tenant B view
    client.force_login(admin_b)

    resp_pol_b = client.get(reverse("quality:electronic_record_policy_list"))
    assert electronic_record_policy_b in resp_pol_b.context["policies"]
    assert electronic_record_policy_a not in resp_pol_b.context["policies"]
    assert escape(electronic_record_policy_b.title).encode() in resp_pol_b.content
    assert escape(electronic_record_policy_a.title).encode() not in resp_pol_b.content

    resp_ass_b = client.get(reverse("quality:data_integrity_assessment_list"))
    assert data_integrity_assessment_b in resp_ass_b.context["assessments"]
    assert data_integrity_assessment_a not in resp_ass_b.context["assessments"]
    assert escape(data_integrity_assessment_b.title).encode() in resp_ass_b.content
    assert escape(data_integrity_assessment_a.title).encode() not in resp_ass_b.content

    resp_rev_b = client.get(reverse("quality:audit_trail_review_list"))
    assert audit_trail_review_b in resp_rev_b.context["reviews"]
    assert audit_trail_review_a not in resp_rev_b.context["reviews"]
    assert escape(audit_trail_review_b.title).encode() in resp_rev_b.content
    assert escape(audit_trail_review_a.title).encode() not in resp_rev_b.content

    resp_cc_b = client.get(reverse("quality:system_change_control_list"))
    assert system_change_control_b in resp_cc_b.context["changes"]
    assert system_change_control_a not in resp_cc_b.context["changes"]
    assert escape(system_change_control_b.title).encode() in resp_cc_b.content
    assert escape(system_change_control_a.title).encode() not in resp_cc_b.content


@pytest.mark.django_db
def test_dataintegrity_dashboard_tenant_isolation(
    client,
    admin_user,
    electronic_record_policy_a,
    electronic_record_policy_b,
    data_integrity_assessment_a,
    data_integrity_assessment_b,
    audit_trail_review_a,
    audit_trail_review_b,
    system_change_control_a,
    system_change_control_b,
):
    """Verify data_integrity_dashboard aggregates only Tenant A's objects and omits Tenant B's."""
    client.force_login(admin_user)
    resp = client.get(reverse("quality:data_integrity_dashboard"))
    assert resp.status_code == 200

    # Ensure context contains only Tenant A objects
    assert electronic_record_policy_a in resp.context["recent_policies"]
    assert electronic_record_policy_b not in resp.context["recent_policies"]
    assert data_integrity_assessment_a in resp.context["recent_assessments"]
    assert data_integrity_assessment_b not in resp.context["recent_assessments"]
    assert audit_trail_review_a in resp.context["recent_reviews"]
    assert audit_trail_review_b not in resp.context["recent_reviews"]
    assert system_change_control_a in resp.context["recent_changes"]
    assert system_change_control_b not in resp.context["recent_changes"]

    # Ensure Tenant A items are present in rendered tables
    assert escape(electronic_record_policy_a.record_type_name).encode() in resp.content
    assert escape(data_integrity_assessment_a.assessment_scope).encode() in resp.content
    assert escape(audit_trail_review_a.title).encode() in resp.content
    assert escape(system_change_control_a.title).encode() in resp.content

    # Ensure Tenant B items are strictly absent
    assert escape(electronic_record_policy_b.record_type_name).encode() not in resp.content
    assert escape(data_integrity_assessment_b.assessment_scope).encode() not in resp.content
    assert escape(audit_trail_review_b.title).encode() not in resp.content
    assert escape(system_change_control_b.title).encode() not in resp.content


# ==============================================================================
# 3. Cross-Tenant Foreign Key Tampering Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_fk_tampering_policy_form(
    tenant_a,
    tenant_b,
    admin_b,
    computer_system_validation_b,
    doc_b,
):
    """Verify ElectronicRecordPolicyForm rejects foreign system, governing_sop, system_owner, and qa_approver."""
    # 1. Direct reject_foreign check on cleaned_data
    form_direct = ElectronicRecordPolicyForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct._errors = {}
    form_direct.cleaned_data = {
        "system": computer_system_validation_b,
        "governing_sop": doc_b,
        "system_owner": admin_b,
        "qa_approver": admin_b,
    }
    reject_foreign(form_direct, form_direct.cleaned_data, ["system", "governing_sop", "system_owner", "qa_approver"])
    for field in ["system", "governing_sop", "system_owner", "qa_approver"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field]

    # 2. Bound form submission with foreign PKs is rejected
    tampered_data = _dataintegrity_policy_payload(
        system=computer_system_validation_b,
        governing_sop=doc_b,
        system_owner=admin_b,
        qa_approver=admin_b,
    )
    bound_form = ElectronicRecordPolicyForm(data=tampered_data, tenant=tenant_a)
    assert not bound_form.is_valid()
    for field in ["system", "governing_sop", "system_owner", "qa_approver"]:
        assert field in bound_form.errors


@pytest.mark.django_db
def test_dataintegrity_fk_tampering_assessment_form(
    tenant_a,
    tenant_b,
    admin_b,
    computer_system_validation_b,
    quality_department_b,
    capa_investigation_b,
    ncr_b,
):
    """Verify DataIntegrityAssessmentForm rejects foreign system, org_unit, lead_assessor, qa_reviewer, linked_capa, and linked_ncr."""
    # 1. Direct reject_foreign check on cleaned_data
    form_direct = DataIntegrityAssessmentForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct._errors = {}
    form_direct.cleaned_data = {
        "system": computer_system_validation_b,
        "org_unit": quality_department_b,
        "lead_assessor": admin_b,
        "qa_reviewer": admin_b,
        "linked_capa": capa_investigation_b,
        "linked_ncr": ncr_b,
    }
    reject_foreign(
        form_direct,
        form_direct.cleaned_data,
        ["system", "org_unit", "lead_assessor", "qa_reviewer", "linked_capa", "linked_ncr"],
    )
    for field in ["system", "org_unit", "lead_assessor", "qa_reviewer", "linked_capa", "linked_ncr"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field]

    # 2. Bound form submission with foreign PKs is rejected
    tampered_data = _dataintegrity_assessment_payload(
        system=computer_system_validation_b,
        org_unit=quality_department_b,
        lead_assessor=admin_b,
        qa_reviewer=admin_b,
        linked_capa=capa_investigation_b.pk,
        linked_ncr=ncr_b.pk,
    )
    bound_form = DataIntegrityAssessmentForm(data=tampered_data, tenant=tenant_a)
    assert not bound_form.is_valid()
    for field in ["system", "org_unit", "lead_assessor", "qa_reviewer", "linked_capa", "linked_ncr"]:
        assert field in bound_form.errors


@pytest.mark.django_db
def test_dataintegrity_fk_tampering_audit_review_form(
    tenant_a,
    tenant_b,
    admin_b,
    computer_system_validation_b,
    ncr_b,
    capa_investigation_b,
):
    """Verify AuditTrailReviewForm rejects foreign system, reviewer, qa_approver, linked_ncr, and linked_capa."""
    # 1. Direct reject_foreign check on cleaned_data
    form_direct = AuditTrailReviewForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct._errors = {}
    form_direct.cleaned_data = {
        "system": computer_system_validation_b,
        "reviewer": admin_b,
        "qa_approver": admin_b,
        "linked_ncr": ncr_b,
        "linked_capa": capa_investigation_b,
    }
    reject_foreign(
        form_direct,
        form_direct.cleaned_data,
        ["system", "reviewer", "qa_approver", "linked_ncr", "linked_capa"],
    )
    for field in ["system", "reviewer", "qa_approver", "linked_ncr", "linked_capa"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field]

    # 2. Bound form submission with foreign PKs is rejected
    tampered_data = _dataintegrity_audit_review_payload(
        system=computer_system_validation_b,
        reviewer=admin_b,
        qa_approver=admin_b,
        linked_ncr=ncr_b.pk,
        linked_capa=capa_investigation_b.pk,
    )
    bound_form = AuditTrailReviewForm(data=tampered_data, tenant=tenant_a)
    assert not bound_form.is_valid()
    for field in ["system", "reviewer", "qa_approver", "linked_ncr", "linked_capa"]:
        assert field in bound_form.errors


@pytest.mark.django_db
def test_dataintegrity_fk_tampering_change_control_form(
    tenant_a,
    tenant_b,
    admin_b,
    computer_system_validation_b,
    quality_department_b,
):
    """Verify SystemChangeControlForm rejects foreign system, requestor, system_owner, qa_lead, and org_unit."""
    # 1. Direct reject_foreign check on cleaned_data
    form_direct = SystemChangeControlForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct._errors = {}
    form_direct.cleaned_data = {
        "system": computer_system_validation_b,
        "requestor": admin_b,
        "system_owner": admin_b,
        "qa_lead": admin_b,
        "org_unit": quality_department_b,
    }
    reject_foreign(
        form_direct,
        form_direct.cleaned_data,
        ["system", "requestor", "system_owner", "qa_lead", "org_unit"],
    )
    for field in ["system", "requestor", "system_owner", "qa_lead", "org_unit"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field]

    # 2. Bound form submission with foreign PKs is rejected
    tampered_data = _dataintegrity_change_control_payload(
        system=computer_system_validation_b,
        requestor=admin_b,
        system_owner=admin_b,
        qa_lead=admin_b,
        org_unit=quality_department_b,
    )
    bound_form = SystemChangeControlForm(data=tampered_data, tenant=tenant_a)
    assert not bound_form.is_valid()
    for field in ["system", "requestor", "system_owner", "qa_lead", "org_unit"]:
        assert field in bound_form.errors


@pytest.mark.django_db
def test_dataintegrity_fk_tampering_http_post_rejected(
    client,
    admin_user,
    tenant_a,
    computer_system_validation_b,
    doc_b,
    admin_b,
):
    """Verify HTTP POST with foreign keys is rejected with 200 form errors and no record is persisted."""
    client.force_login(admin_user)
    initial_count = ElectronicRecordPolicy.objects.filter(tenant=tenant_a).count()

    tampered_payload = _dataintegrity_policy_payload(
        title="Malicious Injected Foreign Policy",
        system=computer_system_validation_b,
        governing_sop=doc_b,
        system_owner=admin_b,
        qa_approver=admin_b,
    )
    resp = client.post(reverse("quality:electronic_record_policy_create"), tampered_payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert ElectronicRecordPolicy.objects.filter(tenant=tenant_a).count() == initial_count


# ==============================================================================
# 4. Authorization & Method Security Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_delete_method_not_allowed_on_get(
    client,
    admin_user,
    electronic_record_policy_a,
    data_integrity_assessment_a,
    audit_trail_review_a,
    system_change_control_a,
):
    """Verify GET requests to delete endpoints return HTTP 405 Method Not Allowed (@require_POST)."""
    client.force_login(admin_user)

    delete_urls = [
        reverse("quality:electronic_record_policy_delete", kwargs={"pk": electronic_record_policy_a.pk}),
        reverse("quality:data_integrity_assessment_delete", kwargs={"pk": data_integrity_assessment_a.pk}),
        reverse("quality:audit_trail_review_delete", kwargs={"pk": audit_trail_review_a.pk}),
        reverse("quality:system_change_control_delete", kwargs={"pk": system_change_control_a.pk}),
    ]
    for url in delete_urls:
        resp = client.get(url)
        assert resp.status_code == 405


@pytest.mark.django_db
def test_dataintegrity_delete_tenant_admin_required(
    client,
    member_user,
    electronic_record_policy_a,
    data_integrity_assessment_a,
    audit_trail_review_a,
    system_change_control_a,
):
    """Verify non-admin user cannot delete records; blocked with HTTP 403 Forbidden (@tenant_admin_required)."""
    client.force_login(member_user)

    policy_pk = electronic_record_policy_a.pk
    assessment_pk = data_integrity_assessment_a.pk
    review_pk = audit_trail_review_a.pk
    change_pk = system_change_control_a.pk

    # 1. Policy delete attempt
    resp_pol = client.post(reverse("quality:electronic_record_policy_delete", kwargs={"pk": policy_pk}))
    assert resp_pol.status_code == 403
    assert ElectronicRecordPolicy.objects.filter(pk=policy_pk).exists()

    # 2. Assessment delete attempt
    resp_ass = client.post(reverse("quality:data_integrity_assessment_delete", kwargs={"pk": assessment_pk}))
    assert resp_ass.status_code == 403
    assert DataIntegrityAssessment.objects.filter(pk=assessment_pk).exists()

    # 3. Audit Review delete attempt
    resp_rev = client.post(reverse("quality:audit_trail_review_delete", kwargs={"pk": review_pk}))
    assert resp_rev.status_code == 403
    assert AuditTrailReview.objects.filter(pk=review_pk).exists()

    # 4. Change Control delete attempt
    resp_cc = client.post(reverse("quality:system_change_control_delete", kwargs={"pk": change_pk}))
    assert resp_cc.status_code == 403
    assert SystemChangeControl.objects.filter(pk=change_pk).exists()


# ==============================================================================
# 5. Legal Hold & Regulatory Protection Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_legal_hold_blocks_policy_deletion(
    client,
    admin_user,
    electronic_record_policy_a,
):
    """Verify policy with legal_hold=True cannot be deleted even by a tenant admin."""
    client.force_login(admin_user)
    electronic_record_policy_a.legal_hold = True
    electronic_record_policy_a.save()

    url = reverse("quality:electronic_record_policy_delete", kwargs={"pk": electronic_record_policy_a.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:electronic_record_policy_detail", kwargs={"pk": electronic_record_policy_a.pk})

    # Policy remains intact in database
    electronic_record_policy_a.refresh_from_db()
    assert electronic_record_policy_a.legal_hold is True
    assert ElectronicRecordPolicy.objects.filter(pk=electronic_record_policy_a.pk).exists()


@pytest.mark.django_db
def test_dataintegrity_unheld_policy_can_be_deleted(
    client,
    admin_user,
    electronic_record_policy_a,
):
    """Verify policy with legal_hold=False can be deleted by a tenant admin."""
    client.force_login(admin_user)
    electronic_record_policy_a.legal_hold = False
    electronic_record_policy_a.save()

    pk = electronic_record_policy_a.pk
    url = reverse("quality:electronic_record_policy_delete", kwargs={"pk": pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:electronic_record_policy_list")
    assert not ElectronicRecordPolicy.objects.filter(pk=pk).exists()


# ==============================================================================
# 6. Audit Logging Verification Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_audit_logging_policy_operations(
    client,
    admin_user,
    tenant_a,
    computer_system_validation_a,
    doc_a,
):
    """Verify create, update, and delete operations on ElectronicRecordPolicy generate matching AuditLog entries."""
    client.force_login(admin_user)

    # 1. Create
    payload = _dataintegrity_policy_payload(
        system=computer_system_validation_a,
        governing_sop=doc_a,
        system_owner=admin_user,
        qa_approver=admin_user,
        title="Audit Logging Verification Policy",
    )
    resp_create = client.post(reverse("quality:electronic_record_policy_create"), payload)
    assert resp_create.status_code == 302
    policy = ElectronicRecordPolicy.objects.get(tenant=tenant_a, title="Audit Logging Verification Policy")
    assert _dataintegrity_verify_audit_log(tenant_a, ElectronicRecordPolicy, policy.pk, "create", actor=admin_user)

    # 2. Update
    update_payload = _dataintegrity_policy_payload(
        title="Audit Logging Policy Updated Title",
        retention_period_years=15,
    )
    resp_update = client.post(
        reverse("quality:electronic_record_policy_edit", kwargs={"pk": policy.pk}),
        update_payload,
    )
    assert resp_update.status_code == 302
    policy.refresh_from_db()
    assert policy.title == "Audit Logging Policy Updated Title"
    assert _dataintegrity_verify_audit_log(tenant_a, ElectronicRecordPolicy, policy.pk, "update", actor=admin_user)

    # 3. Delete
    policy.legal_hold = False
    policy.save()
    pk = policy.pk
    resp_delete = client.post(reverse("quality:electronic_record_policy_delete", kwargs={"pk": pk}))
    assert resp_delete.status_code == 302
    assert not ElectronicRecordPolicy.objects.filter(pk=pk).exists()
    assert _dataintegrity_verify_audit_log(tenant_a, ElectronicRecordPolicy, pk, "delete", actor=admin_user)


@pytest.mark.django_db
def test_dataintegrity_audit_logging_assessment_operations(
    client,
    admin_user,
    tenant_a,
    computer_system_validation_a,
    quality_department,
):
    """Verify create, update, and delete operations on DataIntegrityAssessment generate matching AuditLog entries."""
    client.force_login(admin_user)

    # 1. Create
    payload = _dataintegrity_assessment_payload(
        system=computer_system_validation_a,
        org_unit=quality_department,
        lead_assessor=admin_user,
        qa_reviewer=admin_user,
        title="Audit Log Assessment Target",
    )
    resp_create = client.post(reverse("quality:data_integrity_assessment_create"), payload)
    assert resp_create.status_code == 302
    assessment = DataIntegrityAssessment.objects.get(tenant=tenant_a, title="Audit Log Assessment Target")
    assert _dataintegrity_verify_audit_log(tenant_a, DataIntegrityAssessment, assessment.pk, "create", actor=admin_user)

    # 2. Update
    update_payload = _dataintegrity_assessment_payload(
        title="Audit Log Assessment Updated Title",
        overall_risk_level="medium",
    )
    resp_update = client.post(
        reverse("quality:data_integrity_assessment_edit", kwargs={"pk": assessment.pk}),
        update_payload,
    )
    assert resp_update.status_code == 302
    assessment.refresh_from_db()
    assert assessment.title == "Audit Log Assessment Updated Title"
    assert _dataintegrity_verify_audit_log(tenant_a, DataIntegrityAssessment, assessment.pk, "update", actor=admin_user)

    # 3. Delete
    pk = assessment.pk
    resp_delete = client.post(reverse("quality:data_integrity_assessment_delete", kwargs={"pk": pk}))
    assert resp_delete.status_code == 302
    assert not DataIntegrityAssessment.objects.filter(pk=pk).exists()
    assert _dataintegrity_verify_audit_log(tenant_a, DataIntegrityAssessment, pk, "delete", actor=admin_user)


@pytest.mark.django_db
def test_dataintegrity_audit_logging_audit_review_operations(
    client,
    admin_user,
    tenant_a,
    computer_system_validation_a,
):
    """Verify create, update, and delete operations on AuditTrailReview generate matching AuditLog entries."""
    client.force_login(admin_user)

    # 1. Create
    payload = _dataintegrity_audit_review_payload(
        system=computer_system_validation_a,
        reviewer=admin_user,
        qa_approver=admin_user,
        title="Audit Log Review Cycle Test",
    )
    resp_create = client.post(reverse("quality:audit_trail_review_create"), payload)
    assert resp_create.status_code == 302
    review = AuditTrailReview.objects.get(tenant=tenant_a, title="Audit Log Review Cycle Test")
    assert _dataintegrity_verify_audit_log(tenant_a, AuditTrailReview, review.pk, "create", actor=admin_user)

    # 2. Update
    update_payload = _dataintegrity_audit_review_payload(
        title="Audit Log Review Cycle Updated",
        records_sampled_count=900,
    )
    resp_update = client.post(
        reverse("quality:audit_trail_review_edit", kwargs={"pk": review.pk}),
        update_payload,
    )
    assert resp_update.status_code == 302
    review.refresh_from_db()
    assert review.title == "Audit Log Review Cycle Updated"
    assert review.records_sampled_count == 900
    assert _dataintegrity_verify_audit_log(tenant_a, AuditTrailReview, review.pk, "update", actor=admin_user)

    # 3. Delete
    pk = review.pk
    resp_delete = client.post(reverse("quality:audit_trail_review_delete", kwargs={"pk": pk}))
    assert resp_delete.status_code == 302
    assert not AuditTrailReview.objects.filter(pk=pk).exists()
    assert _dataintegrity_verify_audit_log(tenant_a, AuditTrailReview, pk, "delete", actor=admin_user)


@pytest.mark.django_db
def test_dataintegrity_audit_logging_change_control_operations(
    client,
    admin_user,
    tenant_a,
    computer_system_validation_a,
    quality_department,
):
    """Verify create, update, and delete operations on SystemChangeControl generate matching AuditLog entries."""
    client.force_login(admin_user)

    # 1. Create
    payload = _dataintegrity_change_control_payload(
        system=computer_system_validation_a,
        requestor=admin_user,
        system_owner=admin_user,
        qa_lead=admin_user,
        org_unit=quality_department,
        title="Audit Log Change Control Test",
    )
    resp_create = client.post(reverse("quality:system_change_control_create"), payload)
    assert resp_create.status_code == 302
    change = SystemChangeControl.objects.get(tenant=tenant_a, title="Audit Log Change Control Test")
    assert _dataintegrity_verify_audit_log(tenant_a, SystemChangeControl, change.pk, "create", actor=admin_user)

    # 2. Update
    update_payload = _dataintegrity_change_control_payload(
        title="Audit Log Change Control Updated",
        change_priority="urgent",
    )
    resp_update = client.post(
        reverse("quality:system_change_control_edit", kwargs={"pk": change.pk}),
        update_payload,
    )
    assert resp_update.status_code == 302
    change.refresh_from_db()
    assert change.title == "Audit Log Change Control Updated"
    assert change.change_priority == "urgent"
    assert _dataintegrity_verify_audit_log(tenant_a, SystemChangeControl, change.pk, "update", actor=admin_user)

    # 3. Delete
    pk = change.pk
    resp_delete = client.post(reverse("quality:system_change_control_delete", kwargs={"pk": pk}))
    assert resp_delete.status_code == 302
    assert not SystemChangeControl.objects.filter(pk=pk).exists()
    assert _dataintegrity_verify_audit_log(tenant_a, SystemChangeControl, pk, "delete", actor=admin_user)
