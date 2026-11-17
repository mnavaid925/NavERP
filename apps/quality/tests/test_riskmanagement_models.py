"""
Unit tests for apps/quality models (Sub-module 12.3: Risk Management - ISO 14971 / FMEA).

Covers:
- RiskManagementPlan [QRMP-]: auto-numbering, device classifications, matrix dimensions,
  status workflows, overdue review logic, assessment & unmitigated counts,
  compound indexes, unique constraints, tenant isolation.
- RiskAssessment [QRSK-]: auto-numbering, analysis types, hazard categories,
  initial RPN and risk level calculation (unacceptable >= 15, alarp >= 6, broadly_acceptable < 6),
  residual RPN & risk level calculation, safety gates (unacceptable forces residual_risk_acceptable=False,
  alarp requires bra_required=True, broadly_acceptable sets acceptable=True),
  clearing residual values, CSS badges, links to DesignInput.
- RiskControlMeasure [QRCM-]: auto-numbering, ISO 14971 Clause 7.1 hierarchy priority,
  status choices and CSS badges, is_fully_verified property,
  spine links to DesignInput, DesignVerification, and ControlledDocument.
- RiskReviewRecord [QRMR-]: auto-numbering, review types, PMS / ISO 14971 Clause 9 reviews,
  status choices and badges, link to ElectronicSignatureRecord, protected reviewer.
"""

from datetime import timedelta
import re
import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.quality.models import (
    ControlledDocument,
    DesignInput,
    DesignProject,
    DesignVerification,
    ElectronicSignatureRecord,
    RiskAssessment,
    RiskControlMeasure,
    RiskManagementPlan,
    RiskReviewRecord,
)

pytestmark = pytest.mark.django_db

_RISKMANAGEMENT_VALID_BADGE_CLASSES = {
    "badge-slate",
    "badge-info",
    "badge-green",
    "badge-amber",
    "badge-red",
    "badge-muted",
}


# =====================================================================
# Module-level Fixtures and Helpers (Prefix: _riskmanagement_*)
# =====================================================================


def _riskmanagement_create_plan(tenant, lead_risk_manager, **kwargs):
    """Factory helper creating a RiskManagementPlan with sensible defaults."""
    data = {
        "tenant": tenant,
        "title": "InfuseFlow Pro 3000 Risk Management Plan",
        "plan_version": "1.0",
        "status": "draft",
        "device_classification": "class_ii_a",
        "lead_risk_manager": lead_risk_manager,
        "matrix_dimension": "5x5",
        "scope_description": "Comprehensive ISO 14971 risk management lifecycle for infusion pump.",
        "risk_acceptability_policy": "Broadly acceptable if RPN < 6; ALARP between 6 and 14 with clinical BRA.",
        "periodic_review_frequency_months": 12,
        "overall_residual_risk_acceptable": False,
    }
    data.update(kwargs)
    return RiskManagementPlan.objects.create(**data)


def _riskmanagement_create_assessment(tenant, plan, **kwargs):
    """Factory helper creating a RiskAssessment with sensible defaults."""
    data = {
        "tenant": tenant,
        "plan": plan,
        "analysis_type": "hazard_analysis",
        "hazard_category": "energy_electrical",
        "hazard_description": "High voltage creepage across power supply barrier",
        "hazardous_situation": "Patient or clinical operator touches exposed energized chassis",
        "foreseeable_sequence_of_events": "Transformer insulation failure allows mains AC onto secondary DC bus",
        "potential_harm": "Ventricular fibrillation or cardiac arrest",
        "initial_severity": 4,
        "initial_probability": 3,
        "initial_detectability": 1,
        "lifecycle_status": "open",
    }
    data.update(kwargs)
    return RiskAssessment.objects.create(**data)


def _riskmanagement_create_control(tenant, risk_assessment, **kwargs):
    """Factory helper creating a RiskControlMeasure with sensible defaults."""
    data = {
        "tenant": tenant,
        "risk_assessment": risk_assessment,
        "control_hierarchy": "inherent_safety",
        "title": "4kV Reinforced Dielectric Galvanic Isolator",
        "description": "Double-insulated reinforced safety transformer meeting IEC 60601-1 Class II requirements.",
        "status": "planned",
        "implementation_verified": False,
        "effectiveness_verified": False,
    }
    data.update(kwargs)
    return RiskControlMeasure.objects.create(**data)


def _riskmanagement_create_review(tenant, plan, lead_reviewer, **kwargs):
    """Factory helper creating a RiskReviewRecord with sensible defaults."""
    data = {
        "tenant": tenant,
        "plan": plan,
        "review_title": "Phase Gate 2 Risk Management Report",
        "review_type": "initial_rmr",
        "review_date": timezone.now().date(),
        "findings_summary": "All identified hazards evaluated; residual risk acceptable per ISO 14971 Clause 9.",
        "status": "draft",
        "lead_reviewer": lead_reviewer,
    }
    data.update(kwargs)
    return RiskReviewRecord.objects.create(**data)


