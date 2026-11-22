"""View tests for Sub-module 12.20 Data Integrity & Electronic Records.

Covers:
- data_integrity_dashboard
- ElectronicRecordPolicy views (list, detail, create, edit, delete)
- DataIntegrityAssessment views (list, detail, create, edit, delete)
- AuditTrailReview views (list, detail, create, edit, delete)
- SystemChangeControl views (list, detail, create, edit, delete)
"""
from datetime import timedelta
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.quality.models import (
    ElectronicRecordPolicy,
    DataIntegrityAssessment,
    AuditTrailReview,
    SystemChangeControl,
)


# ==============================================================================
# Module Helpers (Prefixed with _dataintegrity_)
# ==============================================================================

def _dataintegrity_verify_audit_log(tenant, obj, action):
    """Verify that an AuditLog entry exists for the given object and action."""
    ct = ContentType.objects.get_for_model(obj.__class__)
    return AuditLog.objects.filter(
        tenant=tenant,
        content_type=ct,
        object_id=str(obj.pk),
        action=action,
    ).exists()


def _dataintegrity_policy_post_data(system=None, governing_sop=None, system_owner=None, qa_approver=None, **overrides):
    """Generate valid POST payload for ElectronicRecordPolicyForm."""
    data = {
        "title": "Laboratory CDS 21 CFR Part 11 Rule",
        "record_type_name": "Chromatography Data Stream",
        "record_category": "lab_analytical",
        "target_model_name": "LabTestWorksheet",
        "system": system.pk if system else "",
        "governing_sop": governing_sop.pk if governing_sop else "",
        "is_part_11_regulated": True,
        "is_annex_11_regulated": True,
        "signature_requirement": "dual_peer_review",
        "reauthentication_required": True,
        "dual_signature_required": True,
        "audit_trail_mandatory": True,
        "retention_period_years": 10,
        "storage_format": "database_relational",
        "backup_frequency": "daily_snapshot",
        "legal_hold": False,
        "status": "draft",
        "system_owner": system_owner.pk if system_owner else "",
        "qa_approver": qa_approver.pk if qa_approver else "",
        "approval_date": "2026-11-20",
        "description": "Closed-system CDS raw data integrity policy.",
    }
    data.update(overrides)
    return data


def _dataintegrity_assessment_post_data(system=None, org_unit=None, lead_assessor=None, qa_reviewer=None, **overrides):
    """Generate valid POST payload for DataIntegrityAssessmentForm."""
    data = {
        "title": "Chromatography CDS ALCOA+ Audit",
        "assessment_scope": "QC Raw Analytical Data Stream",
        "system": system.pk if system else "",
        "org_unit": org_unit.pk if org_unit else "",
        "lead_assessor": lead_assessor.pk if lead_assessor else "",
        "qa_reviewer": qa_reviewer.pk if qa_reviewer else "",
        "assessment_date": "2026-11-20",
        "next_review_due": "2027-11-20",
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
        "vulnerabilities_summary": "Zero critical vulnerabilities discovered.",
        "remediation_plan": "Routine annual verification schedule.",
        "status": "draft",
        "comments": "Baseline initial ALCOA+ assessment.",
    }
    data.update(overrides)
    return data


def _dataintegrity_audit_trail_post_data(system=None, reviewer=None, qa_approver=None, **overrides):
    """Generate valid POST payload for AuditTrailReviewForm."""
    data = {
        "title": "Monthly CDS Raw Data Review",
        "system": system.pk if system else "",
        "review_type": "periodic_system",
        "audit_source": "database_audit_log",
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "reviewer": reviewer.pk if reviewer else "",
        "qa_approver": qa_approver.pk if qa_approver else "",
        "review_date": "2026-11-01",
        "records_sampled_count": 500,
        "anomalies_detected_count": 0,
        "anomaly_severity": "none",
        "findings_summary": "500 records verified. Zero deleted entries, zero access drifts.",
        "disposition": "approved_clean",
        "status": "scheduled",
        "qa_comments": "Audit trail log clean and Part 11 compliant.",
    }
    data.update(overrides)
    return data


