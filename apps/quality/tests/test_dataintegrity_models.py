"""Model unit tests for Submodule 12.20 Data Integrity & Electronic Records.

Covers:
- ElectronicRecordPolicy (21 CFR Part 11 / Annex 11 governance)
- DataIntegrityAssessment (ALCOA+ 9-dimension assessments)
- AuditTrailReview (audit log review, anomaly detection, disposition)
- SystemChangeControl (GxP computerized system change management)
"""
from datetime import timedelta
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.quality.models import (
    ElectronicRecordPolicy,
    DataIntegrityAssessment,
    AuditTrailReview,
    SystemChangeControl,
)


def _dataintegrity_count_by_status(model_cls, tenant, status):
    """Helper: count records for a model, tenant, and status."""
    return model_cls.objects.filter(tenant=tenant, status=status).count()


def _dataintegrity_assert_badge_mapping(choices, badge_map):
    """Helper: verify that every choice key has a valid mapped CSS badge."""
    for key, _ in choices:
        assert key in badge_map
        assert badge_map[key].startswith("badge-")


# ==============================================================================
# 1. ElectronicRecordPolicy Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_policy_creation_numbering_and_str(tenant_a, admin_user):
    policy = ElectronicRecordPolicy.objects.create(
        tenant=tenant_a,
        title="Electronic Batch Production Records Policy",
        record_type_name="Electronic Master Batch Record",
        record_category="production_batch",
        target_model_name="BatchRecord",
        system_owner=admin_user,
    )
    assert policy.number.startswith("QREC-")
    assert str(policy) == f"{policy.number} — {policy.record_type_name}"

    # Verify model defaults
    assert policy.is_part_11_regulated is True
    assert policy.is_annex_11_regulated is True
    assert policy.status == "draft"
    assert policy.legal_hold is False
    assert policy.signature_requirement == "dual_peer_review"
    assert policy.reauthentication_required is True
    assert policy.dual_signature_required is False
    assert policy.audit_trail_mandatory is True
    assert policy.retention_period_years == 10
    assert policy.storage_format == "database_relational"
    assert policy.backup_frequency == "daily_snapshot"


@pytest.mark.django_db
def test_dataintegrity_policy_properties(electronic_record_policy_a):
    assert electronic_record_policy_a.is_active
    assert electronic_record_policy_a.requires_signature

    electronic_record_policy_a.status = "draft"
    electronic_record_policy_a.save()
    assert not electronic_record_policy_a.is_active

    electronic_record_policy_a.signature_requirement = "none"
    electronic_record_policy_a.save()
    assert not electronic_record_policy_a.requires_signature


@pytest.mark.django_db
def test_dataintegrity_policy_choices_and_css():
    categories = dict(ElectronicRecordPolicy.RECORD_CATEGORY_CHOICES)
    assert "production_batch" in categories
    assert "lab_analytical" in categories
    assert "electronic_signature" in categories

    sig_requirements = dict(ElectronicRecordPolicy.SIGNATURE_REQUIREMENT_CHOICES)
    assert "none" in sig_requirements
    assert "dual_peer_review" in sig_requirements
    assert "triple_qa_approval" in sig_requirements
    assert "ccb_approval" in sig_requirements

    formats = dict(ElectronicRecordPolicy.STORAGE_FORMAT_CHOICES)
    assert "database_relational" in formats
    assert "pdf_a_immutable" in formats
    assert "hybrid_blob" in formats

    frequencies = dict(ElectronicRecordPolicy.BACKUP_FREQUENCY_CHOICES)
    assert "continuous_wal" in frequencies
    assert "daily_snapshot" in frequencies

    statuses = dict(ElectronicRecordPolicy.STATUS_CHOICES)
    assert "draft" in statuses
    assert "active" in statuses
    assert "archived" in statuses

    _dataintegrity_assert_badge_mapping(
        ElectronicRecordPolicy.STATUS_CHOICES, ElectronicRecordPolicy.STATUS_CSS
    )