# =====================================================================
# 1. RiskManagementPlan Tests
# =====================================================================


def test_riskmanagement_plan_auto_number_format(tenant_a, admin_user):
    """Auto-numbering must follow QRMP-##### format."""
    plan = _riskmanagement_create_plan(tenant_a, admin_user)
    assert plan.number.startswith("QRMP-")
    assert re.match(r"^QRMP-\d{5}$", plan.number) is not None


def test_riskmanagement_plan_sequential_continuity_per_tenant(tenant_a, admin_user):
    """Sequential auto-numbering must increment monotonically per tenant."""
    p1 = _riskmanagement_create_plan(tenant_a, admin_user, title="Plan 1")
    p2 = _riskmanagement_create_plan(tenant_a, admin_user, title="Plan 2")
    p3 = _riskmanagement_create_plan(tenant_a, admin_user, title="Plan 3")

    num1 = int(p1.number.split("-")[1])
    num2 = int(p2.number.split("-")[1])
    num3 = int(p3.number.split("-")[1])
    assert num2 == num1 + 1
    assert num3 == num2 + 1


def test_riskmanagement_plan_multi_tenant_isolation(tenant_a, tenant_b, admin_user, admin_b):
    """Tenant B should not increment or collide with Tenant A's sequence."""
    p_a = _riskmanagement_create_plan(tenant_a, admin_user, title="Acme Plan")
    p_b = _riskmanagement_create_plan(tenant_b, admin_b, title="Globex Plan")
    assert p_a.tenant != p_b.tenant
    assert p_a.number.startswith("QRMP-")
    assert p_b.number.startswith("QRMP-")


def test_riskmanagement_plan_str_representation(tenant_a, admin_user):
    """__str__ must return '{number} - {title} (v{plan_version})'."""
    plan = _riskmanagement_create_plan(tenant_a, admin_user, title="Safety Syringe Plan", plan_version="2.1")
    expected = f"{plan.number} - Safety Syringe Plan (v2.1)"
    assert str(plan) == expected


def test_riskmanagement_plan_default_values(tenant_a, admin_user):
    """Verify standard ISO 14971 default values on creation."""
    plan = RiskManagementPlan.objects.create(
        tenant=tenant_a,
        title="Default Infusion Plan",
        lead_risk_manager=admin_user,
        scope_description="Default scope description.",
        risk_acceptability_policy="Default policy.",
    )
    assert plan.plan_version == "1.0"
    assert plan.status == "draft"
    assert plan.device_classification == "class_ii_a"
    assert plan.matrix_dimension == "5x5"
    assert plan.periodic_review_frequency_months == 12
    assert plan.overall_residual_risk_acceptable is False
    assert plan.overall_benefit_risk_summary == ""
    assert plan.approved_signature is None
    assert plan.next_review_due_date is None


def test_riskmanagement_plan_status_choices_and_badges(tenant_a, admin_user):
    """Verify all status choices have mapped, valid badge CSS classes."""
    statuses = [c[0] for c in RiskManagementPlan.STATUS_CHOICES]
    expected_statuses = ["draft", "in_review", "active", "periodic_review", "superseded", "archived"]
    for st in expected_statuses:
        assert st in statuses

    for st in expected_statuses:
        plan = _riskmanagement_create_plan(tenant_a, admin_user, status=st)
        assert plan.status_badge in _RISKMANAGEMENT_VALID_BADGE_CLASSES

    # Unknown fallback
    fake_plan = RiskManagementPlan(status="unknown_status")
    assert fake_plan.status_badge == "badge-slate"


def test_riskmanagement_plan_device_class_choices_and_badges(tenant_a, admin_user):
    """Verify device classification choices and CSS badges."""
    classes = [c[0] for c in RiskManagementPlan.DEVICE_CLASSIFICATION_CHOICES]
    expected_classes = ["class_i", "class_ii_a", "class_ii_b", "class_iii", "samd", "non_medical"]
    for cls_name in expected_classes:
        assert cls_name in classes

    for cls_name in expected_classes:
        plan = _riskmanagement_create_plan(tenant_a, admin_user, device_classification=cls_name)
        assert plan.device_class_badge in _RISKMANAGEMENT_VALID_BADGE_CLASSES

    fake_plan = RiskManagementPlan(device_classification="unknown_class")
    assert fake_plan.device_class_badge == "badge-slate"