def _dataintegrity_change_control_post_data(system=None, requestor=None, system_owner=None, qa_lead=None, org_unit=None, **overrides):
    """Generate valid POST payload for SystemChangeControlForm."""
    data = {
        "title": "PostgreSQL Driver Security Upgrade",
        "system": system.pk if system else "",
        "change_type": "software_patch",
        "change_priority": "routine",
        "gxp_impact": "direct_gxp",
        "requestor": requestor.pk if requestor else "",
        "system_owner": system_owner.pk if system_owner else "",
        "qa_lead": qa_lead.pk if qa_lead else "",
        "org_unit": org_unit.pk if org_unit else "",
        "description": "Upgrade PostgreSQL ODBC driver to patch timeout drops during peak load.",
        "business_justification": "Enhance system stability and ensure unbroken data transmission.",
        "data_integrity_risk": "Low risk; zero schema modifications.",
        "validation_deliverables": "IQ script and 5 automated regression test runs.",
        "rollback_plan": "Reinstall previous v15.2 driver snapshot.",
        "target_date": "2026-12-15",
        "post_review_due_date": "2027-03-15",
        "status": "draft",
        "testing_successful": False,
        "data_backup_verified": False,
        "ccb_approved": False,
        "closure_summary": "",
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. Data Integrity Dashboard Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_dashboard_view(
    client,
    admin_user,
    electronic_record_policy_a,
    data_integrity_assessment_a,
    audit_trail_review_a,
    system_change_control_a,
):
    """Verify data_integrity_dashboard returns 200 with all contracted KPI context keys."""
    client.force_login(admin_user)
    url = reverse("quality:data_integrity_dashboard")
    resp = client.get(url)
    assert resp.status_code == 200

    # Assert KPI counts and slices exist in context
    assert "total_policies_count" in resp.context
    assert "part11_policies_count" in resp.context
    assert "active_assessments_count" in resp.context
    assert "critical_risk_assessments_count" in resp.context
    assert "overdue_assessments_count" in resp.context
    assert "total_reviews_count" in resp.context
    assert "anomaly_reviews_count" in resp.context
    assert "open_changes_count" in resp.context
    assert "emergency_changes_count" in resp.context

    assert "recent_policies" in resp.context
    assert "recent_assessments" in resp.context
    assert "recent_reviews" in resp.context
    assert "recent_changes" in resp.context

    # Verify KPI counts match populated data
    assert resp.context["total_policies_count"] == 1
    assert resp.context["part11_policies_count"] == 1
    assert resp.context["total_reviews_count"] == 1
    assert resp.context["anomaly_reviews_count"] == 0

    # Content check
    assert b"Data Integrity" in resp.content or b"Electronic Records" in resp.content


@pytest.mark.django_db
def test_dataintegrity_dashboard_unauthenticated_redirect(client):
    """Verify unauthenticated user cannot access dashboard and is redirected to login."""
    url = reverse("quality:data_integrity_dashboard")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url or "login" in resp.url


# ==============================================================================
# 2. ElectronicRecordPolicy Views Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_policy_list_view(client, admin_user, electronic_record_policy_a):
    """Verify electronic_record_policy_list returns 200 with stats, context, and items."""
    client.force_login(admin_user)
    url = reverse("quality:electronic_record_policy_list")
    resp = client.get(url)
    assert resp.status_code == 200

    # Context keys check
    assert "policies" in resp.context
    assert "total_count" in resp.context
    assert "active_count" in resp.context
    assert "part11_count" in resp.context
    assert "legal_hold_count" in resp.context
    assert "category_choices" in resp.context
    assert "status_choices" in resp.context

    assert electronic_record_policy_a in resp.context["policies"]
    assert electronic_record_policy_a.number.encode() in resp.content


@pytest.mark.django_db
def test_dataintegrity_policy_list_filters_and_search(
    client,
    admin_user,
    electronic_record_policy_a,
    tenant_a,
    computer_system_validation_a,
):
    """Verify electronic_record_policy_list filters by status, category, part11, and search q."""
    client.force_login(admin_user)
    url = reverse("quality:electronic_record_policy_list")

    # Filter by category matching
    resp = client.get(url, {"category": "production_batch"})
    assert resp.status_code == 200
    assert electronic_record_policy_a in resp.context["policies"]

    # Filter by non-matching category
    resp = client.get(url, {"category": "lab_analytical"})
    assert resp.status_code == 200
    assert electronic_record_policy_a not in resp.context["policies"]

    # Filter by status matching
    resp = client.get(url, {"status": "active"})
    assert resp.status_code == 200
    assert electronic_record_policy_a in resp.context["policies"]

    # Filter by non-matching status
    resp = client.get(url, {"status": "draft"})
    assert resp.status_code == 200
    assert electronic_record_policy_a not in resp.context["policies"]

    # Filter by part11="1"
    resp = client.get(url, {"part11": "1"})
    assert resp.status_code == 200
    assert electronic_record_policy_a in resp.context["policies"]

    # Filter by part11="0"
    resp = client.get(url, {"part11": "0"})
    assert resp.status_code == 200
    assert electronic_record_policy_a not in resp.context["policies"]

    # Search query matching title
    resp = client.get(url, {"q": electronic_record_policy_a.title[:12]})
    assert resp.status_code == 200
    assert electronic_record_policy_a in resp.context["policies"]

    # Search query non-matching
    resp = client.get(url, {"q": "NonExistentSearchTerm123"})
    assert resp.status_code == 200
    assert len(resp.context["policies"]) == 0


@pytest.mark.django_db
def test_dataintegrity_policy_list_pagination(client, admin_user, tenant_a):
    """Verify electronic_record_policy_list pagination handles page splits (>20 items)."""
    client.force_login(admin_user)
    # Bulk create 25 dummy policies
    policies = [
        ElectronicRecordPolicy(
            tenant=tenant_a,
            title=f"Batch Policy {i}",
            record_type_name=f"Record Type {i}",
            number=f"QREC-PAG-{i:03d}",
        )
        for i in range(25)
    ]
    ElectronicRecordPolicy.objects.bulk_create(policies)

    url = reverse("quality:electronic_record_policy_list")
    resp_p1 = client.get(url, {"page": 1})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["policies"]) == 20
    assert resp_p1.context["is_paginated"] is True

    resp_p2 = client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["policies"]) == 5


