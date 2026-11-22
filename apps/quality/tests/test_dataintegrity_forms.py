"""Form unit tests for Submodule 12.20 Data Integrity & Electronic Records.

Covers:
- ElectronicRecordPolicyForm (21 CFR Part 11 / Annex 11 governance)
- DataIntegrityAssessmentForm (ALCOA+ 9-dimension assessments & remediation)
- AuditTrailReviewForm (audit log review, date range, and clean disposition checks)
- SystemChangeControlForm (GxP computerized system change management & closure summary)
"""
from datetime import timedelta
import pytest
from django.utils import timezone

from apps.quality.forms import (
    AuditTrailReviewForm,
    DataIntegrityAssessmentForm,
    ElectronicRecordPolicyForm,
    SystemChangeControlForm,
)
from apps.quality.forms._common import reject_foreign


def _dataintegrity_policy_base_data(**overrides):
    """Helper: return base valid data dictionary for ElectronicRecordPolicyForm."""
    base = {
        "title": "Electronic Batch Production Records Governance Policy",
        "record_type_name": "Electronic Master Batch Record",
        "record_category": "production_batch",
        "target_model_name": "BatchRecord",
        "is_part_11_regulated": True,
        "is_annex_11_regulated": True,
        "signature_requirement": "dual_peer_review",
        "reauthentication_required": True,
        "dual_signature_required": False,
        "audit_trail_mandatory": True,
        "retention_period_years": 10,
        "storage_format": "database_relational",
        "backup_frequency": "daily_snapshot",
        "legal_hold": False,
        "status": "draft",
        "description": "21 CFR Part 11 policy governance and electronic record boundary specifications.",
    }
    base.update(overrides)
    return base


def _dataintegrity_assessment_base_data(**overrides):
    """Helper: return base valid data dictionary for DataIntegrityAssessmentForm."""
    today = timezone.now().date()
    base = {
        "title": "LIMS Analytical Raw Data Integrity & Audit Trail Assessment",
        "assessment_scope": "QC Chromatography Data System (CDS)",
        "assessment_date": today.isoformat(),
        "next_review_due": (today + timedelta(days=365)).isoformat(),
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
        "vulnerabilities_summary": "No critical vulnerabilities identified.",
        "remediation_plan": "",
        "status": "draft",
        "comments": "Routine annual DI review.",
    }
    base.update(overrides)
    return base


def _dataintegrity_audit_trail_base_data(**overrides):
    """Helper: return base valid data dictionary for AuditTrailReviewForm."""
    today = timezone.now().date()
    base = {
        "title": "Monthly Core Database Audit Trail Review",
        "review_type": "periodic_system",
        "audit_source": "database_audit_log",
        "period_start": (today - timedelta(days=30)).isoformat(),
        "period_end": today.isoformat(),
        "review_date": today.isoformat(),
        "records_sampled_count": 150,
        "anomalies_detected_count": 0,
        "anomaly_severity": "none",
        "findings_summary": "All transaction logs verified without exception.",
        "disposition": "pending_review",
        "status": "scheduled",
        "qa_comments": "Regular review cadence.",
    }
    base.update(overrides)
    return base


def _dataintegrity_change_control_base_data(**overrides):
    """Helper: return base valid data dictionary for SystemChangeControlForm."""
    today = timezone.now().date()
    base = {
        "title": "ERP Quality Module Database Schema Migration & Audit Log Hardening",
        "change_type": "software_patch",
        "change_priority": "routine",
        "gxp_impact": "direct_gxp",
        "description": "Apply database migration for QMS data integrity tables.",
        "business_justification": "Implement 21 CFR Part 11 compliance tracking.",
        "data_integrity_risk": "Low risk; automated migration scripts with rollback.",
        "validation_deliverables": "UAT test execution scripts and post-deployment verification.",
        "rollback_plan": "Reverse migration script and restore snapshot if errors occur.",
        "target_date": (today + timedelta(days=14)).isoformat(),
        "post_review_due_date": (today + timedelta(days=30)).isoformat(),
        "status": "draft",
        "testing_successful": False,
        "data_backup_verified": True,
        "ccb_approved": False,
        "closure_summary": "",
    }
    base.update(overrides)
    return base


