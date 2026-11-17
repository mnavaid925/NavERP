"""
Unit tests for apps/quality forms (Sub-module 12.3: Risk Management - ISO 14971 / FMEA).

Covers:
- RiskManagementPlanForm:
  - System field exclusion (tenant, number, approved_signature, created_at, updated_at).
  - Valid submission and minimal submission with sensible defaults.
  - Required fields validation (title, lead_risk_manager, scope_description, risk_acceptability_policy).
  - Foreign key tenant scoping in __init__ (department, design_project, lead_risk_manager).
  - Inactive users exclusion from lead_risk_manager choices.
  - Empty querysets when instantiated with tenant=None.
  - Cross-tenant injection rejection via reject_foreign and ModelChoiceField.
  - Date validations (valid ISO date, empty date, invalid date string error).
  - Choice fields validation (device_classification, matrix_dimension, status).
  - Widget CSS classes (form-input, form-select, form-textarea, form-checkbox, type="date").
  - Form save persistence with QRMP- auto-number and tenant attachment.
- RiskAssessmentForm:
  - System field exclusion (tenant, number, initial_rpn, initial_risk_level, residual_rpn, residual_risk_level, created_at, updated_at).
  - Valid submission with initial severity, probability, detectability scores.
  - Required fields validation (plan, hazard_description, hazardous_situation, potential_harm).
  - Severity and probability numeric bounds & choice validation (1 to 5).
  - ISO 14971 Safety Gate validations:
    - Rejection of residual_risk_acceptable=True when calculated residual risk level is "unacceptable" (S x P >= 15).
    - Acceptance of residual_risk_acceptable=False in "unacceptable" zone without error.
    - Requirement of benefit_risk_justification when in ALARP zone (6 <= S x P < 15) and residual_risk_acceptable=True.
    - Acceptance of residual_risk_acceptable=True in ALARP zone when benefit_risk_justification is provided.
    - Acceptance of residual_risk_acceptable=False in ALARP zone without benefit_risk_justification.
    - Broadly acceptable zone (S x P < 6) where residual_risk_acceptable=True requires no justification.
  - Foreign key tenant scoping in __init__ (plan, design_input).
  - Empty querysets when instantiated without tenant.
  - Cross-tenant injection rejection via reject_foreign.
  - Choice validation (analysis_type, hazard_category, lifecycle_status).
  - Widget CSS classes and form save persistence with QRSK- auto-number.
- RiskControlMeasureForm:
  - System field exclusion (tenant, number, created_at, updated_at).
  - Valid submission with control hierarchy and planned status.
  - Required fields validation (risk_assessment, title, description).
  - Control hierarchy priority choices (inherent_safety, protective_measure, information_for_safety).
  - Status choices validation.
  - ISO 14971 Clause 7.2 Verification validations:
    - Requires verification_notes or design_verification when implementation_verified=True.
    - Requires verification_notes or design_verification when effectiveness_verified=True.
    - Valid when verification_notes provided alone.
    - Valid when design_verification protocol provided alone.
    - Valid when neither verified flag is checked.
  - Cross-project consistency check:
    - Rejects design_input belonging to a different project than risk_assessment.plan.design_project.
    - Valid when design_input belongs to matching project.
    - Valid when either plan.design_project or design_input.project is None.
  - Foreign key tenant scoping in __init__ (risk_assessment, assigned_to, design_input, controlled_document, design_verification).
  - Inactive users exclusion from assigned_to.
  - Empty querysets when instantiated without tenant.
  - Cross-tenant injection rejection via reject_foreign.
  - Widget CSS classes and form save persistence with QRCM- auto-number.
- RiskReviewRecordForm:
  - System field exclusion (tenant, number, approved_signature, created_at, updated_at).
  - Valid submission with review types and draft status.
  - Required fields validation (plan, review_title, review_date, findings_summary, lead_reviewer).
  - Status restrictions:
    - Status choices in __init__ strictly restricted to ("draft", "under_review").
    - Clean method rejects status="approved" directly in form (approval requires formal sign-off).
    - Clean method rejects status="rejected".
    - Allows status="draft" and status="under_review".
  - Review type choices validation (initial_rmr, periodic_review, post_market_surveillance, etc.).
  - Date validations (review_date, review_period_start, review_period_end).
  - Foreign key tenant scoping in __init__ (plan, lead_reviewer).
  - Empty querysets when instantiated without tenant.
  - Cross-tenant injection rejection via reject_foreign.
  - Widget CSS classes and form save persistence with QRMR- auto-number.
"""

from datetime import timedelta
import pytest
from django import forms
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.quality.forms import (
    RiskAssessmentForm,
    RiskControlMeasureForm,
    RiskManagementPlanForm,
    RiskReviewRecordForm,
)
from apps.quality.forms._common import reject_foreign
from apps.quality.models import (
    ControlledDocument,
    DesignInput,
    DesignProject,
    DesignVerification,
    RiskAssessment,
    RiskControlMeasure,
    RiskManagementPlan,
    RiskReviewRecord,
)

pytestmark = pytest.mark.django_db


# =====================================================================
# Fixtures and Helpers (Prefix: _riskmanagement_*)
# =====================================================================


def _riskmanagement_pk(val):
    """Return pk if val is a model instance, or val itself if already a scalar / None."""
    if val is None or val == "":
        return ""
    return getattr(val, "pk", val)


def _riskmanagement_plan_base_data(manager, project=None, department=None, **extra):
    """Build valid baseline POST dictionary for RiskManagementPlanForm."""
    data = {
        "title": "InfuseFlow Pro 3000 Risk Management Plan",
        "plan_version": "1.0",
        "status": "draft",
        "design_project": _riskmanagement_pk(project),
        "lead_risk_manager": _riskmanagement_pk(manager),
        "department": _riskmanagement_pk(department),
        "device_classification": "class_ii_a",
        "scope_description": "Comprehensive ISO 14971 risk management lifecycle for infusion pump system.",
        "matrix_dimension": "5x5",
        "risk_acceptability_policy": "Broadly acceptable if RPN < 6; ALARP between 6 and 14 with clinical BRA justification.",
        "overall_residual_risk_acceptable": False,
        "overall_benefit_risk_summary": "Initial scoping phase clinical benefit-risk summary.",
        "periodic_review_frequency_months": 12,
        "next_review_due_date": (timezone.now() + timedelta(days=365)).date().isoformat(),
    }
    data.update(extra)
    return data