@pytest.mark.django_db
def test_dataintegrity_policy_detail_view(client, admin_user, electronic_record_policy_a):
    """Verify electronic_record_policy_detail passes policy context and returns 200."""
    client.force_login(admin_user)
    url = reverse("quality:electronic_record_policy_detail", kwargs={"pk": electronic_record_policy_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["policy"] == electronic_record_policy_a
    assert electronic_record_policy_a.number.encode() in resp.content


@pytest.mark.django_db
def test_dataintegrity_policy_detail_tenant_isolation(client, admin_user, electronic_record_policy_b):
    """Verify tenant_a user accessing tenant_b policy receives 404."""
    client.force_login(admin_user)
    url = reverse("quality:electronic_record_policy_detail", kwargs={"pk": electronic_record_policy_b.pk})
    resp = client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_dataintegrity_policy_create_view(client, admin_user, tenant_a, computer_system_validation_a, doc_a):
    """Verify electronic_record_policy_create GET returns 200, valid POST creates record, writes AuditLog, redirects."""
    client.force_login(admin_user)
    url = reverse("quality:electronic_record_policy_create")

    # 1. GET returns 200
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    # 2. Valid POST
    payload = _dataintegrity_policy_post_data(
        system=computer_system_validation_a,
        governing_sop=doc_a,
        system_owner=admin_user,
        qa_approver=admin_user,
        title="LIMS Analytical Test Raw Records Policy",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    created = ElectronicRecordPolicy.objects.filter(
        tenant=tenant_a, title="LIMS Analytical Test Raw Records Policy"
    ).first()
    assert created is not None
    assert resp_post.url == reverse("quality:electronic_record_policy_detail", kwargs={"pk": created.pk})

    # 3. Verify AuditLog written
    assert _dataintegrity_verify_audit_log(tenant_a, created, "create")


@pytest.mark.django_db
def test_dataintegrity_policy_create_invalid_form(client, admin_user):
    """Verify electronic_record_policy_create invalid POST returns 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:electronic_record_policy_create")
    # Empty title and retention 0
    resp = client.post(url, {"title": "", "retention_period_years": 0})
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_dataintegrity_policy_edit_view(client, admin_user, electronic_record_policy_a):
    """Verify electronic_record_policy_edit GET returns 200, valid POST updates and writes AuditLog."""
    client.force_login(admin_user)
    url = reverse("quality:electronic_record_policy_edit", kwargs={"pk": electronic_record_policy_a.pk})

    # 1. GET returns 200
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    # 2. POST updates
    payload = _dataintegrity_policy_post_data(
        title="Updated eBR 21 CFR Part 11 Rule",
        retention_period_years=20,
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:electronic_record_policy_detail", kwargs={"pk": electronic_record_policy_a.pk})

    electronic_record_policy_a.refresh_from_db()
    assert electronic_record_policy_a.title == "Updated eBR 21 CFR Part 11 Rule"
    assert electronic_record_policy_a.retention_period_years == 20

    # 3. Verify AuditLog written
    assert _dataintegrity_verify_audit_log(electronic_record_policy_a.tenant, electronic_record_policy_a, "update")


@pytest.mark.django_db
def test_dataintegrity_policy_delete_view_get_method_not_allowed(client, admin_user, electronic_record_policy_a):
    """Verify electronic_record_policy_delete rejects GET with 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:electronic_record_policy_delete", kwargs={"pk": electronic_record_policy_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_dataintegrity_policy_delete_view_legal_hold_guard(client, admin_user, electronic_record_policy_a):
    """Verify electronic_record_policy_delete blocks deletion when legal_hold is True."""
    client.force_login(admin_user)
    electronic_record_policy_a.legal_hold = True
    electronic_record_policy_a.save()

    url = reverse("quality:electronic_record_policy_delete", kwargs={"pk": electronic_record_policy_a.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:electronic_record_policy_detail", kwargs={"pk": electronic_record_policy_a.pk})
    assert ElectronicRecordPolicy.objects.filter(pk=electronic_record_policy_a.pk).exists()


@pytest.mark.django_db
def test_dataintegrity_policy_delete_view_success(client, admin_user, electronic_record_policy_a):
    """Verify electronic_record_policy_delete POST removes record, logs AuditLog, redirects to list."""
    client.force_login(admin_user)
    electronic_record_policy_a.legal_hold = False
    electronic_record_policy_a.save()

    pk = electronic_record_policy_a.pk
    tenant = electronic_record_policy_a.tenant

    url = reverse("quality:electronic_record_policy_delete", kwargs={"pk": pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:electronic_record_policy_list")
    assert not ElectronicRecordPolicy.objects.filter(pk=pk).exists()

    # Verify AuditLog delete action exists
    ct = ContentType.objects.get_for_model(ElectronicRecordPolicy)
    assert AuditLog.objects.filter(tenant=tenant, content_type=ct, object_id=str(pk), action="delete").exists()


# ==============================================================================
# 3. DataIntegrityAssessment Views Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_assessment_list_view(client, admin_user, data_integrity_assessment_a):
    """Verify data_integrity_assessment_list returns 200 with stats and assessments."""
    client.force_login(admin_user)
    url = reverse("quality:data_integrity_assessment_list")
    resp = client.get(url)
    assert resp.status_code == 200

    assert "assessments" in resp.context
    assert "total_count" in resp.context
    assert "high_risk_count" in resp.context
    assert "pending_remediation_count" in resp.context
    assert "approved_count" in resp.context
    assert "risk_choices" in resp.context
    assert "status_choices" in resp.context
    assert "systems" in resp.context

    assert data_integrity_assessment_a in resp.context["assessments"]
    assert data_integrity_assessment_a.number.encode() in resp.content


@pytest.mark.django_db
def test_dataintegrity_assessment_list_filters_and_search(
    client,
    admin_user,
    data_integrity_assessment_a,
    computer_system_validation_a,
):
    """Verify data_integrity_assessment_list filters by risk_level, status, system, and q."""
    client.force_login(admin_user)
    url = reverse("quality:data_integrity_assessment_list")

    # Filter by risk_level matching
    resp = client.get(url, {"risk_level": "low"})
    assert resp.status_code == 200
    assert data_integrity_assessment_a in resp.context["assessments"]

    # Filter by risk_level non-matching
    resp = client.get(url, {"risk_level": "critical"})
    assert resp.status_code == 200
    assert data_integrity_assessment_a not in resp.context["assessments"]

    # Filter by status matching
    resp = client.get(url, {"status": "approved"})
    assert resp.status_code == 200
    assert data_integrity_assessment_a in resp.context["assessments"]

    # Filter by status non-matching
    resp = client.get(url, {"status": "draft"})
    assert resp.status_code == 200
    assert data_integrity_assessment_a not in resp.context["assessments"]

    # Filter by system matching
    resp = client.get(url, {"system": str(computer_system_validation_a.pk)})
    assert resp.status_code == 200
    assert data_integrity_assessment_a in resp.context["assessments"]

    # Search q matching title
    resp = client.get(url, {"q": data_integrity_assessment_a.title[:10]})
    assert resp.status_code == 200
    assert data_integrity_assessment_a in resp.context["assessments"]


@pytest.mark.django_db
def test_dataintegrity_assessment_detail_view(client, admin_user, data_integrity_assessment_a):
    """Verify data_integrity_assessment_detail passes assessment context and returns 200."""
    client.force_login(admin_user)
    url = reverse("quality:data_integrity_assessment_detail", kwargs={"pk": data_integrity_assessment_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["assessment"] == data_integrity_assessment_a
    assert data_integrity_assessment_a.number.encode() in resp.content


@pytest.mark.django_db
def test_dataintegrity_assessment_detail_tenant_isolation(client, admin_user, data_integrity_assessment_b):
    """Verify cross-tenant detail view access returns 404."""
    client.force_login(admin_user)
    url = reverse("quality:data_integrity_assessment_detail", kwargs={"pk": data_integrity_assessment_b.pk})
    resp = client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_dataintegrity_assessment_create_view(client, admin_user, tenant_a, computer_system_validation_a, quality_department):
    """Verify data_integrity_assessment_create GET returns 200, valid POST creates record and writes AuditLog."""
    client.force_login(admin_user)
    url = reverse("quality:data_integrity_assessment_create")

    # GET
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    # POST
    payload = _dataintegrity_assessment_post_data(
        system=computer_system_validation_a,
        org_unit=quality_department,
        lead_assessor=admin_user,
        qa_reviewer=admin_user,
        title="Electronic Microplate Reader ALCOA+ Review",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    created = DataIntegrityAssessment.objects.filter(
        tenant=tenant_a, title="Electronic Microplate Reader ALCOA+ Review"
    ).first()
    assert created is not None
    assert resp_post.url == reverse("quality:data_integrity_assessment_detail", kwargs={"pk": created.pk})

    # Verify AuditLog
    assert _dataintegrity_verify_audit_log(tenant_a, created, "create")


@pytest.mark.django_db
def test_dataintegrity_assessment_create_auto_populates_qa_approved_at(
    client, admin_user, tenant_a, computer_system_validation_a, quality_department
):
    """Verify data_integrity_assessment_create with status=approved auto-populates qa_approved_at."""
    client.force_login(admin_user)
    url = reverse("quality:data_integrity_assessment_create")

    payload = _dataintegrity_assessment_post_data(
        system=computer_system_validation_a,
        org_unit=quality_department,
        lead_assessor=admin_user,
        qa_reviewer=admin_user,
        title="Immediate Approved Assessment",
        status="approved",
    )
    resp = client.post(url, payload)
    assert resp.status_code == 302

    created = DataIntegrityAssessment.objects.filter(
        tenant=tenant_a, title="Immediate Approved Assessment"
    ).first()
    assert created is not None
    assert created.status == "approved"
    assert created.qa_approved_at is not None


@pytest.mark.django_db
def test_dataintegrity_assessment_edit_view_and_transition_approved(client, admin_user, data_integrity_assessment_a):
    """Verify edit view GET 200, valid POST updates and auto-populates qa_approved_at on transition to approved."""
    client.force_login(admin_user)
    # Set status to in_assessment and clear qa_approved_at
    data_integrity_assessment_a.status = "in_assessment"
    data_integrity_assessment_a.qa_approved_at = None
    data_integrity_assessment_a.save()

    url = reverse("quality:data_integrity_assessment_edit", kwargs={"pk": data_integrity_assessment_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = _dataintegrity_assessment_post_data(
        title="Updated ALCOA+ Review Title",
        status="approved",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    data_integrity_assessment_a.refresh_from_db()
    assert data_integrity_assessment_a.title == "Updated ALCOA+ Review Title"
    assert data_integrity_assessment_a.status == "approved"
    assert data_integrity_assessment_a.qa_approved_at is not None

    # Verify AuditLog
    assert _dataintegrity_verify_audit_log(data_integrity_assessment_a.tenant, data_integrity_assessment_a, "update")


@pytest.mark.django_db
def test_dataintegrity_assessment_delete_view_get_method_not_allowed(client, admin_user, data_integrity_assessment_a):
    """Verify data_integrity_assessment_delete rejects GET with 405."""
    client.force_login(admin_user)
    url = reverse("quality:data_integrity_assessment_delete", kwargs={"pk": data_integrity_assessment_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_dataintegrity_assessment_delete_view_success(client, admin_user, data_integrity_assessment_a):
    """Verify data_integrity_assessment_delete POST removes record, logs AuditLog, redirects to list."""
    client.force_login(admin_user)
    pk = data_integrity_assessment_a.pk
    tenant = data_integrity_assessment_a.tenant

    url = reverse("quality:data_integrity_assessment_delete", kwargs={"pk": pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:data_integrity_assessment_list")
    assert not DataIntegrityAssessment.objects.filter(pk=pk).exists()

    ct = ContentType.objects.get_for_model(DataIntegrityAssessment)
    assert AuditLog.objects.filter(tenant=tenant, content_type=ct, object_id=str(pk), action="delete").exists()


# ==============================================================================
# 4. AuditTrailReview Views Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_list_view(client, admin_user, audit_trail_review_a):
    """Verify audit_trail_review_list returns 200 with stats and reviews."""
    client.force_login(admin_user)
    url = reverse("quality:audit_trail_review_list")
    resp = client.get(url)
    assert resp.status_code == 200

    assert "reviews" in resp.context
    assert "total_count" in resp.context
    assert "anomaly_count" in resp.context
    assert "completed_count" in resp.context
    assert "clean_count" in resp.context
    assert "type_choices" in resp.context
    assert "severity_choices" in resp.context
    assert "status_choices" in resp.context

    assert audit_trail_review_a in resp.context["reviews"]
    assert audit_trail_review_a.number.encode() in resp.content


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_list_filters_and_search(client, admin_user, audit_trail_review_a):
    """Verify audit_trail_review_list filters by review_type, severity, status, and search q."""
    client.force_login(admin_user)
    url = reverse("quality:audit_trail_review_list")

    # Filter review_type
    resp = client.get(url, {"review_type": "periodic_system"})
    assert resp.status_code == 200
    assert audit_trail_review_a in resp.context["reviews"]

    resp = client.get(url, {"review_type": "event_investigation"})
    assert resp.status_code == 200
    assert audit_trail_review_a not in resp.context["reviews"]

    # Filter severity
    resp = client.get(url, {"severity": "none"})
    assert resp.status_code == 200
    assert audit_trail_review_a in resp.context["reviews"]

    # Filter status
    resp = client.get(url, {"status": "completed"})
    assert resp.status_code == 200
    assert audit_trail_review_a in resp.context["reviews"]

    # Search q
    resp = client.get(url, {"q": audit_trail_review_a.title[:12]})
    assert resp.status_code == 200
    assert audit_trail_review_a in resp.context["reviews"]


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_detail_view(client, admin_user, audit_trail_review_a):
    """Verify audit_trail_review_detail passes review context and returns 200."""
    client.force_login(admin_user)
    url = reverse("quality:audit_trail_review_detail", kwargs={"pk": audit_trail_review_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["review"] == audit_trail_review_a
    assert audit_trail_review_a.number.encode() in resp.content


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_detail_tenant_isolation(client, admin_user, audit_trail_review_b):
    """Verify cross-tenant detail view access returns 404."""
    client.force_login(admin_user)
    url = reverse("quality:audit_trail_review_detail", kwargs={"pk": audit_trail_review_b.pk})
    resp = client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_create_view(client, admin_user, tenant_a, computer_system_validation_a):
    """Verify audit_trail_review_create GET returns 200, valid POST creates record and writes AuditLog."""
    client.force_login(admin_user)
    url = reverse("quality:audit_trail_review_create")

    # GET
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    # POST
    payload = _dataintegrity_audit_trail_post_data(
        system=computer_system_validation_a,
        reviewer=admin_user,
        qa_approver=admin_user,
        title="Q4 2026 ERP Database Audit Review",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    created = AuditTrailReview.objects.filter(
        tenant=tenant_a, title="Q4 2026 ERP Database Audit Review"
    ).first()
    assert created is not None
    assert resp_post.url == reverse("quality:audit_trail_review_detail", kwargs={"pk": created.pk})

    # Verify AuditLog
    assert _dataintegrity_verify_audit_log(tenant_a, created, "create")


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_edit_view_and_transition_completed(client, admin_user, audit_trail_review_a):
    """Verify edit view GET 200, valid POST updates and auto-populates completed_at when status transitioned to completed."""
    client.force_login(admin_user)
    # Set to in_progress and clear completed_at
    audit_trail_review_a.status = "in_progress"
    audit_trail_review_a.completed_at = None
    audit_trail_review_a.save()

    url = reverse("quality:audit_trail_review_edit", kwargs={"pk": audit_trail_review_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = _dataintegrity_audit_trail_post_data(
        title="Updated Audit Review Title",
        status="completed",
        period_start=str(audit_trail_review_a.period_start),
        period_end=str(audit_trail_review_a.period_end),
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    audit_trail_review_a.refresh_from_db()
    assert audit_trail_review_a.title == "Updated Audit Review Title"
    assert audit_trail_review_a.status == "completed"
    assert audit_trail_review_a.completed_at is not None

    # Verify AuditLog
    assert _dataintegrity_verify_audit_log(audit_trail_review_a.tenant, audit_trail_review_a, "update")


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_delete_view_get_method_not_allowed(client, admin_user, audit_trail_review_a):
    """Verify audit_trail_review_delete rejects GET with 405."""
    client.force_login(admin_user)
    url = reverse("quality:audit_trail_review_delete", kwargs={"pk": audit_trail_review_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_delete_view_success(client, admin_user, audit_trail_review_a):
    """Verify audit_trail_review_delete POST removes record, writes AuditLog, redirects to list."""
    client.force_login(admin_user)
    pk = audit_trail_review_a.pk
    tenant = audit_trail_review_a.tenant

    url = reverse("quality:audit_trail_review_delete", kwargs={"pk": pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:audit_trail_review_list")
    assert not AuditTrailReview.objects.filter(pk=pk).exists()

    ct = ContentType.objects.get_for_model(AuditTrailReview)
    assert AuditLog.objects.filter(tenant=tenant, content_type=ct, object_id=str(pk), action="delete").exists()


# ==============================================================================
# 5. SystemChangeControl Views Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_system_change_control_list_view(client, admin_user, system_change_control_a):
    """Verify system_change_control_list returns 200 with stats and change records."""
    client.force_login(admin_user)
    url = reverse("quality:system_change_control_list")
    resp = client.get(url)
    assert resp.status_code == 200

    assert "changes" in resp.context
    assert "total_count" in resp.context
    assert "emergency_count" in resp.context
    assert "direct_gxp_count" in resp.context
    assert "open_count" in resp.context
    assert "type_choices" in resp.context
    assert "priority_choices" in resp.context
    assert "gxp_choices" in resp.context
    assert "status_choices" in resp.context

    assert system_change_control_a in resp.context["changes"]
    assert system_change_control_a.number.encode() in resp.content


@pytest.mark.django_db
def test_dataintegrity_system_change_control_list_filters_and_search(client, admin_user, system_change_control_a):
    """Verify system_change_control_list filters by change_type, priority, gxp_impact, status, and q."""
    client.force_login(admin_user)
    url = reverse("quality:system_change_control_list")

    # Filter change_type
    resp = client.get(url, {"change_type": "software_patch"})
    assert resp.status_code == 200
    assert system_change_control_a in resp.context["changes"]

    resp = client.get(url, {"change_type": "major_upgrade"})
    assert resp.status_code == 200
    assert system_change_control_a not in resp.context["changes"]

    # Filter priority
    resp = client.get(url, {"priority": "urgent"})
    assert resp.status_code == 200
    assert system_change_control_a in resp.context["changes"]

    # Filter gxp_impact
    resp = client.get(url, {"gxp_impact": "direct_gxp"})
    assert resp.status_code == 200
    assert system_change_control_a in resp.context["changes"]

    # Filter status
    resp = client.get(url, {"status": "implemented_closed"})
    assert resp.status_code == 200
    assert system_change_control_a in resp.context["changes"]

    # Search q
    resp = client.get(url, {"q": system_change_control_a.title[:12]})
    assert resp.status_code == 200
    assert system_change_control_a in resp.context["changes"]


@pytest.mark.django_db
def test_dataintegrity_system_change_control_detail_view(client, admin_user, system_change_control_a):
    """Verify system_change_control_detail passes change context and returns 200."""
    client.force_login(admin_user)
    url = reverse("quality:system_change_control_detail", kwargs={"pk": system_change_control_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["change"] == system_change_control_a
    assert system_change_control_a.number.encode() in resp.content


@pytest.mark.django_db
def test_dataintegrity_system_change_control_detail_tenant_isolation(client, admin_user, system_change_control_b):
    """Verify cross-tenant detail view access returns 404."""
    client.force_login(admin_user)
    url = reverse("quality:system_change_control_detail", kwargs={"pk": system_change_control_b.pk})
    resp = client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_dataintegrity_system_change_control_create_view(
    client, admin_user, tenant_a, computer_system_validation_a, quality_department
):
    """Verify system_change_control_create GET returns 200, valid POST creates record and writes AuditLog."""
    client.force_login(admin_user)
    url = reverse("quality:system_change_control_create")

    # GET
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    # POST
    payload = _dataintegrity_change_control_post_data(
        system=computer_system_validation_a,
        requestor=admin_user,
        system_owner=admin_user,
        qa_lead=admin_user,
        org_unit=quality_department,
        title="LIMS TLS 1.3 Cipher Suite Modernization",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    created = SystemChangeControl.objects.filter(
        tenant=tenant_a, title="LIMS TLS 1.3 Cipher Suite Modernization"
    ).first()
    assert created is not None
    assert resp_post.url == reverse("quality:system_change_control_detail", kwargs={"pk": created.pk})

    # Verify AuditLog
    assert _dataintegrity_verify_audit_log(tenant_a, created, "create")


@pytest.mark.django_db
def test_dataintegrity_system_change_control_edit_view_and_transition_closed(client, admin_user, system_change_control_a):
    """Verify edit view GET 200, valid POST updates and auto-populates actual_implementation_date when closed."""
    client.force_login(admin_user)
    # Set to approved_for_build and clear actual_implementation_date
    system_change_control_a.status = "approved_for_build"
    system_change_control_a.actual_implementation_date = None
    system_change_control_a.save()

    url = reverse("quality:system_change_control_edit", kwargs={"pk": system_change_control_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = _dataintegrity_change_control_post_data(
        title="Updated System Change Control Title",
        status="implemented_closed",
        closure_summary="Deployment verified with 100% test execution pass rate.",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    system_change_control_a.refresh_from_db()
    assert system_change_control_a.title == "Updated System Change Control Title"
    assert system_change_control_a.status == "implemented_closed"
    assert system_change_control_a.actual_implementation_date == timezone.now().date()

    # Verify AuditLog
    assert _dataintegrity_verify_audit_log(system_change_control_a.tenant, system_change_control_a, "update")


@pytest.mark.django_db
def test_dataintegrity_system_change_control_delete_view_get_method_not_allowed(client, admin_user, system_change_control_a):
    """Verify system_change_control_delete rejects GET with 405."""
    client.force_login(admin_user)
    url = reverse("quality:system_change_control_delete", kwargs={"pk": system_change_control_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_dataintegrity_system_change_control_delete_view_success(client, admin_user, system_change_control_a):
    """Verify system_change_control_delete POST removes record, writes AuditLog, redirects to list."""
    client.force_login(admin_user)
    pk = system_change_control_a.pk
    tenant = system_change_control_a.tenant

    url = reverse("quality:system_change_control_delete", kwargs={"pk": pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:system_change_control_list")
    assert not SystemChangeControl.objects.filter(pk=pk).exists()

    ct = ContentType.objects.get_for_model(SystemChangeControl)
    assert AuditLog.objects.filter(tenant=tenant, content_type=ct, object_id=str(pk), action="delete").exists()