# ==============================================================================
# 1. ElectronicRecordPolicyForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_policy_form_valid(
    tenant_a, admin_user, computer_system_validation_a, doc_a
):
    """Verify ElectronicRecordPolicyForm validates and saves with complete valid data."""
    payload = _dataintegrity_policy_base_data(
        system=computer_system_validation_a.pk,
        governing_sop=doc_a.pk,
        system_owner=admin_user.pk,
        qa_approver=admin_user.pk,
        approval_date=timezone.now().date().isoformat(),
    )
    form = ElectronicRecordPolicyForm(tenant=tenant_a, data=payload)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    form.save_m2m()

    assert instance.tenant == tenant_a
    assert instance.number.startswith("QREC-")
    assert instance.system == computer_system_validation_a
    assert instance.governing_sop == doc_a
    assert instance.system_owner == admin_user
    assert instance.qa_approver == admin_user
    assert instance.retention_period_years == 10

    # Exclusions check
    assert "tenant" not in form.fields
    assert "number" not in form.fields

    # Update flow with commit=True on existing instance
    edit_payload = _dataintegrity_policy_base_data(
        title="Updated Electronic Records Policy Title",
        retention_period_years=15,
    )
    edit_form = ElectronicRecordPolicyForm(
        tenant=tenant_a, instance=instance, data=edit_payload
    )
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save(commit=True)
    assert updated.pk == instance.pk
    assert updated.title == "Updated Electronic Records Policy Title"
    assert updated.retention_period_years == 15


@pytest.mark.django_db
def test_dataintegrity_policy_form_required_fields(tenant_a):
    """Verify ElectronicRecordPolicyForm requires mandatory fields."""
    form = ElectronicRecordPolicyForm(tenant=tenant_a, data={})
    assert not form.is_valid()
    assert "title" in form.errors
    assert "record_type_name" in form.errors
    assert "record_category" in form.errors


@pytest.mark.django_db
def test_dataintegrity_policy_form_retention_period_validation(tenant_a):
    """Verify retention_period_years must be at least 1 year."""
    # Zero retention period
    form_zero = ElectronicRecordPolicyForm(
        tenant=tenant_a,
        data=_dataintegrity_policy_base_data(retention_period_years=0),
    )
    assert not form_zero.is_valid()
    assert "retention_period_years" in form_zero.errors
    assert "Retention period must be at least 1 year." in form_zero.errors["retention_period_years"]

    # Negative retention period
    form_neg = ElectronicRecordPolicyForm(
        tenant=tenant_a,
        data=_dataintegrity_policy_base_data(retention_period_years=-5),
    )
    assert not form_neg.is_valid()
    assert "retention_period_years" in form_neg.errors

    # Valid boundary (1 year)
    form_one = ElectronicRecordPolicyForm(
        tenant=tenant_a,
        data=_dataintegrity_policy_base_data(retention_period_years=1),
    )
    assert form_one.is_valid(), form_one.errors

    # Valid retention period (25 years)
    form_valid = ElectronicRecordPolicyForm(
        tenant=tenant_a,
        data=_dataintegrity_policy_base_data(retention_period_years=25),
    )
    assert form_valid.is_valid(), form_valid.errors


@pytest.mark.django_db
def test_dataintegrity_policy_form_foreign_key_scoping_queryset(
    tenant_a,
    tenant_b,
    computer_system_validation_a,
    computer_system_validation_b,
    doc_a,
    doc_b,
    admin_user,
    admin_b,
):
    """Verify foreign key fields are strictly scoped to tenant_a in form querysets."""
    form = ElectronicRecordPolicyForm(tenant=tenant_a)

    system_qs = form.fields["system"].queryset
    assert computer_system_validation_a in system_qs
    assert computer_system_validation_b not in system_qs

    sop_qs = form.fields["governing_sop"].queryset
    assert doc_a in sop_qs
    assert doc_b not in sop_qs

    owner_qs = form.fields["system_owner"].queryset
    assert admin_user in owner_qs
    assert admin_b not in owner_qs

    approver_qs = form.fields["qa_approver"].queryset
    assert admin_user in approver_qs
    assert admin_b not in approver_qs