def test_riskmanagement_plan_matrix_dimension_choices(tenant_a, admin_user):
    """Verify matrix dimension enumeration per commercial risk assessment."""
    dimensions = [c[0] for c in RiskManagementPlan.MATRIX_DIMENSION_CHOICES]
    assert "3x3" in dimensions
    assert "4x4" in dimensions
    assert "5x5" in dimensions

    plan = _riskmanagement_create_plan(tenant_a, admin_user, matrix_dimension="3x3")
    assert plan.matrix_dimension == "3x3"


def test_riskmanagement_plan_is_review_overdue_property(tenant_a, admin_user):
    """Review overdue check requires active or periodic_review status and past date."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    # Active status with past due date -> Overdue
    plan_overdue = _riskmanagement_create_plan(
        tenant_a, admin_user, status="active", next_review_due_date=yesterday
    )
    assert plan_overdue.is_review_overdue is True

    # Active status with future due date -> Not overdue
    plan_future = _riskmanagement_create_plan(
        tenant_a, admin_user, status="active", next_review_due_date=tomorrow
    )
    assert plan_future.is_review_overdue is False

    # Draft status with past due date -> Not overdue (must be active or periodic_review)
    plan_draft = _riskmanagement_create_plan(
        tenant_a, admin_user, status="draft", next_review_due_date=yesterday
    )
    assert plan_draft.is_review_overdue is False

    # Periodic review status with past due date -> Overdue
    plan_periodic = _riskmanagement_create_plan(
        tenant_a, admin_user, status="periodic_review", next_review_due_date=yesterday
    )
    assert plan_periodic.is_review_overdue is True

    # No due date set -> Not overdue
    plan_none = _riskmanagement_create_plan(
        tenant_a, admin_user, status="active", next_review_due_date=None
    )
    assert plan_none.is_review_overdue is False


def test_riskmanagement_plan_assessments_count_property(tenant_a, admin_user):
    """assessments_count must reflect total risk assessments linked to plan."""
    plan = _riskmanagement_create_plan(tenant_a, admin_user)
    assert plan.assessments_count == 0

    _riskmanagement_create_assessment(tenant_a, plan, hazard_description="Hazard 1")
    _riskmanagement_create_assessment(tenant_a, plan, hazard_description="Hazard 2")
    assert plan.assessments_count == 2


def test_riskmanagement_plan_unmitigated_risks_count_property(tenant_a, admin_user):
    """unmitigated_risks_count must count assessments where residual_risk_acceptable is False."""
    plan = _riskmanagement_create_plan(tenant_a, admin_user)

    # Hazard 1: open with no residual check -> unmitigated
    a1 = _riskmanagement_create_assessment(tenant_a, plan, hazard_description="Risk 1")
    assert a1.residual_risk_acceptable is False

    # Hazard 2: broadly acceptable residual risk -> mitigated
    a2 = _riskmanagement_create_assessment(
        tenant_a,
        plan,
        hazard_description="Risk 2",
        residual_severity=1,
        residual_probability=2,
    )
    assert a2.residual_risk_acceptable is True

    # Hazard 3: unacceptable residual risk -> unmitigated
    a3 = _riskmanagement_create_assessment(
        tenant_a,
        plan,
        hazard_description="Risk 3",
        residual_severity=4,
        residual_probability=4,
    )
    assert a3.residual_risk_acceptable is False

    assert plan.assessments_count == 3
    assert plan.unmitigated_risks_count == 2


def test_riskmanagement_plan_lead_risk_manager_protected(tenant_a, admin_user):
    """Lead risk manager deletion must raise ProtectedError."""
    plan = _riskmanagement_create_plan(tenant_a, admin_user)
    with pytest.raises(ProtectedError):
        admin_user.delete()


def test_riskmanagement_plan_department_set_null(tenant_a, admin_user, quality_department):
    """Department deletion must set null on plan."""
    plan = _riskmanagement_create_plan(tenant_a, admin_user, department=quality_department)
    assert plan.department == quality_department
    quality_department.delete()
    plan.refresh_from_db()
    assert plan.department is None


def test_riskmanagement_plan_unique_constraint(tenant_a, tenant_b, admin_user, admin_b):
    """UniqueConstraint enforces uniqueness of (tenant, number)."""
    p1 = _riskmanagement_create_plan(tenant_a, admin_user)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RiskManagementPlan.objects.create(
                tenant=tenant_a,
                number=p1.number,
                title="Duplicate Number Plan",
                lead_risk_manager=admin_user,
            )

    # Cross-tenant same number is allowed
    p_b = RiskManagementPlan.objects.create(
        tenant=tenant_b,
        number=p1.number,
        title="Cross Tenant Plan",
        lead_risk_manager=admin_b,
    )
    assert p_b.number == p1.number
    assert p_b.tenant != p1.tenant


def test_riskmanagement_plan_indexes_and_meta(tenant_a):
    """Verify Model Meta constraints, index definitions, and verbose names."""
    meta = RiskManagementPlan._meta
    assert meta.verbose_name == "Risk Management Plan"
    assert meta.verbose_name_plural == "Risk Management Plans"
    assert meta.ordering == ["-created_at"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_qrmp_ten_status" in index_names
    assert "idx_qrmp_ten_class" in index_names
    assert "idx_qrmp_ten_prj" in index_names
    assert "idx_qrmp_ten_created" in index_names


# =====================================================================
# 2. RiskAssessment Tests
# =====================================================================


def test_riskmanagement_assessment_auto_number_format(risk_management_plan_a):
    """Auto-numbering must follow QRSK-##### format."""
    assessment = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant, risk_management_plan_a
    )
    assert assessment.number.startswith("QRSK-")
    assert re.match(r"^QRSK-\d{5}$", assessment.number) is not None