def _riskmanagement_assessment_base_data(plan, design_input=None, **extra):
    """Build valid baseline POST dictionary for RiskAssessmentForm."""
    data = {
        "plan": _riskmanagement_pk(plan),
        "analysis_type": "hazard_analysis",
        "hazard_category": "energy_electrical",
        "hazard_description": "High voltage creepage across power supply barrier",
        "hazardous_situation": "Patient or operator touches exposed energized chassis",
        "foreseeable_sequence_of_events": "Transformer insulation failure allows mains AC onto secondary DC bus",
        "potential_harm": "Ventricular fibrillation or cardiac arrest",
        "item_function": "Power Supply Isolation Unit",
        "failure_mode": "Dielectric breakdown",
        "failure_cause": "Component overvoltage degradation",
        "failure_effect": "Loss of electrical isolation to enclosure",
        "initial_severity": 4,
        "initial_probability": 3,
        "initial_detectability": 1,
        "residual_severity": "",
        "residual_probability": "",
        "residual_detectability": "",
        "residual_risk_acceptable": False,
        "bra_required": False,
        "benefit_risk_justification": "",
        "disclosed_in_ifu": False,
        "design_input": _riskmanagement_pk(design_input),
        "lifecycle_status": "open",
    }
    data.update(extra)
    return data


def _riskmanagement_control_base_data(
    risk_assessment,
    assigned_user=None,
    design_input=None,
    doc=None,
    verification=None,
    **extra,
):
    """Build valid baseline POST dictionary for RiskControlMeasureForm."""
    data = {
        "risk_assessment": _riskmanagement_pk(risk_assessment),
        "control_hierarchy": "inherent_safety",
        "title": "Dual Galvanic Isolation Transformers",
        "description": "Implement 4kV reinforced isolation transformer meeting IEC 60601-1.",
        "assigned_to": _riskmanagement_pk(assigned_user),
        "due_date": (timezone.now() + timedelta(days=60)).date().isoformat(),
        "status": "planned",
        "design_input": _riskmanagement_pk(design_input),
        "controlled_document": _riskmanagement_pk(doc),
        "design_verification": _riskmanagement_pk(verification),
        "implementation_verified": False,
        "effectiveness_verified": False,
        "verification_notes": "",
        "introduces_new_hazard": False,
        "new_hazard_details": "",
    }
    data.update(extra)
    return data


def _riskmanagement_review_base_data(plan, reviewer, **extra):
    """Build valid baseline POST dictionary for RiskReviewRecordForm."""
    data = {
        "plan": _riskmanagement_pk(plan),
        "review_title": "Annual Post-Market Risk Management Review",
        "review_type": "periodic_review",
        "review_date": timezone.now().date().isoformat(),
        "review_period_start": (timezone.now() - timedelta(days=365)).date().isoformat(),
        "review_period_end": timezone.now().date().isoformat(),
        "pms_sources_reviewed": "Reviewed 12 complaints, 0 adverse events, and 3 internal non-conformances.",
        "new_hazards_identified": False,
        "risk_profile_changed": False,
        "overall_residual_risk_reconfirmed": True,
        "findings_summary": "All residual risks remain within acceptable criteria defined in the risk plan.",
        "action_items_required": "",
        "status": "draft",
        "lead_reviewer": _riskmanagement_pk(reviewer),
    }
    data.update(extra)
    return data


def _riskmanagement_create_user(tenant, username, email, is_active=True):
    """Helper creating a test user under a given tenant."""
    return User.objects.create_user(
        username=username,
        email=email,
        password="TestPassword123!",
        tenant=tenant,
        is_active=is_active,
    )


def _riskmanagement_create_alt_project(tenant, lead_user, dept=None, suffix="002"):
    """Helper creating a secondary DesignProject under a tenant for cross-project testing."""
    return DesignProject.objects.create(
        tenant=tenant,
        title=f"Secondary Infusion Device {suffix}",
        device_name=f"InfuseMini {suffix}",
        device_class="class_ii_b",
        regulatory_pathway="510k",
        intended_use="Ambulatory infusion pump system.",
        current_phase="design_input",
        status="active",
        project_lead=lead_user,
        quality_lead=lead_user,
        department=dept,
        dhf_locked=False,
    )


def _riskmanagement_create_alt_input(tenant, project, user, identifier="DI-ALT-001"):
    """Helper creating an alternate DesignInput for a project."""
    return DesignInput.objects.create(
        tenant=tenant,
        project=project,
        identifier=identifier,
        title=f"Alternate Requirement {identifier}",
        input_type="functional",
        priority="high",
        status="approved",
        owner=user,
        acceptance_criteria="Alternative criteria for cross-project verification testing.",
    )


# =====================================================================
# 1. System Field Exclusion Tests across All 4 Forms
# =====================================================================


def test_riskmanagement_forms_plan_system_field_exclusion(tenant_a, admin_user):
    """Verify tenant, number, approved_signature, created_at, updated_at are excluded from RiskManagementPlanForm."""
    form = RiskManagementPlanForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "approved_signature", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from RiskManagementPlanForm"

    # Injected values in POST data must not bind to instance attributes
    malicious_data = _riskmanagement_plan_base_data(
        admin_user,
        tenant=tenant_a.pk,
        number="QRMP-HACKED-9999",
        approved_signature=999,
    )
    bound_form = RiskManagementPlanForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QRMP-HACKED-9999"
    assert getattr(instance, "approved_signature_id", None) is None


def test_riskmanagement_forms_assessment_system_field_exclusion(tenant_a, risk_management_plan_a):
    """Verify tenant, number, RPN & level computed fields, created_at, updated_at are excluded from RiskAssessmentForm."""
    form = RiskAssessmentForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "initial_rpn",
        "initial_risk_level",
        "residual_rpn",
        "residual_risk_level",
        "created_at",
        "updated_at",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from RiskAssessmentForm"

    malicious_data = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        tenant=tenant_a.pk,
        number="QRSK-HACKED-001",
        initial_rpn=999,
        initial_risk_level="broadly_acceptable",
    )
    bound_form = RiskAssessmentForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QRSK-HACKED-001"


def test_riskmanagement_forms_control_system_field_exclusion(tenant_a, risk_assessment_a):
    """Verify tenant, number, created_at, updated_at are excluded from RiskControlMeasureForm."""
    form = RiskControlMeasureForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from RiskControlMeasureForm"

    malicious_data = _riskmanagement_control_base_data(
        risk_assessment_a,
        tenant=tenant_a.pk,
        number="QRCM-HACKED-777",
    )
    bound_form = RiskControlMeasureForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QRCM-HACKED-777"


def test_riskmanagement_forms_review_system_field_exclusion(tenant_a, risk_management_plan_a, admin_user):
    """Verify tenant, number, approved_signature, created_at, updated_at are excluded from RiskReviewRecordForm."""
    form = RiskReviewRecordForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "approved_signature", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from RiskReviewRecordForm"

    malicious_data = _riskmanagement_review_base_data(
        risk_management_plan_a,
        admin_user,
        tenant=tenant_a.pk,
        number="QRMR-HACKED-111",
        approved_signature=123,
    )
    bound_form = RiskReviewRecordForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QRMR-HACKED-111"
    assert getattr(instance, "approved_signature_id", None) is None


# =====================================================================
# 2. RiskManagementPlanForm Tests
# =====================================================================