@pytest.mark.django_db
def test_dataintegrity_policy_form_reject_foreign_bound(
    tenant_a, computer_system_validation_b, doc_b, admin_b
):
    """Verify bound form rejects foreign tenant objects submitted in POST payload."""
    # Foreign system
    form_sys = ElectronicRecordPolicyForm(
        tenant=tenant_a,
        data=_dataintegrity_policy_base_data(system=computer_system_validation_b.pk),
    )
    assert not form_sys.is_valid()
    assert "system" in form_sys.errors

    # Foreign governing SOP
    form_sop = ElectronicRecordPolicyForm(
        tenant=tenant_a,
        data=_dataintegrity_policy_base_data(governing_sop=doc_b.pk),
    )
    assert not form_sop.is_valid()
    assert "governing_sop" in form_sop.errors

    # Foreign system owner
    form_owner = ElectronicRecordPolicyForm(
        tenant=tenant_a,
        data=_dataintegrity_policy_base_data(system_owner=admin_b.pk),
    )
    assert not form_owner.is_valid()
    assert "system_owner" in form_owner.errors


@pytest.mark.django_db
def test_dataintegrity_policy_form_reject_foreign_direct(
    tenant_a, computer_system_validation_b, doc_b, admin_b
):
    """Directly test reject_foreign helper on ElectronicRecordPolicyForm relations."""
    form = ElectronicRecordPolicyForm(tenant=tenant_a)
    form.cleaned_data = {
        "system": computer_system_validation_b,
        "governing_sop": doc_b,
        "system_owner": admin_b,
        "qa_approver": admin_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["system", "governing_sop", "system_owner", "qa_approver"],
    )
    for field_name in ["system", "governing_sop", "system_owner", "qa_approver"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in form.errors[field_name]


# ==============================================================================
# 2. DataIntegrityAssessmentForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_assessment_form_valid(
    tenant_a,
    admin_user,
    computer_system_validation_a,
    quality_department,
    ncr_a,
    capa_investigation_a,
):
    """Verify DataIntegrityAssessmentForm validates and saves with complete valid data."""
    payload = _dataintegrity_assessment_base_data(
        system=computer_system_validation_a.pk,
        org_unit=quality_department.pk,
        lead_assessor=admin_user.pk,
        qa_reviewer=admin_user.pk,
        linked_ncr=ncr_a.pk,
        linked_capa=capa_investigation_a.pk,
        status="in_assessment",
    )
    form = DataIntegrityAssessmentForm(tenant=tenant_a, data=payload)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    form.save_m2m()

    assert instance.tenant == tenant_a
    assert instance.number.startswith("QDIR-")
    assert instance.system == computer_system_validation_a
    assert instance.org_unit == quality_department
    assert instance.lead_assessor == admin_user
    assert instance.qa_reviewer == admin_user
    assert instance.linked_ncr == ncr_a
    assert instance.linked_capa == capa_investigation_a

    # Exclusions check
    assert "tenant" not in form.fields
    assert "number" not in form.fields

    # Update flow with commit=True on existing instance
    edit_payload = _dataintegrity_assessment_base_data(
        title="Updated DI Assessment Title",
        overall_risk_level="medium",
    )
    edit_form = DataIntegrityAssessmentForm(
        tenant=tenant_a, instance=instance, data=edit_payload
    )
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save(commit=True)
    assert updated.pk == instance.pk
    assert updated.title == "Updated DI Assessment Title"
    assert updated.overall_risk_level == "medium"


@pytest.mark.django_db
def test_dataintegrity_assessment_form_required_fields(tenant_a):
    """Verify DataIntegrityAssessmentForm requires title and assessment_scope."""
    form = DataIntegrityAssessmentForm(tenant=tenant_a, data={})
    assert not form.is_valid()
    assert "title" in form.errors
    assert "assessment_scope" in form.errors