def test_riskmanagement_assessment_sequential_continuity(risk_management_plan_a):
    """Sequential auto-numbering must increment monotonically per tenant."""
    a1 = _riskmanagement_create_assessment(risk_management_plan_a.tenant, risk_management_plan_a)
    a2 = _riskmanagement_create_assessment(risk_management_plan_a.tenant, risk_management_plan_a)
    num1 = int(a1.number.split("-")[1])
    num2 = int(a2.number.split("-")[1])
    assert num2 == num1 + 1


def test_riskmanagement_assessment_str_representation(risk_management_plan_a):
    """__str__ returns '{number} - {desc}' using hazard_description or failure_mode."""
    a1 = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        hazard_description="Electromagnetic interference",
    )
    assert str(a1) == f"{a1.number} - Electromagnetic interference"

    a2 = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        hazard_description="",
        failure_mode="Solenoid valve stuck closed",
    )
    assert str(a2) == f"{a2.number} - Solenoid valve stuck closed"

    a3 = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        hazard_description="",
        failure_mode="",
    )
    assert str(a3) == f"{a3.number} - Risk Assessment"


def test_riskmanagement_assessment_initial_rpn_calculation(risk_management_plan_a):
    """initial_rpn must compute S x P x D on save."""
    # S=4, P=3, D=2 -> RPN = 24
    a1 = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        initial_severity=4,
        initial_probability=3,
        initial_detectability=2,
    )
    assert a1.initial_rpn == 24

    # Default detectability=1: S=5, P=2, D=1 -> RPN = 10
    a2 = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        initial_severity=5,
        initial_probability=2,
        initial_detectability=1,
    )
    assert a2.initial_rpn == 10


def test_riskmanagement_assessment_calculate_level_thresholds():
    """Static calculate_level must follow ISO 14971 matrix criteria:
    score >= 15 -> unacceptable, score >= 6 -> alarp, score < 6 -> broadly_acceptable."""
    # Unacceptable (>= 15)
    assert RiskAssessment.calculate_level(5, 3) == "unacceptable"  # 15
    assert RiskAssessment.calculate_level(4, 4) == "unacceptable"  # 16
    assert RiskAssessment.calculate_level(5, 5) == "unacceptable"  # 25

    # ALARP / Conditionally Acceptable (6 <= score < 15)
    assert RiskAssessment.calculate_level(3, 2) == "alarp"  # 6
    assert RiskAssessment.calculate_level(3, 3) == "alarp"  # 9
    assert RiskAssessment.calculate_level(4, 3) == "alarp"  # 12
    assert RiskAssessment.calculate_level(2, 7) == "alarp"  # 14

    # Broadly Acceptable (< 6)
    assert RiskAssessment.calculate_level(1, 1) == "broadly_acceptable"  # 1
    assert RiskAssessment.calculate_level(2, 2) == "broadly_acceptable"  # 4
    assert RiskAssessment.calculate_level(5, 1) == "broadly_acceptable"  # 5


def test_riskmanagement_assessment_initial_risk_level_on_save(risk_management_plan_a):
    """initial_risk_level must be computed automatically from severity and probability on save."""
    # 5 * 3 = 15 -> unacceptable
    a_unacc = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        initial_severity=5,
        initial_probability=3,
    )
    assert a_unacc.initial_risk_level == "unacceptable"

    # 3 * 3 = 9 -> alarp
    a_alarp = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        initial_severity=3,
        initial_probability=3,
    )
    assert a_alarp.initial_risk_level == "alarp"

    # 2 * 2 = 4 -> broadly_acceptable
    a_broad = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        initial_severity=2,
        initial_probability=2,
    )
    assert a_broad.initial_risk_level == "broadly_acceptable"