def test_riskmanagement_forms_plan_valid_submission(
    tenant_a, admin_user, design_project_a, quality_department
):
    """Submitting valid RiskManagementPlanForm persists record with tenant, QRMP- auto-number, and FK associations."""
    data = _riskmanagement_plan_base_data(
        admin_user,
        project=design_project_a,
        department=quality_department,
        title="Comprehensive InfuseFlow Pro 3000 Risk Plan",
        plan_version="2.0",
        status="active",
        device_classification="class_ii_b",
        matrix_dimension="5x5",
        periodic_review_frequency_months=6,
    )
    form = RiskManagementPlanForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    plan = form.save()

    assert plan.pk is not None
    assert plan.tenant == tenant_a
    assert plan.number.startswith("QRMP-")
    assert plan.title == "Comprehensive InfuseFlow Pro 3000 Risk Plan"
    assert plan.plan_version == "2.0"
    assert plan.status == "active"
    assert plan.device_classification == "class_ii_b"
    assert plan.lead_risk_manager == admin_user
    assert plan.design_project == design_project_a
    assert plan.department == quality_department
    assert plan.periodic_review_frequency_months == 6


def test_riskmanagement_forms_plan_minimal_valid_submission(tenant_a, admin_user):
    """Submitting required fields while omitting optional FKs and dates creates a valid plan."""
    data = {
        "title": "Minimal Risk Scoping Plan",
        "plan_version": "1.0",
        "status": "draft",
        "lead_risk_manager": admin_user.pk,
        "device_classification": "class_ii_a",
        "scope_description": "Initial hazard identification scope.",
        "matrix_dimension": "5x5",
        "risk_acceptability_policy": "ISO 14971 baseline policy.",
        "periodic_review_frequency_months": 12,
        # Omitted optional fields: design_project, department, next_review_due_date, overall_benefit_risk_summary
    }
    form = RiskManagementPlanForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    plan = form.save()

    assert plan.pk is not None
    assert plan.tenant == tenant_a
    assert plan.number.startswith("QRMP-")
    assert plan.plan_version == "1.0"
    assert plan.status == "draft"
    assert plan.device_classification == "class_ii_a"
    assert plan.matrix_dimension == "5x5"
    assert plan.design_project is None
    assert plan.department is None
    assert plan.next_review_due_date is None


def test_riskmanagement_forms_plan_required_fields(tenant_a):
    """Leaving mandatory fields blank generates field validation errors."""
    form = RiskManagementPlanForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "lead_risk_manager" in form.errors
    assert "scope_description" in form.errors
    assert "risk_acceptability_policy" in form.errors


def test_riskmanagement_forms_plan_fk_tenant_scoping_dropdowns(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    design_project_a,
    design_project_b,
    quality_department,
    quality_department_b,
):
    """Dropdown querysets for lead_risk_manager, department, and design_project must be filtered by tenant."""
    form = RiskManagementPlanForm(tenant=tenant_a)

    lead_pks = list(form.fields["lead_risk_manager"].queryset.values_list("pk", flat=True))
    dept_pks = list(form.fields["department"].queryset.values_list("pk", flat=True))
    proj_pks = list(form.fields["design_project"].queryset.values_list("pk", flat=True))

    assert admin_user.pk in lead_pks
    assert admin_b.pk not in lead_pks
    assert quality_department.pk in dept_pks
    assert quality_department_b.pk not in dept_pks
    assert design_project_a.pk in proj_pks
    assert design_project_b.pk not in proj_pks


def test_riskmanagement_forms_plan_inactive_users_excluded(tenant_a, admin_user):
    """Inactive users under tenant must be excluded from lead_risk_manager queryset."""
    inactive_user = _riskmanagement_create_user(
        tenant_a, "inactive_lead", "inactive@acme.com", is_active=False
    )
    form = RiskManagementPlanForm(tenant=tenant_a)
    lead_pks = list(form.fields["lead_risk_manager"].queryset.values_list("pk", flat=True))

    assert admin_user.pk in lead_pks
    assert inactive_user.pk not in lead_pks


def test_riskmanagement_forms_plan_no_tenant_empty_querysets():
    """Instantiating RiskManagementPlanForm with tenant=None sets all FK querysets to none()."""
    form = RiskManagementPlanForm(tenant=None)
    assert form.fields["department"].queryset.count() == 0
    assert form.fields["design_project"].queryset.count() == 0
    assert form.fields["lead_risk_manager"].queryset.count() == 0


def test_riskmanagement_forms_plan_cross_tenant_rejection(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    design_project_a,
    design_project_b,
    quality_department_b,
):
    """Submitting foreign department, foreign design_project, or foreign manager fails validation."""
    # Submitting department belonging to tenant_b
    data_bad_dept = _riskmanagement_plan_base_data(
        admin_user, project=design_project_a, department=quality_department_b
    )
    form_dept = RiskManagementPlanForm(data=data_bad_dept, tenant=tenant_a)
    assert not form_dept.is_valid()
    assert "department" in form_dept.errors

    # Submitting design_project belonging to tenant_b
    data_bad_proj = _riskmanagement_plan_base_data(admin_user, project=design_project_b)
    form_proj = RiskManagementPlanForm(data=data_bad_proj, tenant=tenant_a)
    assert not form_proj.is_valid()
    assert "design_project" in form_proj.errors

    # Submitting manager belonging to tenant_b
    data_bad_user = _riskmanagement_plan_base_data(admin_b, project=design_project_a)
    form_user = RiskManagementPlanForm(data=data_bad_user, tenant=tenant_a)
    assert not form_user.is_valid()
    assert "lead_risk_manager" in form_user.errors


def test_riskmanagement_forms_plan_reject_foreign_clean_direct(
    tenant_a, admin_b, design_project_b, quality_department_b
):
    """Directly verify reject_foreign helper adds workspace violation errors on RiskManagementPlanForm."""
    form = RiskManagementPlanForm(tenant=tenant_a)
    form.cleaned_data = {
        "department": quality_department_b,
        "design_project": design_project_b,
        "lead_risk_manager": admin_b,
    }
    reject_foreign(form, form.cleaned_data, ["department", "design_project", "lead_risk_manager"])
    assert "department" in form.errors
    assert "design_project" in form.errors
    assert "lead_risk_manager" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["department"])