@pytest.mark.django_db
def test_dataintegrity_assessment_form_alcoa_remediation_required_when_approved(
    tenant_a, capa_investigation_a
):
    """Verify ALCOA+ remediation check: status=approved requires plan or linked CAPA if non-compliant."""
    # 1. Approved with non-compliant rating, no remediation plan, no CAPA -> Invalid
    payload_invalid = _dataintegrity_assessment_base_data(
        status="approved",
        attributable_rating="non_compliant",
        remediation_plan="",
        linked_capa=None,
    )
    form_inv = DataIntegrityAssessmentForm(tenant=tenant_a, data=payload_invalid)
    assert not form_inv.is_valid()
    assert "remediation_plan" in form_inv.errors
    assert (
        "Remediation plan or linked CAPA is required for approval when any ALCOA+ rating is non-compliant."
        in form_inv.errors["remediation_plan"]
    )

    # 2. Approved with non-compliant rating, but remediation plan is provided -> Valid
    payload_with_plan = _dataintegrity_assessment_base_data(
        status="approved",
        attributable_rating="non_compliant",
        remediation_plan="Implement mandatory individual operator biometric accounts.",
        linked_capa=None,
    )
    form_plan = DataIntegrityAssessmentForm(tenant=tenant_a, data=payload_with_plan)
    assert form_plan.is_valid(), form_plan.errors

    # 3. Approved with non-compliant rating, but linked CAPA is provided -> Valid
    payload_with_capa = _dataintegrity_assessment_base_data(
        status="approved",
        complete_rating="non_compliant",
        remediation_plan="",
        linked_capa=capa_investigation_a.pk,
    )
    form_capa = DataIntegrityAssessmentForm(tenant=tenant_a, data=payload_with_capa)
    assert form_capa.is_valid(), form_capa.errors

    # 4. Draft with non-compliant rating and no remediation -> Valid (only enforced when approved)
    payload_draft = _dataintegrity_assessment_base_data(
        status="draft",
        original_rating="non_compliant",
        remediation_plan="",
        linked_capa=None,
    )
    form_draft = DataIntegrityAssessmentForm(tenant=tenant_a, data=payload_draft)
    assert form_draft.is_valid(), form_draft.errors

    # 5. Approved with all dimensions fully compliant -> Valid without remediation
    payload_all_compliant = _dataintegrity_assessment_base_data(
        status="approved",
        attributable_rating="fully_compliant",
        legible_rating="fully_compliant",
        contemporaneous_rating="fully_compliant",
        original_rating="fully_compliant",
        accurate_rating="fully_compliant",
        complete_rating="fully_compliant",
        consistent_rating="fully_compliant",
        enduring_rating="fully_compliant",
        available_rating="fully_compliant",
        remediation_plan="",
        linked_capa=None,
    )
    form_comp = DataIntegrityAssessmentForm(tenant=tenant_a, data=payload_all_compliant)
    assert form_comp.is_valid(), form_comp.errors


@pytest.mark.django_db
def test_dataintegrity_assessment_form_foreign_key_scoping_queryset(
    tenant_a,
    tenant_b,
    computer_system_validation_a,
    computer_system_validation_b,
    quality_department,
    quality_department_b,
    ncr_a,
    ncr_b,
    capa_investigation_a,
    capa_investigation_b,
    admin_user,
    admin_b,
):
    """Verify DataIntegrityAssessmentForm scopes all foreign relations to tenant_a."""
    form = DataIntegrityAssessmentForm(tenant=tenant_a)

    assert computer_system_validation_a in form.fields["system"].queryset
    assert computer_system_validation_b not in form.fields["system"].queryset

    assert quality_department in form.fields["org_unit"].queryset
    assert quality_department_b not in form.fields["org_unit"].queryset

    assert admin_user in form.fields["lead_assessor"].queryset
    assert admin_b not in form.fields["lead_assessor"].queryset

    assert admin_user in form.fields["qa_reviewer"].queryset
    assert admin_b not in form.fields["qa_reviewer"].queryset

    assert ncr_a in form.fields["linked_ncr"].queryset
    assert ncr_b not in form.fields["linked_ncr"].queryset

    assert capa_investigation_a in form.fields["linked_capa"].queryset
    assert capa_investigation_b not in form.fields["linked_capa"].queryset