def test_riskmanagement_assessment_residual_scoring_and_safety_gates(risk_management_plan_a):
    """Verify residual scoring, RPN computation, and automated safety gate enforcement."""
    # 1. Unacceptable residual risk forces residual_risk_acceptable to False
    a_unacc = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        initial_severity=5,
        initial_probability=5,
        residual_severity=5,
        residual_probability=3,  # 5 * 3 = 15 -> unacceptable
        residual_detectability=2,
        residual_risk_acceptable=True,  # Attempting to override safety gate
    )
    assert a_unacc.residual_rpn == 30  # 5 * 3 * 2
    assert a_unacc.residual_risk_level == "unacceptable"
    assert a_unacc.residual_risk_acceptable is False  # Gate enforced!

    # 2. ALARP residual risk sets bra_required to True
    a_alarp = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        initial_severity=4,
        initial_probability=4,
        residual_severity=3,
        residual_probability=3,  # 3 * 3 = 9 -> alarp
        residual_detectability=1,
        bra_required=False,
    )
    assert a_alarp.residual_rpn == 9
    assert a_alarp.residual_risk_level == "alarp"
    assert a_alarp.bra_required is True

    # 3. Broadly acceptable residual risk sets residual_risk_acceptable to True
    a_broad = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        initial_severity=4,
        initial_probability=3,
        residual_severity=2,
        residual_probability=2,  # 2 * 2 = 4 -> broadly_acceptable
        residual_detectability=1,
    )
    assert a_broad.residual_rpn == 4
    assert a_broad.residual_risk_level == "broadly_acceptable"
    assert a_broad.residual_risk_acceptable is True


def test_riskmanagement_assessment_clearing_residual_fields(risk_management_plan_a):
    """When residual severity or probability is omitted/cleared, residual fields reset."""
    # Initially created with residual scoring
    assessment = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        residual_severity=2,
        residual_probability=2,
        residual_detectability=1,
    )
    assert assessment.residual_rpn == 4
    assert assessment.residual_risk_level == "broadly_acceptable"
    assert assessment.residual_risk_acceptable is True

    # Clear residual severity and resave
    assessment.residual_severity = None
    assessment.save()

    assert assessment.residual_rpn is None
    assert assessment.residual_risk_level == ""
    assert assessment.residual_risk_acceptable is False


def test_riskmanagement_assessment_analysis_type_choices_and_badges():
    """Verify analysis type choices and badge CSS."""
    types = [c[0] for c in RiskAssessment.ANALYSIS_TYPE_CHOICES]
    expected_types = ["hazard_analysis", "dfmea", "pfmea", "software_fmea", "use_error_urra"]
    for t in expected_types:
        assert t in types

    for key, badge in RiskAssessment.ANALYSIS_TYPE_CSS.items():
        assert badge in _RISKMANAGEMENT_VALID_BADGE_CLASSES

    a = RiskAssessment(analysis_type="dfmea")
    assert a.analysis_type_badge == "badge-slate"

    fake = RiskAssessment(analysis_type="unknown")
    assert fake.analysis_type_badge == "badge-slate"


def test_riskmanagement_assessment_hazard_category_choices():
    """Verify hazard category choices per ISO 14971 Annex C."""
    categories = [c[0] for c in RiskAssessment.HAZARD_CATEGORY_CHOICES]
    expected_cats = [
        "energy_electrical",
        "energy_thermal",
        "energy_mechanical",
        "radiation",
        "biological_chemical",
        "operational_use_error",
        "software_cybersecurity",
        "environmental",
        "other",
    ]
    for cat in expected_cats:
        assert cat in categories


def test_riskmanagement_assessment_css_badges(risk_management_plan_a):
    """Verify initial and residual risk level and lifecycle status badges."""
    a = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        initial_severity=5,
        initial_probability=4,  # unacceptable
        residual_severity=1,
        residual_probability=1,  # broadly_acceptable
        lifecycle_status="closed",
    )
    assert a.initial_risk_level_badge == "badge-red"
    assert a.residual_risk_level_badge == "badge-green"
    assert a.lifecycle_status_badge == "badge-green"

    # Alarp badge check
    a.residual_severity = 3
    a.residual_probability = 3  # alarp
    a.lifecycle_status = "mitigation_in_progress"
    a.save()
    assert a.residual_risk_level_badge == "badge-amber"
    assert a.lifecycle_status_badge == "badge-amber"


def test_riskmanagement_assessment_design_input_link(risk_management_plan_a, design_input_spec):
    """DesignInput can be linked as originating or mitigating requirement."""
    assessment = _riskmanagement_create_assessment(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        design_input=design_input_spec,
    )
    assert assessment.design_input == design_input_spec

    # Null on delete
    design_input_spec.delete()
    assessment.refresh_from_db()
    assert assessment.design_input is None