@pytest.mark.django_db
def test_dataintegrity_policy_relationships(
    electronic_record_policy_a,
    computer_system_validation_a,
    doc_a,
    admin_user,
):
    assert electronic_record_policy_a.system == computer_system_validation_a
    assert electronic_record_policy_a.governing_sop == doc_a
    assert electronic_record_policy_a.system_owner == admin_user
    assert electronic_record_policy_a.qa_approver == admin_user

    # Reverse relationships
    assert electronic_record_policy_a in computer_system_validation_a.electronic_record_policies.all()
    assert electronic_record_policy_a in doc_a.record_policies.all()


@pytest.mark.django_db
def test_dataintegrity_policy_unique_number_per_tenant(tenant_a, tenant_b, admin_user):
    policy1 = ElectronicRecordPolicy.objects.create(
        tenant=tenant_a,
        title="Policy Alpha",
        record_type_name="Record Alpha",
        system_owner=admin_user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ElectronicRecordPolicy.objects.create(
                tenant=tenant_a,
                number=policy1.number,
                title="Duplicate Number Policy",
                record_type_name="Record Duplicate",
                system_owner=admin_user,
            )

    # Different tenant can share number format independently
    policy_b = ElectronicRecordPolicy.objects.create(
        tenant=tenant_b,
        number=policy1.number,
        title="Tenant B Policy Same Number",
        record_type_name="Record Beta",
    )
    assert policy_b.number == policy1.number
    assert policy_b.tenant != policy1.tenant


@pytest.mark.django_db
def test_dataintegrity_policy_helper_count(tenant_a, electronic_record_policy_a):
    active_count = _dataintegrity_count_by_status(ElectronicRecordPolicy, tenant_a, "active")
    assert active_count == 1
    draft_count = _dataintegrity_count_by_status(ElectronicRecordPolicy, tenant_a, "draft")
    assert draft_count == 0


# ==============================================================================
# 2. DataIntegrityAssessment Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_assessment_creation_numbering_and_str(tenant_a, admin_user):
    today = timezone.now().date()
    assessment = DataIntegrityAssessment.objects.create(
        tenant=tenant_a,
        title="Chromatography Workstation ALCOA+ Audit",
        assessment_scope="HPLC and GC Data Systems",
        lead_assessor=admin_user,
        assessment_date=today,
    )
    assert assessment.number.startswith("QDIR-")
    assert str(assessment) == f"{assessment.number} — {assessment.title}"

    # Verify default ratings
    assert assessment.attributable_rating == "fully_compliant"
    assert assessment.legible_rating == "fully_compliant"
    assert assessment.contemporaneous_rating == "fully_compliant"
    assert assessment.original_rating == "fully_compliant"
    assert assessment.accurate_rating == "fully_compliant"
    assert assessment.complete_rating == "fully_compliant"
    assert assessment.consistent_rating == "fully_compliant"
    assert assessment.enduring_rating == "fully_compliant"
    assert assessment.available_rating == "fully_compliant"

    assert assessment.overall_risk_level == "low"
    assert assessment.status == "draft"


@pytest.mark.django_db
def test_dataintegrity_assessment_alcoa_dimensions(data_integrity_assessment_a):
    dimensions = [
        data_integrity_assessment_a.attributable_rating,
        data_integrity_assessment_a.legible_rating,
        data_integrity_assessment_a.contemporaneous_rating,
        data_integrity_assessment_a.original_rating,
        data_integrity_assessment_a.accurate_rating,
        data_integrity_assessment_a.complete_rating,
        data_integrity_assessment_a.consistent_rating,
        data_integrity_assessment_a.enduring_rating,
        data_integrity_assessment_a.available_rating,
    ]
    assert len(dimensions) == 9
    assert all(rating == "fully_compliant" for rating in dimensions)


@pytest.mark.django_db
def test_dataintegrity_assessment_properties(data_integrity_assessment_a):
    today = timezone.now().date()

    # Fully compliant baseline
    assert data_integrity_assessment_a.non_compliant_count == 0
    assert not data_integrity_assessment_a.is_high_risk
    assert data_integrity_assessment_a.is_acceptable
    assert not data_integrity_assessment_a.is_overdue

    # Introduce non-compliant ratings
    data_integrity_assessment_a.attributable_rating = "non_compliant"
    data_integrity_assessment_a.legible_rating = "non_compliant"
    data_integrity_assessment_a.save()
    assert data_integrity_assessment_a.non_compliant_count == 2
    assert not data_integrity_assessment_a.is_acceptable

    # Risk level tests
    data_integrity_assessment_a.overall_risk_level = "high"
    data_integrity_assessment_a.save()
    assert data_integrity_assessment_a.is_high_risk
    assert not data_integrity_assessment_a.is_acceptable

    data_integrity_assessment_a.overall_risk_level = "critical"
    data_integrity_assessment_a.save()
    assert data_integrity_assessment_a.is_high_risk

    # Overdue tests
    data_integrity_assessment_a.status = "in_assessment"
    data_integrity_assessment_a.next_review_due = today - timedelta(days=5)
    data_integrity_assessment_a.save()
    assert data_integrity_assessment_a.is_overdue

    data_integrity_assessment_a.status = "approved"
    data_integrity_assessment_a.save()
    assert not data_integrity_assessment_a.is_overdue


@pytest.mark.django_db
def test_dataintegrity_assessment_choices_and_css():
    alcoa_choices = dict(DataIntegrityAssessment.ALCOA_RATING_CHOICES)
    assert "fully_compliant" in alcoa_choices
    assert "partially_compliant" in alcoa_choices
    assert "non_compliant" in alcoa_choices
    assert "not_applicable" in alcoa_choices

    risks = dict(DataIntegrityAssessment.RISK_LEVEL_CHOICES)
    assert "low" in risks
    assert "critical" in risks

    _dataintegrity_assert_badge_mapping(
        DataIntegrityAssessment.STATUS_CHOICES, DataIntegrityAssessment.STATUS_CSS
    )
    _dataintegrity_assert_badge_mapping(
        DataIntegrityAssessment.RISK_LEVEL_CHOICES, DataIntegrityAssessment.RISK_LEVEL_CSS
    )


@pytest.mark.django_db
def test_dataintegrity_assessment_relationships(
    data_integrity_assessment_a,
    computer_system_validation_a,
    quality_department,
    ncr_a,
    capa_investigation_a,
    admin_user,
):
    assert data_integrity_assessment_a.system == computer_system_validation_a
    assert data_integrity_assessment_a.org_unit == quality_department
    assert data_integrity_assessment_a.lead_assessor == admin_user
    assert data_integrity_assessment_a.qa_reviewer == admin_user
    assert data_integrity_assessment_a.linked_ncr == ncr_a
    assert data_integrity_assessment_a.linked_capa == capa_investigation_a

    # Reverse relationships
    assert data_integrity_assessment_a in computer_system_validation_a.data_integrity_assessments.all()
    assert data_integrity_assessment_a in quality_department.data_integrity_assessments.all()
    assert data_integrity_assessment_a in ncr_a.di_assessments.all()
    assert data_integrity_assessment_a in capa_investigation_a.di_assessments.all()


@pytest.mark.django_db
def test_dataintegrity_assessment_unique_number_per_tenant(tenant_a, admin_user):
    today = timezone.now().date()
    item1 = DataIntegrityAssessment.objects.create(
        tenant=tenant_a,
        title="Assessment 1",
        assessment_scope="Scope 1",
        lead_assessor=admin_user,
        assessment_date=today,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DataIntegrityAssessment.objects.create(
                tenant=tenant_a,
                number=item1.number,
                title="Assessment Duplicate",
                assessment_scope="Scope Dup",
                lead_assessor=admin_user,
                assessment_date=today,
            )


# ==============================================================================
# 3. AuditTrailReview Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_creation_numbering_and_str(tenant_a, admin_user):
    today = timezone.now().date()
    review = AuditTrailReview.objects.create(
        tenant=tenant_a,
        title="Spectrophotometer Raw Log Monthly Review",
        period_start=today - timedelta(days=30),
        period_end=today,
        reviewer=admin_user,
        qa_approver=admin_user,
    )
    assert review.number.startswith("QATR-")
    assert str(review) == f"{review.number} — {review.title}"

    # Verify defaults
    assert review.review_type == "periodic_system"
    assert review.audit_source == "database_audit_log"
    assert review.anomaly_severity == "none"
    assert review.disposition == "pending_review"
    assert review.status == "scheduled"
    assert review.records_sampled_count == 0
    assert review.anomalies_detected_count == 0


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_properties(audit_trail_review_a, audit_trail_review_b):
    # audit_trail_review_a has 0 anomalies, severity='none'
    assert audit_trail_review_a.is_clean
    assert not audit_trail_review_a.requires_escalation

    # audit_trail_review_b has 2 anomalies, severity='minor'
    assert not audit_trail_review_b.is_clean
    assert not audit_trail_review_b.requires_escalation

    # Escalation condition: major or critical
    audit_trail_review_b.anomaly_severity = "major"
    audit_trail_review_b.save()
    assert audit_trail_review_b.requires_escalation

    audit_trail_review_b.anomaly_severity = "critical"
    audit_trail_review_b.save()
    assert audit_trail_review_b.requires_escalation


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_choices_and_css():
    types = dict(AuditTrailReview.REVIEW_TYPE_CHOICES)
    assert "routine_batch" in types
    assert "periodic_system" in types
    assert "event_investigation" in types

    sources = dict(AuditTrailReview.AUDIT_SOURCE_CHOICES)
    assert "database_audit_log" in sources
    assert "instrument_raw_log" in sources

    severities = dict(AuditTrailReview.SEVERITY_CHOICES)
    assert "none" in severities
    assert "critical" in severities

    dispositions = dict(AuditTrailReview.DISPOSITION_CHOICES)
    assert "pending_review" in dispositions
    assert "approved_clean" in dispositions
    assert "rejected_escalated" in dispositions

    _dataintegrity_assert_badge_mapping(
        AuditTrailReview.SEVERITY_CHOICES, AuditTrailReview.SEVERITY_CSS
    )
    _dataintegrity_assert_badge_mapping(
        AuditTrailReview.DISPOSITION_CHOICES, AuditTrailReview.DISPOSITION_CSS
    )
    _dataintegrity_assert_badge_mapping(
        AuditTrailReview.STATUS_CHOICES, AuditTrailReview.STATUS_CSS
    )


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_relationships(
    audit_trail_review_a,
    computer_system_validation_a,
    ncr_a,
    capa_investigation_a,
    admin_user,
):
    assert audit_trail_review_a.system == computer_system_validation_a
    assert audit_trail_review_a.reviewer == admin_user
    assert audit_trail_review_a.qa_approver == admin_user
    assert audit_trail_review_a.linked_ncr == ncr_a
    assert audit_trail_review_a.linked_capa == capa_investigation_a

    # Reverse relationships
    assert audit_trail_review_a in computer_system_validation_a.audit_trail_reviews.all()
    assert audit_trail_review_a in ncr_a.audit_trail_reviews.all()
    assert audit_trail_review_a in capa_investigation_a.audit_trail_reviews.all()


@pytest.mark.django_db
def test_dataintegrity_audit_trail_review_unique_number_per_tenant(tenant_a, admin_user):
    today = timezone.now().date()
    item1 = AuditTrailReview.objects.create(
        tenant=tenant_a,
        title="Review 1",
        period_start=today - timedelta(days=10),
        period_end=today,
        reviewer=admin_user,
        qa_approver=admin_user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AuditTrailReview.objects.create(
                tenant=tenant_a,
                number=item1.number,
                title="Review Dup",
                period_start=today - timedelta(days=10),
                period_end=today,
                reviewer=admin_user,
                qa_approver=admin_user,
            )


# ==============================================================================
# 4. SystemChangeControl Tests
# ==============================================================================

@pytest.mark.django_db
def test_dataintegrity_system_change_control_creation_numbering_and_str(tenant_a, admin_user):
    today = timezone.now().date()
    ccr = SystemChangeControl.objects.create(
        tenant=tenant_a,
        title="MES Database Driver Security Upgrade",
        description="Upgrade ODBC driver for database connectivity.",
        requestor=admin_user,
        system_owner=admin_user,
        qa_lead=admin_user,
        target_date=today + timedelta(days=30),
    )
    assert ccr.number.startswith("QCCR-")
    assert str(ccr) == f"{ccr.number} — {ccr.title}"

    # Verify defaults
    assert ccr.change_type == "software_patch"
    assert ccr.change_priority == "routine"
    assert ccr.gxp_impact == "direct_gxp"
    assert ccr.status == "draft"
    assert ccr.testing_successful is False
    assert ccr.data_backup_verified is False
    assert ccr.ccb_approved is False


@pytest.mark.django_db
def test_dataintegrity_system_change_control_properties(
    system_change_control_a,
    system_change_control_b,
):
    today = timezone.now().date()

    # system_change_control_a is implemented_closed, urgent
    assert system_change_control_a.is_closed
    assert not system_change_control_a.is_emergency
    assert not system_change_control_a.is_overdue

    # system_change_control_b is draft, emergency
    assert not system_change_control_b.is_closed
    assert system_change_control_b.is_emergency
    assert not system_change_control_b.is_overdue

    # Test overdue condition
    system_change_control_b.target_date = today - timedelta(days=3)
    system_change_control_b.status = "approved_for_build"
    system_change_control_b.save()
    assert system_change_control_b.is_overdue

    # If closed/rejected/cancelled, not overdue
    for term_status in ["implemented_closed", "rejected", "cancelled"]:
        system_change_control_b.status = term_status
        system_change_control_b.save()
        assert not system_change_control_b.is_overdue

    # If target_date is None, not overdue
    system_change_control_b.target_date = None
    system_change_control_b.status = "impact_assessment"
    system_change_control_b.save()
    assert not system_change_control_b.is_overdue


@pytest.mark.django_db
def test_dataintegrity_system_change_control_choices_and_css():
    types = dict(SystemChangeControl.CHANGE_TYPE_CHOICES)
    assert "software_patch" in types
    assert "major_upgrade" in types
    assert "cloud_saas_update" in types
    assert "decommission" in types

    impacts = dict(SystemChangeControl.GXP_IMPACT_CHOICES)
    assert "direct_gxp" in impacts
    assert "indirect_gxp" in impacts
    assert "non_gxp" in impacts

    priorities = dict(SystemChangeControl.CHANGE_PRIORITY_CHOICES)
    assert "routine" in priorities
    assert "emergency" in priorities

    statuses = dict(SystemChangeControl.STATUS_CHOICES)
    assert "draft" in statuses
    assert "implemented_closed" in statuses
    assert "rejected" in statuses

    _dataintegrity_assert_badge_mapping(
        SystemChangeControl.STATUS_CHOICES, SystemChangeControl.STATUS_CSS
    )
    _dataintegrity_assert_badge_mapping(
        SystemChangeControl.CHANGE_PRIORITY_CHOICES, SystemChangeControl.PRIORITY_CSS
    )
    _dataintegrity_assert_badge_mapping(
        SystemChangeControl.GXP_IMPACT_CHOICES, SystemChangeControl.GXP_IMPACT_CSS
    )


@pytest.mark.django_db
def test_dataintegrity_system_change_control_relationships(
    system_change_control_a,
    computer_system_validation_a,
    quality_department,
    admin_user,
):
    assert system_change_control_a.system == computer_system_validation_a
    assert system_change_control_a.org_unit == quality_department
    assert system_change_control_a.requestor == admin_user
    assert system_change_control_a.system_owner == admin_user
    assert system_change_control_a.qa_lead == admin_user

    # Reverse relationships
    assert system_change_control_a in computer_system_validation_a.change_controls.all()
    assert system_change_control_a in quality_department.system_change_controls.all()


@pytest.mark.django_db
def test_dataintegrity_system_change_control_unique_number_per_tenant(tenant_a, admin_user):
    today = timezone.now().date()
    item1 = SystemChangeControl.objects.create(
        tenant=tenant_a,
        title="Change 1",
        description="Desc 1",
        requestor=admin_user,
        system_owner=admin_user,
        qa_lead=admin_user,
        target_date=today + timedelta(days=10),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SystemChangeControl.objects.create(
                tenant=tenant_a,
                number=item1.number,
                title="Change Dup",
                description="Desc Dup",
                requestor=admin_user,
                system_owner=admin_user,
                qa_lead=admin_user,
                target_date=today + timedelta(days=10),
            )