def test_riskmanagement_forms_plan_date_validations(tenant_a, admin_user):
    """Verify next_review_due_date handles valid date, empty date, and invalid date formats."""
    # Valid date format
    data_valid = _riskmanagement_plan_base_data(
        admin_user, next_review_due_date="2027-06-30"
    )
    form_valid = RiskManagementPlanForm(data=data_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors
    plan = form_valid.save()
    assert plan.next_review_due_date.isoformat() == "2027-06-30"

    # Empty date format (optional field)
    data_empty = _riskmanagement_plan_base_data(admin_user, next_review_due_date="")
    form_empty = RiskManagementPlanForm(data=data_empty, tenant=tenant_a)
    assert form_empty.is_valid(), form_empty.errors
    plan_no_date = form_empty.save()
    assert plan_no_date.next_review_due_date is None

    # Invalid date format
    data_invalid = _riskmanagement_plan_base_data(
        admin_user, next_review_due_date="not-a-valid-date"
    )
    form_invalid = RiskManagementPlanForm(data=data_invalid, tenant=tenant_a)
    assert not form_invalid.is_valid()
    assert "next_review_due_date" in form_invalid.errors


def test_riskmanagement_forms_plan_choices_validation(tenant_a, admin_user):
    """Verify choices for device_classification, matrix_dimension, and status."""
    for valid_class in ["class_i", "class_ii_a", "class_ii_b", "class_iii", "samd", "non_medical"]:
        data = _riskmanagement_plan_base_data(admin_user, device_classification=valid_class)
        form = RiskManagementPlanForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Device classification '{valid_class}' should be valid: {form.errors}"

    for valid_matrix in ["3x3", "4x4", "5x5"]:
        data = _riskmanagement_plan_base_data(admin_user, matrix_dimension=valid_matrix)
        form = RiskManagementPlanForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Matrix dimension '{valid_matrix}' should be valid: {form.errors}"

    for valid_status in ["draft", "in_review", "active", "periodic_review", "superseded", "archived"]:
        data = _riskmanagement_plan_base_data(admin_user, status=valid_status)
        form = RiskManagementPlanForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Status '{valid_status}' should be valid: {form.errors}"

    # Invalid choices
    bad_data = _riskmanagement_plan_base_data(
        admin_user,
        device_classification="class_unknown",
        matrix_dimension="10x10",
        status="bogus_status",
    )
    bad_form = RiskManagementPlanForm(data=bad_data, tenant=tenant_a)
    assert not bad_form.is_valid()
    assert "device_classification" in bad_form.errors
    assert "matrix_dimension" in bad_form.errors
    assert "status" in bad_form.errors


def test_riskmanagement_forms_plan_widget_classes(tenant_a):
    """Verify all form widgets on RiskManagementPlanForm have correct CSS classes."""
    form = RiskManagementPlanForm(tenant=tenant_a)
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["plan_version"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["status"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["design_project"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["lead_risk_manager"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["department"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["device_classification"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["scope_description"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["matrix_dimension"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["risk_acceptability_policy"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["overall_residual_risk_acceptable"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["overall_benefit_risk_summary"].widget.attrs.get("class", "")
    assert (
        form.fields["next_review_due_date"].widget.attrs.get("type")
        or getattr(form.fields["next_review_due_date"].widget, "input_type", None)
    ) == "date"


# =====================================================================
# 3. RiskAssessmentForm Tests
# =====================================================================


def test_riskmanagement_forms_assessment_valid_creation(
    tenant_a, risk_management_plan_a, design_input_spec
):
    """Submitting valid RiskAssessmentForm persists assessment and computes RPN & level on save."""
    data = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        design_input=design_input_spec,
        hazard_description="Over-infusion due to sensor drift",
        hazardous_situation="Patient receives 2x prescribed narcotic rate",
        potential_harm="Respiratory arrest or hypoxic brain injury",
        initial_severity=5,
        initial_probability=3,
        initial_detectability=2,
    )
    form = RiskAssessmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assessment = form.save()

    assert assessment.pk is not None
    assert assessment.tenant == tenant_a
    assert assessment.number.startswith("QRSK-")
    assert assessment.plan == risk_management_plan_a
    assert assessment.design_input == design_input_spec
    assert assessment.initial_severity == 5
    assert assessment.initial_probability == 3
    assert assessment.initial_rpn == 5 * 3 * 2  # 30
    assert assessment.initial_risk_level == "unacceptable"


def test_riskmanagement_forms_assessment_required_fields(tenant_a):
    """Submitting empty data to RiskAssessmentForm triggers validation errors on required fields."""
    form = RiskAssessmentForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "plan" in form.errors
    assert "hazard_description" in form.errors
    assert "hazardous_situation" in form.errors
    assert "potential_harm" in form.errors


def test_riskmanagement_forms_assessment_severity_probability_bounds(
    tenant_a, risk_management_plan_a
):
    """Severity, probability, and detectability must respect 1-5 choices."""
    # Out-of-bounds numbers
    for bad_s in [0, 6, -1, 99]:
        data = _riskmanagement_assessment_base_data(
            risk_management_plan_a, initial_severity=bad_s
        )
        form = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "initial_severity" in form.errors

    for bad_p in [0, 6, -2, 10]:
        data = _riskmanagement_assessment_base_data(
            risk_management_plan_a, initial_probability=bad_p
        )
        form = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "initial_probability" in form.errors

    for bad_d in [0, 6, 99]:
        data = _riskmanagement_assessment_base_data(
            risk_management_plan_a, initial_detectability=bad_d
        )
        form = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "initial_detectability" in form.errors


def test_riskmanagement_forms_assessment_safety_gate_reject_unacceptable(
    tenant_a, risk_management_plan_a
):
    """Residual risk in Unacceptable zone (S x P >= 15) CANNOT be marked acceptable."""
    # S=5, P=3 => 15 (unacceptable), marked acceptable=True -> REJECTED
    data_unacceptable = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        residual_severity=5,
        residual_probability=3,
        residual_detectability=1,
        residual_risk_acceptable=True,
    )
    form_unacceptable = RiskAssessmentForm(data=data_unacceptable, tenant=tenant_a)
    assert not form_unacceptable.is_valid()
    assert "residual_risk_acceptable" in form_unacceptable.errors
    assert "Unacceptable zone" in str(form_unacceptable.errors["residual_risk_acceptable"])

    # S=4, P=4 => 16 (unacceptable), marked acceptable=True -> REJECTED
    data_unacceptable_44 = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        residual_severity=4,
        residual_probability=4,
        residual_detectability=1,
        residual_risk_acceptable=True,
    )
    form_unacceptable_44 = RiskAssessmentForm(data=data_unacceptable_44, tenant=tenant_a)
    assert not form_unacceptable_44.is_valid()
    assert "residual_risk_acceptable" in form_unacceptable_44.errors


def test_riskmanagement_forms_assessment_safety_gate_unacceptable_not_acceptable_valid(
    tenant_a, risk_management_plan_a
):
    """Residual risk in Unacceptable zone with residual_risk_acceptable=False is valid."""
    data = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        residual_severity=5,
        residual_probability=3,
        residual_detectability=1,
        residual_risk_acceptable=False,
    )
    form = RiskAssessmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assessment = form.save()
    assert assessment.residual_risk_level == "unacceptable"
    assert assessment.residual_risk_acceptable is False


def test_riskmanagement_forms_assessment_safety_gate_alarp_requires_bra_justification(
    tenant_a, risk_management_plan_a
):
    """Residual risk in ALARP zone (6 <= S x P < 15) marked acceptable REQUIRES benefit_risk_justification."""
    # S=3, P=3 => 9 (alarp), acceptable=True, but no justification -> REJECTED
    data_no_justification = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        residual_severity=3,
        residual_probability=3,
        residual_detectability=2,
        residual_risk_acceptable=True,
        benefit_risk_justification="",
    )
    form_no_just = RiskAssessmentForm(data=data_no_justification, tenant=tenant_a)
    assert not form_no_just.is_valid()
    assert "benefit_risk_justification" in form_no_just.errors
    assert "Benefit-Risk Analysis (BRA)" in str(form_no_just.errors["benefit_risk_justification"])

    # Whitespace-only justification is also rejected
    data_spaces = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        residual_severity=3,
        residual_probability=3,
        residual_detectability=2,
        residual_risk_acceptable=True,
        benefit_risk_justification="     \n  \t  ",
    )
    form_spaces = RiskAssessmentForm(data=data_spaces, tenant=tenant_a)
    assert not form_spaces.is_valid()
    assert "benefit_risk_justification" in form_spaces.errors


def test_riskmanagement_forms_assessment_safety_gate_alarp_with_justification_valid(
    tenant_a, risk_management_plan_a
):
    """Residual risk in ALARP zone marked acceptable WITH clinical justification is valid."""
    data = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        residual_severity=3,
        residual_probability=3,
        residual_detectability=2,
        residual_risk_acceptable=True,
        bra_required=True,
        benefit_risk_justification=(
            "Clinical evaluation report CER-2026 demonstrates therapeutic life-saving benefit "
            "of continuous infusion outweighs residual occlusion probability under fail-safe monitoring."
        ),
    )
    form = RiskAssessmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assessment = form.save()
    assert assessment.residual_risk_level == "alarp"
    assert assessment.residual_risk_acceptable is True
    assert assessment.bra_required is True


def test_riskmanagement_forms_assessment_safety_gate_alarp_acceptable_false_no_justification_valid(
    tenant_a, risk_management_plan_a
):
    """Residual risk in ALARP zone with residual_risk_acceptable=False does NOT require justification."""
    data = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        residual_severity=3,
        residual_probability=3,
        residual_detectability=2,
        residual_risk_acceptable=False,
        benefit_risk_justification="",
    )
    form = RiskAssessmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assessment = form.save()
    assert assessment.residual_risk_level == "alarp"


def test_riskmanagement_forms_assessment_broadly_acceptable_zone(
    tenant_a, risk_management_plan_a
):
    """Residual risk in Broadly Acceptable zone (S x P < 6) does not require BRA justification."""
    # S=2, P=2 => 4 (< 6 -> broadly_acceptable)
    data = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        residual_severity=2,
        residual_probability=2,
        residual_detectability=1,
        residual_risk_acceptable=True,
        benefit_risk_justification="",
    )
    form = RiskAssessmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assessment = form.save()
    assert assessment.residual_risk_level == "broadly_acceptable"
    assert assessment.residual_risk_acceptable is True


def test_riskmanagement_forms_assessment_fk_tenant_scoping_dropdowns(
    tenant_a,
    tenant_b,
    risk_management_plan_a,
    risk_management_plan_b,
    design_input_spec,
    design_input_b,
):
    """Dropdown querysets for plan and design_input must be filtered by tenant."""
    form = RiskAssessmentForm(tenant=tenant_a)
    plan_pks = list(form.fields["plan"].queryset.values_list("pk", flat=True))
    input_pks = list(form.fields["design_input"].queryset.values_list("pk", flat=True))

    assert risk_management_plan_a.pk in plan_pks
    assert risk_management_plan_b.pk not in plan_pks
    assert design_input_spec.pk in input_pks
    assert design_input_b.pk not in input_pks


def test_riskmanagement_forms_assessment_no_tenant_empty_querysets():
    """Instantiating RiskAssessmentForm with tenant=None sets querysets to none()."""
    form = RiskAssessmentForm(tenant=None)
    assert form.fields["plan"].queryset.count() == 0
    assert form.fields["design_input"].queryset.count() == 0


def test_riskmanagement_forms_assessment_cross_tenant_rejection(
    tenant_a,
    risk_management_plan_a,
    risk_management_plan_b,
    design_input_b,
):
    """Submitting foreign plan or foreign design_input fails validation."""
    # Submitting plan from tenant_b
    data_bad_plan = _riskmanagement_assessment_base_data(risk_management_plan_b)
    form_plan = RiskAssessmentForm(data=data_bad_plan, tenant=tenant_a)
    assert not form_plan.is_valid()
    assert "plan" in form_plan.errors

    # Submitting design_input from tenant_b
    data_bad_input = _riskmanagement_assessment_base_data(
        risk_management_plan_a, design_input=design_input_b
    )
    form_input = RiskAssessmentForm(data=data_bad_input, tenant=tenant_a)
    assert not form_input.is_valid()
    assert "design_input" in form_input.errors


def test_riskmanagement_forms_assessment_reject_foreign_clean_direct(
    tenant_a, risk_management_plan_b, design_input_b
):
    """Directly verify reject_foreign adds errors on RiskAssessmentForm for cross-tenant FKs."""
    form = RiskAssessmentForm(tenant=tenant_a)
    form.cleaned_data = {
        "plan": risk_management_plan_b,
        "design_input": design_input_b,
    }
    reject_foreign(form, form.cleaned_data, ["plan", "design_input"])
    assert "plan" in form.errors
    assert "design_input" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["plan"])


def test_riskmanagement_forms_assessment_choices_validation(tenant_a, risk_management_plan_a):
    """Verify analysis_type, hazard_category, and lifecycle_status choices validation."""
    for valid_type in ["hazard_analysis", "dfmea", "pfmea", "software_fmea", "use_error_urra"]:
        data = _riskmanagement_assessment_base_data(risk_management_plan_a, analysis_type=valid_type)
        form = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Analysis type '{valid_type}' should be valid"

    for valid_cat in [
        "energy_electrical",
        "energy_thermal",
        "energy_mechanical",
        "radiation",
        "biological_chemical",
        "operational_use_error",
        "software_cybersecurity",
        "environmental",
        "other",
    ]:
        data = _riskmanagement_assessment_base_data(risk_management_plan_a, hazard_category=valid_cat)
        form = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Hazard category '{valid_cat}' should be valid"

    bad_data = _riskmanagement_assessment_base_data(
        risk_management_plan_a,
        analysis_type="invalid_analysis",
        hazard_category="invalid_category",
        lifecycle_status="invalid_status",
    )
    bad_form = RiskAssessmentForm(data=bad_data, tenant=tenant_a)
    assert not bad_form.is_valid()
    assert "analysis_type" in bad_form.errors
    assert "hazard_category" in bad_form.errors
    assert "lifecycle_status" in bad_form.errors


def test_riskmanagement_forms_assessment_widget_classes(tenant_a):
    """Verify CSS widget classes on RiskAssessmentForm."""
    form = RiskAssessmentForm(tenant=tenant_a)
    assert "form-select" in form.fields["plan"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["analysis_type"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["hazard_category"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["hazard_description"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["hazardous_situation"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["potential_harm"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["initial_severity"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["initial_probability"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["initial_detectability"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["residual_risk_acceptable"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["benefit_risk_justification"].widget.attrs.get("class", "")


# =====================================================================
# 4. RiskControlMeasureForm Tests
# =====================================================================


def test_riskmanagement_forms_control_valid_creation(
    tenant_a,
    risk_assessment_a,
    admin_user,
    design_input_spec,
    design_verification_a,
    quality_doc_effective,
):
    """Submitting valid RiskControlMeasureForm persists mitigation linked to design spine."""
    data = _riskmanagement_control_base_data(
        risk_assessment_a,
        assigned_user=admin_user,
        design_input=design_input_spec,
        doc=quality_doc_effective,
        verification=design_verification_a,
        title="Double Opto-Coupler Creepage Distance",
        description="Enforce 8mm creepage barrier on secondary PCB layout.",
        control_hierarchy="inherent_safety",
        status="planned",
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    control = form.save()

    assert control.pk is not None
    assert control.tenant == tenant_a
    assert control.number.startswith("QRCM-")
    assert control.risk_assessment == risk_assessment_a
    assert control.assigned_to == admin_user
    assert control.design_input == design_input_spec
    assert control.controlled_document == quality_doc_effective
    assert control.design_verification == design_verification_a
    assert control.control_hierarchy == "inherent_safety"
    assert control.status == "planned"


def test_riskmanagement_forms_control_required_fields(tenant_a):
    """Submitting empty data to RiskControlMeasureForm produces errors on required fields."""
    form = RiskControlMeasureForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "risk_assessment" in form.errors
    assert "title" in form.errors
    assert "description" in form.errors


def test_riskmanagement_forms_control_hierarchy_and_status_choices(
    tenant_a, risk_assessment_a
):
    """Verify ISO 14971 hierarchy choices and status choices."""
    for valid_hier in ["inherent_safety", "protective_measure", "information_for_safety"]:
        data = _riskmanagement_control_base_data(risk_assessment_a, control_hierarchy=valid_hier)
        form = RiskControlMeasureForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Hierarchy '{valid_hier}' should be valid: {form.errors}"

    for valid_status in ["planned", "in_progress", "implemented", "verified", "ineffective", "obsolete"]:
        data = _riskmanagement_control_base_data(risk_assessment_a, status=valid_status)
        form = RiskControlMeasureForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Status '{valid_status}' should be valid: {form.errors}"

    bad_data = _riskmanagement_control_base_data(
        risk_assessment_a, control_hierarchy="invalid_hier", status="invalid_status"
    )
    bad_form = RiskControlMeasureForm(data=bad_data, tenant=tenant_a)
    assert not bad_form.is_valid()
    assert "control_hierarchy" in bad_form.errors
    assert "status" in bad_form.errors


def test_riskmanagement_forms_control_verification_requires_evidence_impl(
    tenant_a, risk_assessment_a
):
    """Checking implementation_verified=True without notes or test protocol triggers validation error."""
    data = _riskmanagement_control_base_data(
        risk_assessment_a,
        implementation_verified=True,
        verification_notes="",
        verification=None,
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "implementation_verified" in form.errors
    assert "Verification notes or a design verification" in str(form.errors["implementation_verified"])


def test_riskmanagement_forms_control_verification_requires_evidence_eff(
    tenant_a, risk_assessment_a
):
    """Checking effectiveness_verified=True without notes or test protocol triggers validation error."""
    data = _riskmanagement_control_base_data(
        risk_assessment_a,
        effectiveness_verified=True,
        verification_notes="",
        verification=None,
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "effectiveness_verified" in form.errors
    assert "Verification notes or a design verification" in str(form.errors["effectiveness_verified"])


def test_riskmanagement_forms_control_verification_requires_evidence_both(
    tenant_a, risk_assessment_a
):
    """Checking both verification flags without notes or test protocol errors on both fields."""
    data = _riskmanagement_control_base_data(
        risk_assessment_a,
        implementation_verified=True,
        effectiveness_verified=True,
        verification_notes="",
        verification=None,
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "implementation_verified" in form.errors
    assert "effectiveness_verified" in form.errors


def test_riskmanagement_forms_control_verification_valid_with_notes_only(
    tenant_a, risk_assessment_a
):
    """Checking implementation_verified=True WITH verification_notes is valid (no protocol required)."""
    data = _riskmanagement_control_base_data(
        risk_assessment_a,
        implementation_verified=True,
        verification_notes="Schematic review verified 4kV rated transformer T1 on PCB revision B.",
        verification=None,
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    control = form.save()
    assert control.implementation_verified is True
    assert "Schematic review" in control.verification_notes


def test_riskmanagement_forms_control_verification_valid_with_protocol_only(
    tenant_a, risk_assessment_a, design_verification_a
):
    """Checking effectiveness_verified=True WITH design_verification is valid (no notes required)."""
    data = _riskmanagement_control_base_data(
        risk_assessment_a,
        effectiveness_verified=True,
        verification_notes="",
        verification=design_verification_a,
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    control = form.save()
    assert control.effectiveness_verified is True
    assert control.design_verification == design_verification_a


def test_riskmanagement_forms_control_verification_valid_with_both_notes_and_protocol(
    tenant_a, risk_assessment_a, design_verification_a
):
    """Checking both flags with both notes and protocol is fully valid."""
    data = _riskmanagement_control_base_data(
        risk_assessment_a,
        implementation_verified=True,
        effectiveness_verified=True,
        verification_notes="Bench testing confirmed dielectric withstand voltage of 4.5kV for 60 seconds.",
        verification=design_verification_a,
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    control = form.save()
    assert control.is_fully_verified is True


def test_riskmanagement_forms_control_cross_project_consistency_mismatch(
    tenant_a, risk_assessment_a, admin_user, quality_department
):
    """Linking design_input from Project B to a risk_assessment under Project A is rejected."""
    # risk_assessment_a.plan belongs to design_project_a
    alt_project = _riskmanagement_create_alt_project(
        tenant_a, admin_user, dept=quality_department, suffix="ALT-002"
    )
    alt_input = _riskmanagement_create_alt_input(
        tenant_a, alt_project, admin_user, identifier="DI-ALT-999"
    )

    data = _riskmanagement_control_base_data(
        risk_assessment_a, design_input=alt_input
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "design_input" in form.errors
    assert "Selected Design Input belongs to Project #" in str(form.errors["design_input"])


def test_riskmanagement_forms_control_cross_project_consistency_matching(
    tenant_a, risk_assessment_a, design_input_spec
):
    """Linking design_input belonging to same project as risk_assessment plan is valid."""
    # Both belong to design_project_a
    data = _riskmanagement_control_base_data(
        risk_assessment_a, design_input=design_input_spec
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_riskmanagement_forms_control_cross_project_consistency_no_project(
    tenant_a, admin_user, risk_assessment_a
):
    """If plan has no design_project or design_input has no project, no cross-project error is raised."""
    unattached_plan = RiskManagementPlan.objects.create(
        tenant=tenant_a,
        title="Unattached General Risk Plan",
        lead_risk_manager=admin_user,
        scope_description="General risk scoping without design project.",
        risk_acceptability_policy="Baseline policy.",
        design_project=None,
    )
    unattached_assessment = RiskAssessment.objects.create(
        tenant=tenant_a,
        plan=unattached_plan,
        hazard_description="General sharp edge hazard",
        hazardous_situation="Operator handling rough packaging",
        potential_harm="Superficial skin laceration",
    )
    data = _riskmanagement_control_base_data(
        unattached_assessment, design_input=None
    )
    form = RiskControlMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_riskmanagement_forms_control_fk_tenant_scoping_dropdowns(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    risk_assessment_a,
    risk_assessment_b,
    design_input_spec,
    design_input_b,
    quality_doc_effective,
    quality_doc_b,
    design_verification_a,
    design_verification_b,
):
    """All foreign key querysets on RiskControlMeasureForm must be filtered by tenant."""
    form = RiskControlMeasureForm(tenant=tenant_a)

    rsk_pks = list(form.fields["risk_assessment"].queryset.values_list("pk", flat=True))
    user_pks = list(form.fields["assigned_to"].queryset.values_list("pk", flat=True))
    input_pks = list(form.fields["design_input"].queryset.values_list("pk", flat=True))
    doc_pks = list(form.fields["controlled_document"].queryset.values_list("pk", flat=True))
    verif_pks = list(form.fields["design_verification"].queryset.values_list("pk", flat=True))

    assert risk_assessment_a.pk in rsk_pks
    assert risk_assessment_b.pk not in rsk_pks
    assert admin_user.pk in user_pks
    assert admin_b.pk not in user_pks
    assert design_input_spec.pk in input_pks
    assert design_input_b.pk not in input_pks
    assert quality_doc_effective.pk in doc_pks
    assert quality_doc_b.pk not in doc_pks
    assert design_verification_a.pk in verif_pks
    assert design_verification_b.pk not in verif_pks


def test_riskmanagement_forms_control_no_tenant_empty_querysets():
    """Instantiating RiskControlMeasureForm with tenant=None sets all FK querysets to none()."""
    form = RiskControlMeasureForm(tenant=None)
    assert form.fields["risk_assessment"].queryset.count() == 0
    assert form.fields["assigned_to"].queryset.count() == 0
    assert form.fields["design_input"].queryset.count() == 0
    assert form.fields["controlled_document"].queryset.count() == 0
    assert form.fields["design_verification"].queryset.count() == 0


def test_riskmanagement_forms_control_cross_tenant_rejection(
    tenant_a,
    risk_assessment_a,
    risk_assessment_b,
    admin_b,
    design_input_b,
    quality_doc_b,
    design_verification_b,
):
    """Submitting foreign records into tenant_a RiskControlMeasureForm triggers validation errors."""
    for field_name, foreign_val in [
        ("risk_assessment", risk_assessment_b),
        ("assigned_to", admin_b),
        ("design_input", design_input_b),
        ("controlled_document", quality_doc_b),
        ("design_verification", design_verification_b),
    ]:
        if field_name == "risk_assessment":
            data = _riskmanagement_control_base_data(foreign_val)
        else:
            data = _riskmanagement_control_base_data(risk_assessment_a)
            data[field_name] = foreign_val.pk
        form = RiskControlMeasureForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Field '{field_name}' with foreign value should fail validation"
        assert field_name in form.errors


def test_riskmanagement_forms_control_reject_foreign_clean_direct(
    tenant_a,
    risk_assessment_b,
    admin_b,
    design_input_b,
    quality_doc_b,
    design_verification_b,
):
    """Directly verify reject_foreign adds validation errors for all 5 FK fields on RiskControlMeasureForm."""
    form = RiskControlMeasureForm(tenant=tenant_a)
    form.cleaned_data = {
        "risk_assessment": risk_assessment_b,
        "assigned_to": admin_b,
        "design_input": design_input_b,
        "controlled_document": quality_doc_b,
        "design_verification": design_verification_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["risk_assessment", "assigned_to", "design_input", "controlled_document", "design_verification"],
    )
    for field_name in ["risk_assessment", "assigned_to", "design_input", "controlled_document", "design_verification"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


def test_riskmanagement_forms_control_widget_classes(tenant_a):
    """Verify CSS widget classes on RiskControlMeasureForm."""
    form = RiskControlMeasureForm(tenant=tenant_a)
    assert "form-select" in form.fields["risk_assessment"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["control_hierarchy"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["description"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["assigned_to"].widget.attrs.get("class", "")
    assert (
        form.fields["due_date"].widget.attrs.get("type")
        or getattr(form.fields["due_date"].widget, "input_type", None)
    ) == "date"
    assert "form-select" in form.fields["status"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["design_input"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["controlled_document"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["design_verification"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["implementation_verified"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["effectiveness_verified"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["verification_notes"].widget.attrs.get("class", "")


# =====================================================================
# 5. RiskReviewRecordForm Tests
# =====================================================================


def test_riskmanagement_forms_review_valid_creation(
    tenant_a, risk_management_plan_a, admin_user
):
    """Submitting valid RiskReviewRecordForm persists review record with QRMR- auto-number."""
    data = _riskmanagement_review_base_data(
        risk_management_plan_a,
        admin_user,
        review_title="Q4 2026 Periodic Risk Review & Evaluation",
        review_type="periodic_review",
        status="draft",
        new_hazards_identified=True,
        risk_profile_changed=False,
        overall_residual_risk_reconfirmed=True,
        findings_summary="One new human factors use error identified from complaint data; logged into risk register.",
        action_items_required="Open CAPA-2026-042 to revise labeling IFU section 3.",
    )
    form = RiskReviewRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    review = form.save()

    assert review.pk is not None
    assert review.tenant == tenant_a
    assert review.number.startswith("QRMR-")
    assert review.plan == risk_management_plan_a
    assert review.lead_reviewer == admin_user
    assert review.review_title == "Q4 2026 Periodic Risk Review & Evaluation"
    assert review.status == "draft"
    assert review.new_hazards_identified is True
    assert review.overall_residual_risk_reconfirmed is True


def test_riskmanagement_forms_review_required_fields(tenant_a):
    """Submitting empty data to RiskReviewRecordForm produces errors on required fields."""
    form = RiskReviewRecordForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "plan" in form.errors
    assert "review_title" in form.errors
    assert "review_date" in form.errors
    assert "findings_summary" in form.errors
    assert "lead_reviewer" in form.errors


def test_riskmanagement_forms_review_status_choices_restricted_in_init(tenant_a):
    """Status choices in RiskReviewRecordForm.__init__ must be restricted to draft and under_review."""
    form = RiskReviewRecordForm(tenant=tenant_a)
    choice_keys = [k for k, _ in form.fields["status"].choices]
    assert choice_keys == ["draft", "under_review"]
    assert "approved" not in choice_keys
    assert "rejected" not in choice_keys


def test_riskmanagement_forms_review_status_clean_rejects_approved(
    tenant_a, risk_management_plan_a, admin_user
):
    """Clean method rejects status='approved' directly in form submission."""
    data = _riskmanagement_review_base_data(
        risk_management_plan_a, admin_user, status="approved"
    )
    form = RiskReviewRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors


def test_riskmanagement_forms_review_status_clean_rejects_rejected(
    tenant_a, risk_management_plan_a, admin_user
):
    """Clean method rejects status='rejected' directly in form submission."""
    data = _riskmanagement_review_base_data(
        risk_management_plan_a, admin_user, status="rejected"
    )
    form = RiskReviewRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors


def test_riskmanagement_forms_review_status_clean_allows_draft_and_under_review(
    tenant_a, risk_management_plan_a, admin_user
):
    """Clean method accepts status='draft' and status='under_review'."""
    for valid_status in ["draft", "under_review"]:
        data = _riskmanagement_review_base_data(
            risk_management_plan_a, admin_user, status=valid_status
        )
        form = RiskReviewRecordForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Status '{valid_status}' should be valid: {form.errors}"
        review = form.save()
        assert review.status == valid_status


def test_riskmanagement_forms_review_review_type_choices(
    tenant_a, risk_management_plan_a, admin_user
):
    """Verify review_type choices validation."""
    valid_types = [
        "initial_rmr",
        "periodic_review",
        "design_change_review",
        "post_market_surveillance",
        "complaint_trend_trigger",
        "ncr_capa_trigger",
    ]
    for r_type in valid_types:
        data = _riskmanagement_review_base_data(
            risk_management_plan_a, admin_user, review_type=r_type
        )
        form = RiskReviewRecordForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Review type '{r_type}' should be valid: {form.errors}"

    bad_data = _riskmanagement_review_base_data(
        risk_management_plan_a, admin_user, review_type="invalid_type"
    )
    bad_form = RiskReviewRecordForm(data=bad_data, tenant=tenant_a)
    assert not bad_form.is_valid()
    assert "review_type" in bad_form.errors


def test_riskmanagement_forms_review_dates_validation(
    tenant_a, risk_management_plan_a, admin_user
):
    """Verify review_date is required and date inputs parse correctly."""
    # Missing review_date
    data_no_date = _riskmanagement_review_base_data(
        risk_management_plan_a, admin_user, review_date=""
    )
    form_no_date = RiskReviewRecordForm(data=data_no_date, tenant=tenant_a)
    assert not form_no_date.is_valid()
    assert "review_date" in form_no_date.errors

    # Invalid date format
    data_bad_date = _riskmanagement_review_base_data(
        risk_management_plan_a, admin_user, review_date="not-a-date"
    )
    form_bad_date = RiskReviewRecordForm(data=data_bad_date, tenant=tenant_a)
    assert not form_bad_date.is_valid()
    assert "review_date" in form_bad_date.errors

    # Valid period start and end dates
    data_valid_dates = _riskmanagement_review_base_data(
        risk_management_plan_a,
        admin_user,
        review_date="2026-11-15",
        review_period_start="2025-11-15",
        review_period_end="2026-11-14",
    )
    form_valid = RiskReviewRecordForm(data=data_valid_dates, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors
    record = form_valid.save()
    assert record.review_date.isoformat() == "2026-11-15"
    assert record.review_period_start.isoformat() == "2025-11-15"
    assert record.review_period_end.isoformat() == "2026-11-14"


def test_riskmanagement_forms_review_fk_tenant_scoping_dropdowns(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    risk_management_plan_a,
    risk_management_plan_b,
):
    """Dropdown querysets for plan and lead_reviewer must be filtered by tenant."""
    form = RiskReviewRecordForm(tenant=tenant_a)
    plan_pks = list(form.fields["plan"].queryset.values_list("pk", flat=True))
    user_pks = list(form.fields["lead_reviewer"].queryset.values_list("pk", flat=True))

    assert risk_management_plan_a.pk in plan_pks
    assert risk_management_plan_b.pk not in plan_pks
    assert admin_user.pk in user_pks
    assert admin_b.pk not in user_pks


def test_riskmanagement_forms_review_no_tenant_empty_querysets():
    """Instantiating RiskReviewRecordForm with tenant=None sets all FK querysets to none()."""
    form = RiskReviewRecordForm(tenant=None)
    assert form.fields["plan"].queryset.count() == 0
    assert form.fields["lead_reviewer"].queryset.count() == 0


def test_riskmanagement_forms_review_cross_tenant_rejection(
    tenant_a,
    risk_management_plan_a,
    risk_management_plan_b,
    admin_user,
    admin_b,
):
    """Submitting foreign plan or foreign lead_reviewer fails validation."""
    # Foreign plan
    data_bad_plan = _riskmanagement_review_base_data(
        risk_management_plan_b, admin_user
    )
    form_plan = RiskReviewRecordForm(data=data_bad_plan, tenant=tenant_a)
    assert not form_plan.is_valid()
    assert "plan" in form_plan.errors

    # Foreign lead_reviewer
    data_bad_user = _riskmanagement_review_base_data(
        risk_management_plan_a, admin_b
    )
    form_user = RiskReviewRecordForm(data=data_bad_user, tenant=tenant_a)
    assert not form_user.is_valid()
    assert "lead_reviewer" in form_user.errors


def test_riskmanagement_forms_review_reject_foreign_clean_direct(
    tenant_a, risk_management_plan_b, admin_b
):
    """Directly verify reject_foreign adds validation errors for plan and lead_reviewer."""
    form = RiskReviewRecordForm(tenant=tenant_a)
    form.cleaned_data = {
        "plan": risk_management_plan_b,
        "lead_reviewer": admin_b,
    }
    reject_foreign(form, form.cleaned_data, ["plan", "lead_reviewer"])
    assert "plan" in form.errors
    assert "lead_reviewer" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["plan"])


def test_riskmanagement_forms_review_widget_classes(tenant_a):
    """Verify CSS widget classes on RiskReviewRecordForm."""
    form = RiskReviewRecordForm(tenant=tenant_a)
    assert "form-select" in form.fields["plan"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["review_title"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["review_type"].widget.attrs.get("class", "")
    assert (
        form.fields["review_date"].widget.attrs.get("type")
        or getattr(form.fields["review_date"].widget, "input_type", None)
    ) == "date"
    assert (
        form.fields["review_period_start"].widget.attrs.get("type")
        or getattr(form.fields["review_period_start"].widget, "input_type", None)
    ) == "date"
    assert (
        form.fields["review_period_end"].widget.attrs.get("type")
        or getattr(form.fields["review_period_end"].widget, "input_type", None)
    ) == "date"
    assert "form-textarea" in form.fields["pms_sources_reviewed"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["new_hazards_identified"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["risk_profile_changed"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["overall_residual_risk_reconfirmed"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["findings_summary"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["action_items_required"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["status"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["lead_reviewer"].widget.attrs.get("class", "")