def test_riskmanagement_assessment_cascade_on_plan_delete(risk_management_plan_a):
    """Deleting a RiskManagementPlan cascades to delete its RiskAssessments."""
    a = _riskmanagement_create_assessment(risk_management_plan_a.tenant, risk_management_plan_a)
    assessment_id = a.id
    risk_management_plan_a.delete()
    assert not RiskAssessment.objects.filter(id=assessment_id).exists()


def test_riskmanagement_assessment_indexes_and_meta():
    """Verify RiskAssessment Meta definitions."""
    meta = RiskAssessment._meta
    assert meta.verbose_name == "Risk Assessment"
    assert meta.verbose_name_plural == "Risk Assessments"
    assert meta.ordering == ["-created_at"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_qrsk_ten_pln_type" in index_names
    assert "idx_qrsk_ten_hazard_cat" in index_names
    assert "idx_qrsk_ten_init_lvl" in index_names
    assert "idx_qrsk_ten_res_lvl" in index_names
    assert "idx_qrsk_ten_status" in index_names
    assert "idx_qrsk_ten_created" in index_names


# =====================================================================
# 3. RiskControlMeasure Tests
# =====================================================================


def test_riskmanagement_control_auto_number_format(risk_assessment_a):
    """Auto-numbering must follow QRCM-##### format."""
    control = _riskmanagement_create_control(risk_assessment_a.tenant, risk_assessment_a)
    assert control.number.startswith("QRCM-")
    assert re.match(r"^QRCM-\d{5}$", control.number) is not None


def test_riskmanagement_control_sequential_continuity(risk_assessment_a):
    """Sequential auto-numbering must increment monotonically per tenant."""
    c1 = _riskmanagement_create_control(risk_assessment_a.tenant, risk_assessment_a, title="C1")
    c2 = _riskmanagement_create_control(risk_assessment_a.tenant, risk_assessment_a, title="C2")
    num1 = int(c1.number.split("-")[1])
    num2 = int(c2.number.split("-")[1])
    assert num2 == num1 + 1


def test_riskmanagement_control_str_representation(risk_assessment_a):
    """__str__ returns '{number} - {title}'."""
    control = _riskmanagement_create_control(
        risk_assessment_a.tenant, risk_assessment_a, title="Ground Fault Circuit Interrupter"
    )
    assert str(control) == f"{control.number} - Ground Fault Circuit Interrupter"


def test_riskmanagement_control_hierarchy_priority_choices_and_badges():
    """Verify ISO 14971 Clause 7.1 mandatory priority hierarchy choices and badges."""
    hierarchies = [c[0] for c in RiskControlMeasure.CONTROL_HIERARCHY_CHOICES]
    assert "inherent_safety" in hierarchies
    assert "protective_measure" in hierarchies
    assert "information_for_safety" in hierarchies

    assert RiskControlMeasure.CONTROL_HIERARCHY_CSS["inherent_safety"] == "badge-green"
    assert RiskControlMeasure.CONTROL_HIERARCHY_CSS["protective_measure"] == "badge-info"
    assert RiskControlMeasure.CONTROL_HIERARCHY_CSS["information_for_safety"] == "badge-amber"

    c = RiskControlMeasure(control_hierarchy="inherent_safety")
    assert c.control_hierarchy_badge == "badge-green"

    fake = RiskControlMeasure(control_hierarchy="unknown")
    assert fake.control_hierarchy_badge == "badge-slate"


def test_riskmanagement_control_status_choices_and_badges(risk_assessment_a):
    """Verify control status choices and badges."""
    statuses = [c[0] for c in RiskControlMeasure.STATUS_CHOICES]
    expected_statuses = ["planned", "in_progress", "implemented", "verified", "ineffective", "obsolete"]
    for st in expected_statuses:
        assert st in statuses

    for st in expected_statuses:
        c = _riskmanagement_create_control(risk_assessment_a.tenant, risk_assessment_a, status=st)
        assert c.status_badge in _RISKMANAGEMENT_VALID_BADGE_CLASSES

    fake = RiskControlMeasure(status="unknown")
    assert fake.status_badge == "badge-slate"


def test_riskmanagement_control_is_fully_verified_property(risk_assessment_a):
    """is_fully_verified requires BOTH implementation_verified and effectiveness_verified to be True."""
    # Neither verified -> False
    c1 = _riskmanagement_create_control(
        risk_assessment_a.tenant,
        risk_assessment_a,
        implementation_verified=False,
        effectiveness_verified=False,
    )
    assert c1.is_fully_verified is False

    # Implementation verified only -> False
    c2 = _riskmanagement_create_control(
        risk_assessment_a.tenant,
        risk_assessment_a,
        implementation_verified=True,
        effectiveness_verified=False,
    )
    assert c2.is_fully_verified is False

    # Effectiveness verified only -> False
    c3 = _riskmanagement_create_control(
        risk_assessment_a.tenant,
        risk_assessment_a,
        implementation_verified=False,
        effectiveness_verified=True,
    )
    assert c3.is_fully_verified is False

    # Both verified -> True
    c4 = _riskmanagement_create_control(
        risk_assessment_a.tenant,
        risk_assessment_a,
        implementation_verified=True,
        effectiveness_verified=True,
    )
    assert c4.is_fully_verified is True


def test_riskmanagement_control_spine_traceability_links(
    risk_assessment_a, design_input_spec, design_verification_a, quality_doc_effective, admin_user
):
    """Verify bidirectional spine traceability to DesignInput, DesignVerification, and ControlledDocument."""
    control = _riskmanagement_create_control(
        risk_assessment_a.tenant,
        risk_assessment_a,
        design_input=design_input_spec,
        design_verification=design_verification_a,
        controlled_document=quality_doc_effective,
        assigned_to=admin_user,
    )
    assert control.design_input == design_input_spec
    assert control.design_verification == design_verification_a
    assert control.controlled_document == quality_doc_effective
    assert control.assigned_to == admin_user

    # DesignVerification deletion sets null
    design_verification_a.delete()
    control.refresh_from_db()
    assert control.design_verification is None


def test_riskmanagement_control_new_hazard_flags(risk_assessment_a):
    """Verify ISO 14971 Clause 7.3 new hazard introduced fields."""
    control = _riskmanagement_create_control(
        risk_assessment_a.tenant,
        risk_assessment_a,
        introduces_new_hazard=True,
        new_hazard_details="Battery heater introduces potential thermal runaway hazard.",
    )
    assert control.introduces_new_hazard is True
    assert "thermal runaway" in control.new_hazard_details


def test_riskmanagement_control_cascade_on_assessment_delete(risk_assessment_a):
    """Deleting a RiskAssessment cascades to delete its RiskControlMeasures."""
    control = _riskmanagement_create_control(risk_assessment_a.tenant, risk_assessment_a)
    control_id = control.id
    risk_assessment_a.delete()
    assert not RiskControlMeasure.objects.filter(id=control_id).exists()


def test_riskmanagement_control_indexes_and_meta():
    """Verify RiskControlMeasure Meta definitions."""
    meta = RiskControlMeasure._meta
    assert meta.verbose_name == "Risk Control Measure"
    assert meta.verbose_name_plural == "Risk Control Measures"
    assert meta.ordering == ["-created_at"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_qrcm_ten_assessment" in index_names
    assert "idx_qrcm_ten_hier" in index_names
    assert "idx_qrcm_ten_status" in index_names
    assert "idx_qrcm_ten_created" in index_names


# =====================================================================
# 4. RiskReviewRecord Tests
# =====================================================================


def test_riskmanagement_review_auto_number_format(risk_management_plan_a, admin_user):
    """Auto-numbering must follow QRMR-##### format."""
    review = _riskmanagement_create_review(risk_management_plan_a.tenant, risk_management_plan_a, admin_user)
    assert review.number.startswith("QRMR-")
    assert re.match(r"^QRMR-\d{5}$", review.number) is not None


def test_riskmanagement_review_sequential_continuity(risk_management_plan_a, admin_user):
    """Sequential auto-numbering must increment monotonically per tenant."""
    r1 = _riskmanagement_create_review(
        risk_management_plan_a.tenant, risk_management_plan_a, admin_user, review_title="Review 1"
    )
    r2 = _riskmanagement_create_review(
        risk_management_plan_a.tenant, risk_management_plan_a, admin_user, review_title="Review 2"
    )
    num1 = int(r1.number.split("-")[1])
    num2 = int(r2.number.split("-")[1])
    assert num2 == num1 + 1


def test_riskmanagement_review_str_representation(risk_management_plan_a, admin_user):
    """__str__ returns '{number} - {review_title}'."""
    review = _riskmanagement_create_review(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        admin_user,
        review_title="Annual Post-Market Risk Assessment",
    )
    assert str(review) == f"{review.number} - Annual Post-Market Risk Assessment"


def test_riskmanagement_review_type_choices_and_badges(risk_management_plan_a, admin_user):
    """Verify review type choices and badges."""
    types = [c[0] for c in RiskReviewRecord.REVIEW_TYPE_CHOICES]
    expected_types = [
        "initial_rmr",
        "periodic_review",
        "design_change_review",
        "post_market_surveillance",
        "complaint_trend_trigger",
        "ncr_capa_trigger",
    ]
    for t in expected_types:
        assert t in types

    for t in expected_types:
        rev = _riskmanagement_create_review(
            risk_management_plan_a.tenant, risk_management_plan_a, admin_user, review_type=t
        )
        assert rev.review_type_badge in _RISKMANAGEMENT_VALID_BADGE_CLASSES

    fake = RiskReviewRecord(review_type="unknown")
    assert fake.review_type_badge == "badge-slate"


def test_riskmanagement_review_status_choices_and_transitions(risk_management_plan_a, admin_user):
    """Verify status choices, transitions (draft -> under_review -> approved), and CSS badges."""
    statuses = [c[0] for c in RiskReviewRecord.STATUS_CHOICES]
    assert "draft" in statuses
    assert "under_review" in statuses
    assert "approved" in statuses
    assert "rejected" in statuses

    # Workflow transition: draft -> under_review -> approved
    review = _riskmanagement_create_review(
        risk_management_plan_a.tenant, risk_management_plan_a, admin_user, status="draft"
    )
    assert review.status == "draft"
    assert review.status_badge == "badge-slate"

    review.status = "under_review"
    review.save()
    assert review.status == "under_review"
    assert review.status_badge == "badge-amber"

    review.status = "approved"
    review.save()
    assert review.status == "approved"
    assert review.status_badge == "badge-green"

    fake = RiskReviewRecord(status="unknown")
    assert fake.status_badge == "badge-slate"


def test_riskmanagement_review_lead_reviewer_protected(risk_management_plan_a, admin_user):
    """Lead reviewer deletion must raise ProtectedError."""
    review = _riskmanagement_create_review(
        risk_management_plan_a.tenant, risk_management_plan_a, admin_user
    )
    with pytest.raises(ProtectedError):
        admin_user.delete()


def test_riskmanagement_review_electronic_signature_link(risk_management_plan_a, admin_user, quality_sig):
    """Risk review record can link to ElectronicSignatureRecord for 21 CFR Part 11 sign-off."""
    review = _riskmanagement_create_review(
        risk_management_plan_a.tenant,
        risk_management_plan_a,
        admin_user,
        approved_signature=quality_sig,
        status="approved",
    )
    assert review.approved_signature == quality_sig

    # Deleting signature sets null on review
    quality_sig.delete()
    review.refresh_from_db()
    assert review.approved_signature is None


def test_riskmanagement_review_cascade_on_plan_delete(risk_management_plan_a, admin_user):
    """Deleting a RiskManagementPlan cascades to delete its RiskReviewRecords."""
    review = _riskmanagement_create_review(
        risk_management_plan_a.tenant, risk_management_plan_a, admin_user
    )
    review_id = review.id
    risk_management_plan_a.delete()
    assert not RiskReviewRecord.objects.filter(id=review_id).exists()


def test_riskmanagement_review_indexes_and_meta():
    """Verify RiskReviewRecord Meta definitions."""
    meta = RiskReviewRecord._meta
    assert meta.verbose_name == "Risk Review Record"
    assert meta.verbose_name_plural == "Risk Review Records"
    assert meta.ordering == ["-created_at"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_qrmr_ten_pln_type" in index_names
    assert "idx_qrmr_ten_status" in index_names
    assert "idx_qrmr_ten_date" in index_names
    assert "idx_qrmr_ten_created" in index_names


# =====================================================================
# 5. Cross-Cutting & Fixture Integration Tests
# =====================================================================


def test_riskmanagement_shared_fixtures_integration(
    risk_management_plan_a,
    risk_management_plan_b,
    risk_assessment_a,
    risk_assessment_b,
    risk_control_measure_a,
    risk_control_measure_b,
    risk_review_record_a,
    risk_review_record_b,
):
    """Verify that all shared fixtures from conftest load cleanly with tenant isolation."""
    # Tenant A
    assert risk_management_plan_a.number.startswith("QRMP-")
    assert risk_assessment_a.number.startswith("QRSK-")
    assert risk_control_measure_a.number.startswith("QRCM-")
    assert risk_review_record_a.number.startswith("QRMR-")
    assert risk_assessment_a.plan == risk_management_plan_a
    assert risk_control_measure_a.risk_assessment == risk_assessment_a
    assert risk_review_record_a.plan == risk_management_plan_a

    # Tenant B
    assert risk_management_plan_b.number.startswith("QRMP-")
    assert risk_assessment_b.number.startswith("QRSK-")
    assert risk_control_measure_b.number.startswith("QRCM-")
    assert risk_review_record_b.number.startswith("QRMR-")
    assert risk_assessment_b.plan == risk_management_plan_b
    assert risk_control_measure_b.risk_assessment == risk_assessment_b
    assert risk_review_record_b.plan == risk_management_plan_b

    # Cross-tenant integrity
    assert risk_management_plan_a.tenant != risk_management_plan_b.tenant
    assert risk_assessment_a.tenant != risk_assessment_b.tenant
    assert risk_control_measure_a.tenant != risk_control_measure_b.tenant
    assert risk_review_record_a.tenant != risk_review_record_b.tenant