@pytest.mark.django_db
def test_dataintegrity_assessment_form_reject_foreign_bound(
    tenant_a,
    quality_department_b,
    computer_system_validation_b,
    ncr_b,
    capa_investigation_b,
):
    """Verify bound form rejects foreign relations submitted in POST payload."""
    form_dept = DataIntegrityAssessmentForm(
        tenant=tenant_a,
        data=_dataintegrity_assessment_base_data(org_unit=quality_department_b.pk),
    )
    assert not form_dept.is_valid()
    assert "org_unit" in form_dept.errors

    form_sys = DataIntegrityAssessmentForm(
        tenant=tenant_a,
        data=_dataintegrity_assessment_base_data(system=computer_system_validation_b.pk),
    )
    assert not form_sys.is_valid()
    assert "system" in form_sys.errors

    form_ncr = DataIntegrityAssessmentForm(
        tenant=tenant_a,
        data=_dataintegrity_assessment_base_data(linked_ncr=ncr_b.pk),
    )
    assert not form_ncr.is_valid()
    assert "linked_ncr" in form_ncr.errors

    form_capa = DataIntegrityAssessmentForm(
        tenant=tenant_a,
        data=_dataintegrity_assessment_base_data(linked_capa=capa_investigation_b.pk),
    )
    assert not form_capa.is_valid()
    assert "linked_capa" in form_capa.errors


@pytest.mark.django_db
def test_dataintegrity_assessment_form_reject_foreign_direct(
    tenant_a,
    quality_department_b,
    computer_system_validation_b,
    ncr_b,
    capa_investigation_b,
    admin_b,
):
    """Directly test reject_foreign helper on DataIntegrityAssessmentForm foreign relations."""
    form = DataIntegrityAssessmentForm(tenant=tenant_a)
    form.cleaned_data = {
        "system": computer_system_validation_b,
        "org_unit": quality_department_b,
        "lead_assessor": admin_b,
        "qa_reviewer": admin_b,
        "linked_capa": capa_investigation_b,
        "linked_ncr": ncr_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["system", "org_unit", "lead_assessor", "qa_reviewer", "linked_capa", "linked_ncr"],
    )
    for field_name in [
        "system",
        "org_unit",
        "lead_assessor",
        "qa_reviewer",
        "linked_capa",
        "linked_ncr",
    ]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in form.errors[field_name]


# ==============================================================================
# 3. AuditTrailReviewForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_audit_trail_form_valid(
    tenant_a, admin_user, computer_system_validation_a, ncr_a, capa_investigation_a
):
    """Verify AuditTrailReviewForm validates and saves with complete valid data."""
    payload = _dataintegrity_audit_trail_base_data(
        system=computer_system_validation_a.pk,
        reviewer=admin_user.pk,
        qa_approver=admin_user.pk,
        linked_ncr=ncr_a.pk,
        linked_capa=capa_investigation_a.pk,
        disposition="approved_clean",
        status="completed",
    )
    form = AuditTrailReviewForm(tenant=tenant_a, data=payload)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    form.save_m2m()

    assert instance.tenant == tenant_a
    assert instance.number.startswith("QATR-")
    assert instance.system == computer_system_validation_a
    assert instance.reviewer == admin_user
    assert instance.qa_approver == admin_user
    assert instance.linked_ncr == ncr_a
    assert instance.linked_capa == capa_investigation_a

    # Exclusions check
    assert "tenant" not in form.fields
    assert "number" not in form.fields

    # Update flow with commit=True on existing instance
    edit_payload = _dataintegrity_audit_trail_base_data(
        title="Updated Audit Trail Review Title",
        records_sampled_count=300,
    )
    edit_form = AuditTrailReviewForm(
        tenant=tenant_a, instance=instance, data=edit_payload
    )
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save(commit=True)
    assert updated.pk == instance.pk
    assert updated.title == "Updated Audit Trail Review Title"
    assert updated.records_sampled_count == 300


@pytest.mark.django_db
def test_dataintegrity_audit_trail_form_required_fields(tenant_a):
    """Verify AuditTrailReviewForm requires title, period_start, and period_end."""
    form = AuditTrailReviewForm(tenant=tenant_a, data={})
    assert not form.is_valid()
    assert "title" in form.errors
    assert "period_start" in form.errors
    assert "period_end" in form.errors


@pytest.mark.django_db
def test_dataintegrity_audit_trail_form_date_range_validation(tenant_a):
    """Verify period_end date cannot precede period_start date."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    # Invalid: period_start > period_end
    payload_invalid = _dataintegrity_audit_trail_base_data(
        period_start=today.isoformat(),
        period_end=yesterday.isoformat(),
    )
    form_inv = AuditTrailReviewForm(tenant=tenant_a, data=payload_invalid)
    assert not form_inv.is_valid()
    assert "period_end" in form_inv.errors
    assert "Period end date cannot precede period start date." in form_inv.errors["period_end"]

    # Valid: period_start == period_end (single day review)
    payload_same_day = _dataintegrity_audit_trail_base_data(
        period_start=today.isoformat(),
        period_end=today.isoformat(),
    )
    form_same = AuditTrailReviewForm(tenant=tenant_a, data=payload_same_day)
    assert form_same.is_valid(), form_same.errors

    # Valid: period_start < period_end
    payload_valid = _dataintegrity_audit_trail_base_data(
        period_start=yesterday.isoformat(),
        period_end=today.isoformat(),
    )
    form_valid = AuditTrailReviewForm(tenant=tenant_a, data=payload_valid)
    assert form_valid.is_valid(), form_valid.errors


@pytest.mark.django_db
def test_dataintegrity_audit_trail_form_clean_disposition_check(tenant_a):
    """Verify disposition cannot be 'approved_clean' when anomalies are detected."""
    # Invalid: anomalies > 0 and disposition is approved_clean
    payload_invalid = _dataintegrity_audit_trail_base_data(
        anomalies_detected_count=3,
        disposition="approved_clean",
    )
    form_inv = AuditTrailReviewForm(tenant=tenant_a, data=payload_invalid)
    assert not form_inv.is_valid()
    assert "disposition" in form_inv.errors
    assert (
        "Disposition cannot be 'Approved Clean' when anomalies are detected."
        in form_inv.errors["disposition"]
    )

    # Valid: anomalies > 0 and disposition is approved_remediated
    payload_remediated = _dataintegrity_audit_trail_base_data(
        anomalies_detected_count=3,
        disposition="approved_remediated",
    )
    form_rem = AuditTrailReviewForm(tenant=tenant_a, data=payload_remediated)
    assert form_rem.is_valid(), form_rem.errors

    # Valid: anomalies > 0 and disposition is rejected_escalated
    payload_escalated = _dataintegrity_audit_trail_base_data(
        anomalies_detected_count=5,
        disposition="rejected_escalated",
    )
    form_esc = AuditTrailReviewForm(tenant=tenant_a, data=payload_escalated)
    assert form_esc.is_valid(), form_esc.errors

    # Valid: anomalies == 0 and disposition is approved_clean
    payload_clean = _dataintegrity_audit_trail_base_data(
        anomalies_detected_count=0,
        disposition="approved_clean",
    )
    form_clean = AuditTrailReviewForm(tenant=tenant_a, data=payload_clean)
    assert form_clean.is_valid(), form_clean.errors


@pytest.mark.django_db
def test_dataintegrity_audit_trail_form_foreign_key_scoping_queryset(
    tenant_a,
    tenant_b,
    computer_system_validation_a,
    computer_system_validation_b,
    ncr_a,
    ncr_b,
    capa_investigation_a,
    capa_investigation_b,
    admin_user,
    admin_b,
):
    """Verify AuditTrailReviewForm scopes foreign key fields to tenant_a."""
    form = AuditTrailReviewForm(tenant=tenant_a)

    assert computer_system_validation_a in form.fields["system"].queryset
    assert computer_system_validation_b not in form.fields["system"].queryset

    assert admin_user in form.fields["reviewer"].queryset
    assert admin_b not in form.fields["reviewer"].queryset

    assert admin_user in form.fields["qa_approver"].queryset
    assert admin_b not in form.fields["qa_approver"].queryset

    assert ncr_a in form.fields["linked_ncr"].queryset
    assert ncr_b not in form.fields["linked_ncr"].queryset

    assert capa_investigation_a in form.fields["linked_capa"].queryset
    assert capa_investigation_b not in form.fields["linked_capa"].queryset


@pytest.mark.django_db
def test_dataintegrity_audit_trail_form_reject_foreign_bound(
    tenant_a, computer_system_validation_b, admin_b
):
    """Verify bound form rejects foreign relations submitted in POST payload."""
    form_sys = AuditTrailReviewForm(
        tenant=tenant_a,
        data=_dataintegrity_audit_trail_base_data(system=computer_system_validation_b.pk),
    )
    assert not form_sys.is_valid()
    assert "system" in form_sys.errors

    form_rev = AuditTrailReviewForm(
        tenant=tenant_a,
        data=_dataintegrity_audit_trail_base_data(reviewer=admin_b.pk),
    )
    assert not form_rev.is_valid()
    assert "reviewer" in form_rev.errors


@pytest.mark.django_db
def test_dataintegrity_audit_trail_form_reject_foreign_direct(
    tenant_a,
    computer_system_validation_b,
    ncr_b,
    capa_investigation_b,
    admin_b,
):
    """Directly test reject_foreign helper on AuditTrailReviewForm foreign relations."""
    form = AuditTrailReviewForm(tenant=tenant_a)
    form.cleaned_data = {
        "system": computer_system_validation_b,
        "reviewer": admin_b,
        "qa_approver": admin_b,
        "linked_ncr": ncr_b,
        "linked_capa": capa_investigation_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["system", "reviewer", "qa_approver", "linked_ncr", "linked_capa"],
    )
    for field_name in ["system", "reviewer", "qa_approver", "linked_ncr", "linked_capa"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in form.errors[field_name]


# ==============================================================================
# 4. SystemChangeControlForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_change_control_form_valid(
    tenant_a,
    admin_user,
    computer_system_validation_a,
    quality_department,
):
    """Verify SystemChangeControlForm validates and saves with complete valid data."""
    payload = _dataintegrity_change_control_base_data(
        system=computer_system_validation_a.pk,
        org_unit=quality_department.pk,
        requestor=admin_user.pk,
        system_owner=admin_user.pk,
        qa_lead=admin_user.pk,
        status="approved_for_build",
    )
    form = SystemChangeControlForm(tenant=tenant_a, data=payload)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    form.save_m2m()

    assert instance.tenant == tenant_a
    assert instance.number.startswith("QCCR-")
    assert instance.system == computer_system_validation_a
    assert instance.org_unit == quality_department
    assert instance.requestor == admin_user
    assert instance.system_owner == admin_user
    assert instance.qa_lead == admin_user

    # Exclusions check
    assert "tenant" not in form.fields
    assert "number" not in form.fields

    # Update flow with commit=True on existing instance
    edit_payload = _dataintegrity_change_control_base_data(
        title="Updated System Change Control Title",
        change_priority="urgent",
    )
    edit_form = SystemChangeControlForm(
        tenant=tenant_a, instance=instance, data=edit_payload
    )
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save(commit=True)
    assert updated.pk == instance.pk
    assert updated.title == "Updated System Change Control Title"
    assert updated.change_priority == "urgent"


@pytest.mark.django_db
def test_dataintegrity_change_control_form_required_fields(tenant_a):
    """Verify SystemChangeControlForm requires title."""
    form = SystemChangeControlForm(tenant=tenant_a, data={})
    assert not form.is_valid()
    assert "title" in form.errors


@pytest.mark.django_db
def test_dataintegrity_change_control_form_closure_summary_validation(tenant_a):
    """Verify closure_summary is required when status is implemented_closed."""
    # Invalid: implemented_closed with empty closure_summary
    payload_empty = _dataintegrity_change_control_base_data(
        status="implemented_closed",
        closure_summary="",
    )
    form_empty = SystemChangeControlForm(tenant=tenant_a, data=payload_empty)
    assert not form_empty.is_valid()
    assert "closure_summary" in form_empty.errors
    assert (
        "Closure summary is required when status is marked Implemented & Closed."
        in form_empty.errors["closure_summary"]
    )

    # Invalid: implemented_closed with whitespace closure_summary
    payload_ws = _dataintegrity_change_control_base_data(
        status="implemented_closed",
        closure_summary="   ",
    )
    form_ws = SystemChangeControlForm(tenant=tenant_a, data=payload_ws)
    assert not form_ws.is_valid()
    assert "closure_summary" in form_ws.errors

    # Valid: implemented_closed with non-empty closure_summary
    payload_closed = _dataintegrity_change_control_base_data(
        status="implemented_closed",
        closure_summary="Database migration schema applied, indexes verified, post-deployment smoke test passed.",
    )
    form_closed = SystemChangeControlForm(tenant=tenant_a, data=payload_closed)
    assert form_closed.is_valid(), form_closed.errors

    # Valid: draft status with empty closure_summary
    payload_draft = _dataintegrity_change_control_base_data(
        status="draft",
        closure_summary="",
    )
    form_draft = SystemChangeControlForm(tenant=tenant_a, data=payload_draft)
    assert form_draft.is_valid(), form_draft.errors


@pytest.mark.django_db
def test_dataintegrity_change_control_form_foreign_key_scoping_queryset(
    tenant_a,
    tenant_b,
    computer_system_validation_a,
    computer_system_validation_b,
    quality_department,
    quality_department_b,
    admin_user,
    admin_b,
):
    """Verify SystemChangeControlForm scopes foreign keys to tenant_a."""
    form = SystemChangeControlForm(tenant=tenant_a)

    assert computer_system_validation_a in form.fields["system"].queryset
    assert computer_system_validation_b not in form.fields["system"].queryset

    assert quality_department in form.fields["org_unit"].queryset
    assert quality_department_b not in form.fields["org_unit"].queryset

    assert admin_user in form.fields["requestor"].queryset
    assert admin_b not in form.fields["requestor"].queryset

    assert admin_user in form.fields["system_owner"].queryset
    assert admin_b not in form.fields["system_owner"].queryset

    assert admin_user in form.fields["qa_lead"].queryset
    assert admin_b not in form.fields["qa_lead"].queryset


@pytest.mark.django_db
def test_dataintegrity_change_control_form_reject_foreign_bound(
    tenant_a, computer_system_validation_b, quality_department_b
):
    """Verify bound form rejects foreign relations submitted in POST payload."""
    form_sys = SystemChangeControlForm(
        tenant=tenant_a,
        data=_dataintegrity_change_control_base_data(system=computer_system_validation_b.pk),
    )
    assert not form_sys.is_valid()
    assert "system" in form_sys.errors

    form_dept = SystemChangeControlForm(
        tenant=tenant_a,
        data=_dataintegrity_change_control_base_data(org_unit=quality_department_b.pk),
    )
    assert not form_dept.is_valid()
    assert "org_unit" in form_dept.errors


@pytest.mark.django_db
def test_dataintegrity_change_control_form_reject_foreign_direct(
    tenant_a,
    computer_system_validation_b,
    quality_department_b,
    admin_b,
):
    """Directly test reject_foreign helper on SystemChangeControlForm foreign relations."""
    form = SystemChangeControlForm(tenant=tenant_a)
    form.cleaned_data = {
        "system": computer_system_validation_b,
        "requestor": admin_b,
        "system_owner": admin_b,
        "qa_lead": admin_b,
        "org_unit": quality_department_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["system", "requestor", "system_owner", "qa_lead", "org_unit"],
    )
    for field_name in ["system", "requestor", "system_owner", "qa_lead", "org_unit"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in form.errors[field_name]
