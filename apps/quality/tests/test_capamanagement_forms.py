"""
Unit tests for apps/quality forms (Sub-module 12.4: CAPA - Corrective & Preventive Action).

Covers:
- CapaInvestigationForm:
  - System field exclusion (tenant, number, created_at, updated_at, escalated_at,
    closed_at, closure_approved_by, formal_closure_signature).
  - Valid full and minimal submissions.
  - Required fields validation (title, issue_summary, lead_investigator, quality_owner).
  - clean_status: disallows "closed" and "voided" on create and edit unless already in that status.
  - clean_status: allows standard lifecycle statuses (draft, under_investigation, etc.).
  - Target closure date validation (valid dates, empty dates, invalid date strings).
  - Tenant-scoped querysets in __init__ (department, lead_investigator, quality_owner,
    containment_verified_by, design_project, risk_assessment).
  - Empty querysets when instantiated without tenant.
  - Cross-tenant injection rejection via ModelChoiceField and reject_foreign.
  - Inactive users exclusion from user choice fields.
  - Form save persistence with QCAP- auto-number and tenant attachment.
- RootCauseAnalysisForm:
  - System field exclusion (tenant, number, created_at, updated_at, verified_by,
    verified_date, verification_notes).
  - Valid 5 Whys and Ishikawa fishbone submissions.
  - Required fields validation (capa, problem_statement, root_cause_summary, lead_investigator).
  - clean_status: disallows "verified" directly on create and edit unless already verified.
  - Parent CAPA immutability: changing capa on existing RCA raises validation error.
  - Tenant-scoped querysets in __init__ (capa, lead_investigator).
  - Empty querysets without tenant.
  - Cross-tenant injection rejection.
  - Inactive users exclusion.
  - Form save persistence with QRCA- auto-number.
- CapaActionForm:
  - System field exclusion (tenant, number, created_at, updated_at, completion_date,
    verified_by, verified_on, verification_evidence).
  - Valid full and minimal submissions.
  - Required fields validation (capa, title, description, assigned_to, due_date).
  - Cross-CAPA validation: linking an action to CAPA A with a root cause belonging to
    CAPA B fails validation on root_cause with descriptive error.
  - Cross-CAPA validation: linking matching root cause or omitting root cause is accepted.
  - Parent CAPA immutability on edit.
  - clean_status: disallows "verified" on create and edit unless already verified.
  - Tenant-scoped querysets in __init__ (capa, root_cause with select_related('capa'),
    assigned_to, department, controlled_document, change_order, design_project).
  - Empty querysets without tenant.
  - Cross-tenant injection rejection via reject_foreign.
  - Inactive users exclusion.
  - Form save persistence with QACT- auto-number.
- CapaEffectivenessReviewForm:
  - System field exclusion (tenant, number, created_at, updated_at, actual_review_date,
    formal_signature).
  - Valid submission.
  - Required fields validation (capa, review_criteria, planned_review_date, evaluator).
  - Recurrence safety rule: outcome="effective" with recurrence_observed=True raises
    validation error on outcome.
  - Recurrence safety rule: permits outcome="effective" when recurrence_observed=False,
    and permits outcome="ineffective" or "inconclusive" when recurrence_observed=True.
  - Parent CAPA immutability on edit.
  - clean_status: disallows "completed" on create and edit unless already completed.
  - Tenant-scoped querysets in __init__ (capa, evaluator).
  - Empty querysets without tenant.
  - Cross-tenant injection rejection.
  - Inactive users exclusion.
  - Form save persistence with QEFF- auto-number.
- Widget CSS Classes and Inputs across all 4 forms.
"""

from datetime import timedelta
import pytest
from django import forms
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.quality.forms import (
    CapaActionForm,
    CapaEffectivenessReviewForm,
    CapaInvestigationForm,
    RootCauseAnalysisForm,
)
from apps.quality.forms._common import reject_foreign
from apps.quality.models import (
    CapaAction,
    CapaEffectivenessReview,
    CapaInvestigation,
    ControlledDocument,
    DesignProject,
    DocumentChangeOrder,
    RiskAssessment,
    RootCauseAnalysis,
)

pytestmark = pytest.mark.django_db


# =====================================================================
# Fixtures and Helpers (Prefix: _capamanagement_*)
# =====================================================================


def _capamanagement_pk(val):
    """Return pk if val is a model instance, or val itself if already a scalar / None."""
    if val is None or val == "":
        return ""
    return getattr(val, "pk", val)


def _capamanagement_create_user(tenant, username, email, is_active=True):
    """Helper creating a test user under a given tenant."""
    return User.objects.create_user(
        username=username,
        email=email,
        password="TestPassword123!",
        tenant=tenant,
        is_active=is_active,
    )


def _capamanagement_investigation_base_data(investigator, owner, department=None, **extra):
    """Build valid baseline POST dictionary for CapaInvestigationForm."""
    data = {
        "title": "Occlusion Pressure Transducer Calibration Drift",
        "issue_summary": "In-line pressure sensor reports 30% below actual line pressure during high flow rate delivery.",
        "action_type": "corrective",
        "source_type": "ncr",
        "source_reference": "NCR-2026-0099",
        "risk_priority": "high",
        "containment_actions": "Quarantine pump serials SN-2026-0001 through SN-2026-0050.",
        "containment_implemented": True,
        "containment_verified_by": _capamanagement_pk(investigator),
        "containment_date": timezone.now().date().isoformat(),
        "affected_item_code": "SNSR-PRS-001",
        "affected_item_name": "Pressure Transducer Assembly",
        "affected_lot_numbers": "LOT-2026-X1, LOT-2026-X2",
        "lead_investigator": _capamanagement_pk(investigator),
        "quality_owner": _capamanagement_pk(owner),
        "department": _capamanagement_pk(department),
        "design_project": "",
        "risk_assessment": "",
        "status": "under_investigation",
        "target_investigation_date": (timezone.now() + timedelta(days=14)).date().isoformat(),
        "target_closure_date": (timezone.now() + timedelta(days=60)).date().isoformat(),
        "is_escalated": False,
        "escalation_reason": "",
        "closure_summary": "",
    }
    data.update(extra)
    return data


def _capamanagement_rca_base_data(capa, investigator, **extra):
    """Build valid baseline POST dictionary for RootCauseAnalysisForm."""
    data = {
        "capa": _capamanagement_pk(capa),
        "rca_method": "5_whys",
        "problem_statement": "Pressure sensor calibration shifts by more than 15% after 200 operational hours.",
        "why_1": "Strain gauge bond adhesive degraded under operating temperature.",
        "why_2": "Curing oven temperature was 15 deg C below formulation curing threshold.",
        "why_3": "Thermocouple calibration on curing oven was out of tolerance by 18 deg C.",
        "why_4": "Oven calibration interval was set to 12 months instead of quarterly per OEM guidance.",
        "why_5": "Calibration schedule maintenance SOP omitted oven sensor drift risk review.",
        "fishbone_manpower": "",
        "fishbone_machine": "",
        "fishbone_material": "",
        "fishbone_method": "",
        "fishbone_measurement": "",
        "fishbone_environment": "",
        "root_cause_category": "equipment",
        "root_cause_summary": "Thermal curing oven thermocouple calibration drift causing incomplete adhesive cure.",
        "escape_point_gap": "End-of-line functional test only checked ambient temperature pressure response.",
        "status": "in_progress",
        "lead_investigator": _capamanagement_pk(investigator),
    }
    data.update(extra)
    return data


def _capamanagement_action_base_data(capa, assigned_to, root_cause=None, department=None, **extra):
    """Build valid baseline POST dictionary for CapaActionForm."""
    data = {
        "capa": _capamanagement_pk(capa),
        "root_cause": _capamanagement_pk(root_cause),
        "action_type": "corrective",
        "title": "Recalibrate Curing Oven and Update PM Calibration SOP",
        "description": "Perform NIST-traceable thermocouple recalibration and establish quarterly calibration schedule.",
        "assigned_to": _capamanagement_pk(assigned_to),
        "department": _capamanagement_pk(department),
        "due_date": (timezone.now() + timedelta(days=30)).date().isoformat(),
        "status": "pending",
        "implementation_notes": "",
        "controlled_document": "",
        "change_order": "",
        "design_project": "",
    }
    data.update(extra)
    return data


def _capamanagement_review_base_data(capa, evaluator, **extra):
    """Build valid baseline POST dictionary for CapaEffectivenessReviewForm."""
    data = {
        "capa": _capamanagement_pk(capa),
        "review_criteria": "Zero pressure transducer calibration drift observed in 3 consecutive production lots.",
        "verification_method": "zero_recurrence_window",
        "planned_review_date": (timezone.now() + timedelta(days=90)).date().isoformat(),
        "evaluator": _capamanagement_pk(evaluator),
        "metrics_evaluated": "50 units from Lots 101, 102, 103 tested after 500 hours burn-in.",
        "recurrence_observed": False,
        "recurrence_details": "",
        "outcome": "effective",
        "status": "scheduled",
        "review_notes": "All lots demonstrated zero drift. Action verified effective.",
    }
    data.update(extra)
    return data


# =====================================================================
# 1. System Field Exclusion Tests across All 4 Forms
# =====================================================================


def test_capamanagement_forms_investigation_system_field_exclusion(tenant_a, admin_user):
    """Verify tenant, number, created_at, updated_at, escalated_at, closed_at, closure_approved_by, formal_closure_signature are excluded."""
    form = CapaInvestigationForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "escalated_at",
        "closed_at",
        "closure_approved_by",
        "formal_closure_signature",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from CapaInvestigationForm"

    # Submitting forbidden parameters in POST data must not bind to form instance
    malicious_data = _capamanagement_investigation_base_data(
        admin_user,
        admin_user,
        tenant=tenant_a.pk,
        number="QCAP-HACKED-9999",
        escalated_at=timezone.now().isoformat(),
        closed_at=timezone.now().isoformat(),
        closure_approved_by=admin_user.pk,
    )
    bound_form = CapaInvestigationForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QCAP-HACKED-9999"
    assert instance.closed_at is None
    assert instance.closure_approved_by is None


def test_capamanagement_forms_rca_system_field_exclusion(tenant_a, admin_user, capa_investigation_a):
    """Verify tenant, number, created_at, updated_at, verified_by, verified_date, verification_notes are excluded from RootCauseAnalysisForm."""
    form = RootCauseAnalysisForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "verified_by",
        "verified_date",
        "verification_notes",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from RootCauseAnalysisForm"

    malicious_data = _capamanagement_rca_base_data(
        capa_investigation_a,
        admin_user,
        tenant=tenant_a.pk,
        number="QRCA-HACKED-9999",
        verified_by=admin_user.pk,
        verified_date=timezone.now().date().isoformat(),
    )
    bound_form = RootCauseAnalysisForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QRCA-HACKED-9999"
    assert instance.verified_by is None
    assert instance.verified_date is None


def test_capamanagement_forms_action_system_field_exclusion(tenant_a, admin_user, capa_investigation_a):
    """Verify tenant, number, created_at, updated_at, completion_date, verified_by, verified_on, verification_evidence are excluded."""
    form = CapaActionForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "completion_date",
        "verified_by",
        "verified_on",
        "verification_evidence",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from CapaActionForm"

    malicious_data = _capamanagement_action_base_data(
        capa_investigation_a,
        admin_user,
        tenant=tenant_a.pk,
        number="QACT-HACKED-9999",
        completion_date=timezone.now().date().isoformat(),
        verified_by=admin_user.pk,
        verified_on=timezone.now().date().isoformat(),
    )
    bound_form = CapaActionForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QACT-HACKED-9999"
    assert instance.verified_by is None
    assert instance.verified_on is None
    assert instance.completion_date is None


def test_capamanagement_forms_review_system_field_exclusion(tenant_a, admin_user, capa_investigation_a):
    """Verify tenant, number, created_at, updated_at, actual_review_date, formal_signature are excluded from CapaEffectivenessReviewForm."""
    form = CapaEffectivenessReviewForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "actual_review_date",
        "formal_signature",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from CapaEffectivenessReviewForm"

    malicious_data = _capamanagement_review_base_data(
        capa_investigation_a,
        admin_user,
        tenant=tenant_a.pk,
        number="QEFF-HACKED-9999",
        actual_review_date=timezone.now().date().isoformat(),
    )
    bound_form = CapaEffectivenessReviewForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QEFF-HACKED-9999"
    assert instance.actual_review_date is None


# =====================================================================
# 2. CapaInvestigationForm Tests
# =====================================================================


def test_capamanagement_forms_investigation_valid_full_submission(
    tenant_a, admin_user, quality_department, design_project_a, risk_assessment_a
):
    """Verify valid submission of CapaInvestigationForm with all foreign keys and metadata."""
    data = _capamanagement_investigation_base_data(
        admin_user,
        admin_user,
        department=quality_department,
        design_project=_capamanagement_pk(design_project_a),
        risk_assessment=_capamanagement_pk(risk_assessment_a),
        action_type="preventive",
        source_type="risk_assessment",
        risk_priority="critical",
        is_escalated=True,
        escalation_reason="Regulatory risk trigger under ISO 13485:2016.",
        closure_summary="Interim investigation containment report.",
    )
    form = CapaInvestigationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    investigation = form.save()
    assert investigation.pk is not None
    assert investigation.tenant == tenant_a
    assert investigation.number.startswith("QCAP-")
    assert investigation.action_type == "preventive"
    assert investigation.design_project == design_project_a
    assert investigation.risk_assessment == risk_assessment_a
    assert investigation.is_escalated is True


def test_capamanagement_forms_investigation_valid_minimal_submission(tenant_a, admin_user):
    """Verify valid submission with only required fields and empty optional fields."""
    data = {
        "title": "Minimal Defect Report Investigation",
        "issue_summary": "Minimal issue description for initial triage.",
        "action_type": "corrective",
        "source_type": "internal_audit",
        "source_reference": "",
        "risk_priority": "medium",
        "containment_actions": "",
        "containment_implemented": False,
        "containment_verified_by": "",
        "containment_date": "",
        "affected_item_code": "",
        "affected_item_name": "",
        "affected_lot_numbers": "",
        "lead_investigator": admin_user.pk,
        "quality_owner": admin_user.pk,
        "department": "",
        "design_project": "",
        "risk_assessment": "",
        "status": "draft",
        "target_investigation_date": "",
        "target_closure_date": "",
        "is_escalated": False,
        "escalation_reason": "",
        "closure_summary": "",
    }
    form = CapaInvestigationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.status == "draft"


def test_capamanagement_forms_investigation_required_fields(tenant_a):
    """Verify required field validation triggers for title, issue_summary, lead_investigator, quality_owner."""
    form = CapaInvestigationForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "issue_summary" in form.errors
    assert "lead_investigator" in form.errors
    assert "quality_owner" in form.errors


def test_capamanagement_forms_investigation_clean_status_disallows_closed_on_create(tenant_a, admin_user):
    """clean_status must reject status='closed' on creation of a new investigation."""
    data = _capamanagement_investigation_base_data(admin_user, admin_user, status="closed")
    form = CapaInvestigationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'closed' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_investigation_clean_status_disallows_voided_on_create(tenant_a, admin_user):
    """clean_status must reject status='voided' on creation of a new investigation."""
    data = _capamanagement_investigation_base_data(admin_user, admin_user, status="voided")
    form = CapaInvestigationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'voided' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_investigation_clean_status_disallows_transition_to_closed_on_edit(
    capa_investigation_a, admin_user
):
    """clean_status must reject changing status to 'closed' on an existing investigation."""
    data = _capamanagement_investigation_base_data(admin_user, admin_user, status="closed")
    form = CapaInvestigationForm(instance=capa_investigation_a, data=data, tenant=capa_investigation_a.tenant)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'closed' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_investigation_clean_status_disallows_transition_to_voided_on_edit(
    capa_investigation_a, admin_user
):
    """clean_status must reject changing status to 'voided' on an existing investigation."""
    data = _capamanagement_investigation_base_data(admin_user, admin_user, status="voided")
    form = CapaInvestigationForm(instance=capa_investigation_a, data=data, tenant=capa_investigation_a.tenant)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'voided' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_investigation_clean_status_allows_existing_closed_or_voided(
    tenant_a, admin_user, quality_department
):
    """clean_status allows editing other fields when the instance is already in 'closed' or 'voided' status."""
    closed_investigation = CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Previously Closed Investigation",
        issue_summary="Investigation closed following full verification.",
        action_type="corrective",
        source_type="ncr",
        risk_priority="medium",
        status="closed",
        lead_investigator=admin_user,
        quality_owner=admin_user,
        department=quality_department,
    )
    data = _capamanagement_investigation_base_data(
        admin_user,
        admin_user,
        title="Updated Title on Closed Investigation",
        status="closed",
    )
    form = CapaInvestigationForm(instance=closed_investigation, data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.title == "Updated Title on Closed Investigation"
    assert saved.status == "closed"


def test_capamanagement_forms_investigation_clean_status_allows_standard_statuses(tenant_a, admin_user):
    """Standard lifecycle statuses (draft, under_investigation, rca_in_progress, action_plan_dev, action_implementation, effectiveness_review) are accepted."""
    standard_statuses = [
        "draft",
        "under_investigation",
        "rca_in_progress",
        "action_plan_dev",
        "action_implementation",
        "effectiveness_review",
    ]
    for status_val in standard_statuses:
        data = _capamanagement_investigation_base_data(admin_user, admin_user, status=status_val)
        form = CapaInvestigationForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Status '{status_val}' should be valid, but got: {form.errors}"


def test_capamanagement_forms_investigation_target_closure_date_validation(tenant_a, admin_user):
    """Verify date parsing on target_closure_date and target_investigation_date."""
    # Valid dates
    future_data = _capamanagement_investigation_base_data(
        admin_user,
        admin_user,
        target_investigation_date=(timezone.now() + timedelta(days=10)).date().isoformat(),
        target_closure_date=(timezone.now() + timedelta(days=45)).date().isoformat(),
    )
    form = CapaInvestigationForm(data=future_data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    # Invalid date string fails validation
    invalid_data = _capamanagement_investigation_base_data(
        admin_user,
        admin_user,
        target_closure_date="not-a-valid-date",
    )
    invalid_form = CapaInvestigationForm(data=invalid_data, tenant=tenant_a)
    assert not invalid_form.is_valid()
    assert "target_closure_date" in invalid_form.errors


def test_capamanagement_forms_investigation_tenant_scoping_querysets(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    quality_department,
    quality_department_b,
    design_project_a,
    design_project_b,
    risk_assessment_a,
    risk_assessment_b,
):
    """Verify that all ForeignKey querysets are strictly filtered to the current tenant."""
    form = CapaInvestigationForm(tenant=tenant_a)

    # Department
    dept_pks = list(form.fields["department"].queryset.values_list("pk", flat=True))
    assert quality_department.pk in dept_pks
    assert quality_department_b.pk not in dept_pks

    # Users
    lead_pks = list(form.fields["lead_investigator"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in lead_pks
    assert admin_b.pk not in lead_pks

    owner_pks = list(form.fields["quality_owner"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in owner_pks
    assert admin_b.pk not in owner_pks

    containment_pks = list(form.fields["containment_verified_by"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in containment_pks
    assert admin_b.pk not in containment_pks

    # Design project
    project_pks = list(form.fields["design_project"].queryset.values_list("pk", flat=True))
    assert design_project_a.pk in project_pks
    assert design_project_b.pk not in project_pks

    # Risk assessment
    risk_pks = list(form.fields["risk_assessment"].queryset.values_list("pk", flat=True))
    assert risk_assessment_a.pk in risk_pks
    assert risk_assessment_b.pk not in risk_pks


def test_capamanagement_forms_investigation_empty_querysets_without_tenant():
    """Verify ForeignKey querysets are empty when form is instantiated with tenant=None."""
    form = CapaInvestigationForm(tenant=None)
    assert form.fields["department"].queryset.count() == 0
    assert form.fields["lead_investigator"].queryset.count() == 0
    assert form.fields["quality_owner"].queryset.count() == 0
    assert form.fields["containment_verified_by"].queryset.count() == 0
    assert form.fields["design_project"].queryset.count() == 0
    assert form.fields["risk_assessment"].queryset.count() == 0


def test_capamanagement_forms_investigation_cross_tenant_rejection_via_model_choice(
    tenant_a, admin_user, admin_b, quality_department_b
):
    """Submitting foreign keys from another tenant fails ModelChoiceField choice validation."""
    data = _capamanagement_investigation_base_data(
        admin_user,
        admin_user,
        department=quality_department_b.pk,
    )
    form = CapaInvestigationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "department" in form.errors

    data_user = _capamanagement_investigation_base_data(
        admin_b,
        admin_user,
    )
    form_user = CapaInvestigationForm(data=data_user, tenant=tenant_a)
    assert not form_user.is_valid()
    assert "lead_investigator" in form_user.errors


def test_capamanagement_forms_investigation_cross_tenant_rejection_direct_reject_foreign(
    tenant_a, admin_b, quality_department_b, design_project_b, risk_assessment_b
):
    """Directly verify reject_foreign raises workspace error for all foreign relations."""
    form = CapaInvestigationForm(tenant=tenant_a)
    form.cleaned_data = {
        "department": quality_department_b,
        "design_project": design_project_b,
        "risk_assessment": risk_assessment_b,
        "lead_investigator": admin_b,
        "quality_owner": admin_b,
        "containment_verified_by": admin_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        [
            "department",
            "design_project",
            "risk_assessment",
            "lead_investigator",
            "quality_owner",
            "containment_verified_by",
        ],
    )
    for field_name in [
        "department",
        "design_project",
        "risk_assessment",
        "lead_investigator",
        "quality_owner",
        "containment_verified_by",
    ]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


def test_capamanagement_forms_investigation_inactive_users_excluded(tenant_a, admin_user):
    """Inactive users under tenant must be excluded from user querysets."""
    inactive_user = _capamanagement_create_user(
        tenant_a, "inactive_investigator", "inactive.capa@acme.com", is_active=False
    )
    form = CapaInvestigationForm(tenant=tenant_a)
    lead_pks = list(form.fields["lead_investigator"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in lead_pks
    assert inactive_user.pk not in lead_pks


def test_capamanagement_forms_investigation_save_persistence(tenant_a, admin_user, quality_department):
    """Form save attaches tenant and persists QCAP- sequence correctly."""
    data = _capamanagement_investigation_base_data(
        admin_user,
        admin_user,
        department=quality_department,
        title="Auto-Numbered CAPA Investigation Persistence",
    )
    form = CapaInvestigationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("QCAP-")
    assert instance.title == "Auto-Numbered CAPA Investigation Persistence"


# =====================================================================
# 3. RootCauseAnalysisForm Tests
# =====================================================================


def test_capamanagement_forms_rca_valid_submission_5_whys(capa_investigation_a, admin_user):
    """Verify valid submission with 5 Whys methodology ladder."""
    data = _capamanagement_rca_base_data(
        capa_investigation_a,
        admin_user,
        rca_method="5_whys",
        problem_statement="Occlusion pressure reading error exceeding 25% under normal saline flow.",
        why_1="Sensor diaphragm deflection was restricted.",
        why_2="Silicone gel encapsulation had cured too rigidly.",
        why_3="Two-part potting resin mixture ratio was 1.5:1 instead of 1:1 nominal.",
        why_4="Automated dispenser pump piston seal had worn out.",
        why_5="No periodic volume verification check for silicone dispensing head.",
        root_cause_category="equipment",
        root_cause_summary="Dispenser pump piston wear causing off-ratio silicone potting formulation.",
    )
    form = RootCauseAnalysisForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    rca = form.save()
    assert rca.pk is not None
    assert rca.tenant == capa_investigation_a.tenant
    assert rca.number.startswith("QRCA-")
    assert rca.rca_method == "5_whys"
    assert rca.why_levels_count == 5


def test_capamanagement_forms_rca_valid_submission_fishbone(capa_investigation_a, admin_user):
    """Verify valid submission with Ishikawa 6M fishbone diagram methodology."""
    data = _capamanagement_rca_base_data(
        capa_investigation_a,
        admin_user,
        rca_method="fishbone_ishikawa",
        problem_statement="Occasional high pressure alarm trigger on channel 2.",
        fishbone_manpower="Operator shift handoff lacked calibration verification sign-off.",
        fishbone_machine="Dispensing valve head nozzle experienced micro-clogging.",
        fishbone_material="Lot variance in potting silicone monomer viscosity.",
        fishbone_method="Work instruction WI-201 did not specify mixing speed limits.",
        fishbone_measurement="Digital manometer gauge resolution insufficient below 0.1 PSI.",
        fishbone_environment="Cleanroom humidity dropped below 30% relative humidity.",
        root_cause_category="process",
        root_cause_summary="Combination of low humidity and nozzle micro-clogging caused dispensing variation.",
    )
    form = RootCauseAnalysisForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    rca = form.save()
    assert rca.pk is not None
    assert rca.rca_method == "fishbone_ishikawa"
    assert rca.fishbone_manpower != ""
    assert rca.fishbone_machine != ""


def test_capamanagement_forms_rca_valid_minimal_submission(capa_investigation_a, admin_user):
    """Verify minimal submission with only required fields."""
    data = {
        "capa": capa_investigation_a.pk,
        "rca_method": "5_whys",
        "problem_statement": "Concise failure description.",
        "why_1": "",
        "why_2": "",
        "why_3": "",
        "why_4": "",
        "why_5": "",
        "fishbone_manpower": "",
        "fishbone_machine": "",
        "fishbone_material": "",
        "fishbone_method": "",
        "fishbone_measurement": "",
        "fishbone_environment": "",
        "root_cause_category": "process",
        "root_cause_summary": "Primary root cause statement.",
        "escape_point_gap": "",
        "status": "draft",
        "lead_investigator": admin_user.pk,
    }
    form = RootCauseAnalysisForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    rca = form.save()
    assert rca.pk is not None
    assert rca.status == "draft"


def test_capamanagement_forms_rca_required_fields(tenant_a):
    """Verify required fields on RootCauseAnalysisForm."""
    form = RootCauseAnalysisForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "capa" in form.errors
    assert "problem_statement" in form.errors
    assert "root_cause_summary" in form.errors
    assert "lead_investigator" in form.errors


def test_capamanagement_forms_rca_clean_status_disallows_verified_on_create(capa_investigation_a, admin_user):
    """clean_status must reject status='verified' on creation of a new Root Cause Analysis."""
    data = _capamanagement_rca_base_data(capa_investigation_a, admin_user, status="verified")
    form = RootCauseAnalysisForm(data=data, tenant=capa_investigation_a.tenant)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'verified' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_rca_clean_status_disallows_verified_on_edit_when_not_verified(
    root_cause_analysis_a, admin_user
):
    """clean_status must reject updating status to 'verified' via standard form when not currently verified."""
    data = _capamanagement_rca_base_data(root_cause_analysis_a.capa, admin_user, status="verified")
    form = RootCauseAnalysisForm(
        instance=root_cause_analysis_a, data=data, tenant=root_cause_analysis_a.tenant
    )
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'verified' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_rca_clean_status_allows_verified_when_already_verified(
    capa_investigation_a, admin_user
):
    """clean_status allows saving with status='verified' if the existing record is already verified."""
    verified_rca = RootCauseAnalysis.objects.create(
        tenant=capa_investigation_a.tenant,
        capa=capa_investigation_a,
        rca_method="5_whys",
        problem_statement="Verified failure mode problem statement.",
        root_cause_summary="Verified root cause summary.",
        root_cause_category="equipment",
        status="verified",
        lead_investigator=admin_user,
        verified_by=admin_user,
        verified_date=timezone.now().date(),
    )
    data = _capamanagement_rca_base_data(
        capa_investigation_a,
        admin_user,
        status="verified",
        problem_statement="Updated Problem Statement on Verified RCA",
    )
    form = RootCauseAnalysisForm(instance=verified_rca, data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.problem_statement == "Updated Problem Statement on Verified RCA"
    assert saved.status == "verified"


def test_capamanagement_forms_rca_clean_status_allows_standard_statuses(capa_investigation_a, admin_user):
    """Standard statuses (draft, in_progress, completed, rejected) are valid for RCA form."""
    for st in ["draft", "in_progress", "completed", "rejected"]:
        data = _capamanagement_rca_base_data(capa_investigation_a, admin_user, status=st)
        form = RootCauseAnalysisForm(data=data, tenant=capa_investigation_a.tenant)
        assert form.is_valid(), f"RCA status '{st}' should be valid, but got: {form.errors}"


def test_capamanagement_forms_rca_parent_capa_immutability_on_edit(
    capa_investigation_a, admin_user, quality_department
):
    """Editing an existing RCA and changing its parent CAPA raises form validation error."""
    capa_alt = CapaInvestigation.objects.create(
        tenant=capa_investigation_a.tenant,
        title="Alternative CAPA Investigation",
        issue_summary="Another investigation in the same tenant.",
        action_type="corrective",
        source_type="complaint",
        risk_priority="low",
        department=quality_department,
        lead_investigator=admin_user,
        quality_owner=admin_user,
    )
    rca = RootCauseAnalysis.objects.create(
        tenant=capa_investigation_a.tenant,
        capa=capa_investigation_a,
        rca_method="5_whys",
        problem_statement="Initial RCA problem statement.",
        root_cause_summary="Initial RCA root cause.",
        lead_investigator=admin_user,
    )
    # Attempt to change capa to capa_alt
    data = _capamanagement_rca_base_data(capa_alt, admin_user)
    form = RootCauseAnalysisForm(instance=rca, data=data, tenant=capa_investigation_a.tenant)
    assert not form.is_valid()
    assert "capa" in form.errors
    assert "The parent CAPA investigation cannot be changed once established." in str(form.errors["capa"])


def test_capamanagement_forms_rca_tenant_scoping_querysets(
    tenant_a, tenant_b, capa_investigation_a, capa_investigation_b, admin_user, admin_b
):
    """Verify that capa and lead_investigator querysets are filtered to current tenant."""
    form = RootCauseAnalysisForm(tenant=tenant_a)

    capa_pks = list(form.fields["capa"].queryset.values_list("pk", flat=True))
    assert capa_investigation_a.pk in capa_pks
    assert capa_investigation_b.pk not in capa_pks

    lead_pks = list(form.fields["lead_investigator"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in lead_pks
    assert admin_b.pk not in lead_pks


def test_capamanagement_forms_rca_empty_querysets_without_tenant():
    """Verify querysets are empty when form is instantiated with tenant=None."""
    form = RootCauseAnalysisForm(tenant=None)
    assert form.fields["capa"].queryset.count() == 0
    assert form.fields["lead_investigator"].queryset.count() == 0


def test_capamanagement_forms_rca_cross_tenant_rejection(tenant_a, capa_investigation_b, admin_b):
    """Directly verify reject_foreign raises workspace error for capa and lead_investigator."""
    form = RootCauseAnalysisForm(tenant=tenant_a)
    form.cleaned_data = {
        "capa": capa_investigation_b,
        "lead_investigator": admin_b,
    }
    reject_foreign(form, form.cleaned_data, ["capa", "lead_investigator"])
    assert "capa" in form.errors
    assert "lead_investigator" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["capa"])


def test_capamanagement_forms_rca_inactive_users_excluded(tenant_a, admin_user):
    """Inactive users under tenant must be excluded from lead_investigator queryset."""
    inactive_user = _capamanagement_create_user(
        tenant_a, "inactive_rca_lead", "inactive.rca@acme.com", is_active=False
    )
    form = RootCauseAnalysisForm(tenant=tenant_a)
    lead_pks = list(form.fields["lead_investigator"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in lead_pks
    assert inactive_user.pk not in lead_pks


def test_capamanagement_forms_rca_save_persistence(capa_investigation_a, admin_user):
    """Verify saving RootCauseAnalysisForm attaches tenant and auto-numbers QRCA-."""
    data = _capamanagement_rca_base_data(capa_investigation_a, admin_user)
    form = RootCauseAnalysisForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == capa_investigation_a.tenant
    assert instance.number.startswith("QRCA-")


# =====================================================================
# 4. CapaActionForm Tests
# =====================================================================


def test_capamanagement_forms_action_valid_full_submission(
    capa_investigation_a,
    root_cause_analysis_a,
    admin_user,
    quality_department,
    quality_doc_draft,
    quality_dco,
    design_project_a,
):
    """Verify valid submission of CapaActionForm with cross-module links."""
    data = _capamanagement_action_base_data(
        capa_investigation_a,
        admin_user,
        root_cause=root_cause_analysis_a,
        department=quality_department,
        action_type="preventive",
        title="Revise Pressure Testing Protocol and Update DHF Specification",
        description="Update calibration SOP and link with Document Change Order DCO-001.",
        controlled_document=_capamanagement_pk(quality_doc_draft),
        change_order=_capamanagement_pk(quality_dco),
        design_project=_capamanagement_pk(design_project_a),
        implementation_notes="Draft revisions drafted and queued for review.",
        status="in_progress",
    )
    form = CapaActionForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    action = form.save()
    assert action.pk is not None
    assert action.tenant == capa_investigation_a.tenant
    assert action.number.startswith("QACT-")
    assert action.root_cause == root_cause_analysis_a
    assert action.controlled_document == quality_doc_draft
    assert action.change_order == quality_dco
    assert action.design_project == design_project_a


def test_capamanagement_forms_action_valid_minimal_submission(capa_investigation_a, admin_user):
    """Verify minimal submission of CapaActionForm with optional links omitted."""
    data = {
        "capa": capa_investigation_a.pk,
        "root_cause": "",
        "action_type": "corrective",
        "title": "Minimal Action Plan Task",
        "description": "Standard work instruction task description.",
        "assigned_to": admin_user.pk,
        "department": "",
        "due_date": (timezone.now() + timedelta(days=14)).date().isoformat(),
        "status": "pending",
        "implementation_notes": "",
        "controlled_document": "",
        "change_order": "",
        "design_project": "",
    }
    form = CapaActionForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    action = form.save()
    assert action.pk is not None
    assert action.root_cause is None
    assert action.status == "pending"


def test_capamanagement_forms_action_required_fields(tenant_a):
    """Verify required fields on CapaActionForm."""
    form = CapaActionForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "capa" in form.errors
    assert "title" in form.errors
    assert "description" in form.errors
    assert "assigned_to" in form.errors
    assert "due_date" in form.errors


def test_capamanagement_forms_action_cross_capa_validation_rejects_mismatched_rca(
    tenant_a, admin_user, quality_department, capa_investigation_a
):
    """Linking an action to CAPA A with a root cause belonging to CAPA B fails validation with descriptive error."""
    capa_alt = CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Second CAPA Investigation",
        issue_summary="Another investigation in the same tenant.",
        action_type="corrective",
        source_type="ncr",
        risk_priority="medium",
        department=quality_department,
        lead_investigator=admin_user,
        quality_owner=admin_user,
    )
    rca_alt = RootCauseAnalysis.objects.create(
        tenant=tenant_a,
        capa=capa_alt,
        rca_method="5_whys",
        problem_statement="Problem under alternative CAPA.",
        root_cause_summary="Root cause under alternative CAPA.",
        lead_investigator=admin_user,
    )
    data = _capamanagement_action_base_data(
        capa_investigation_a,
        admin_user,
        root_cause=rca_alt,
    )
    form = CapaActionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "root_cause" in form.errors
    assert "The selected Root Cause Analysis must belong to the selected CAPA investigation." in str(
        form.errors["root_cause"]
    )


def test_capamanagement_forms_action_cross_capa_validation_accepts_matching_rca(
    capa_investigation_a, root_cause_analysis_a, admin_user
):
    """Linking an action to CAPA A with a root cause belonging to CAPA A succeeds."""
    data = _capamanagement_action_base_data(
        capa_investigation_a,
        admin_user,
        root_cause=root_cause_analysis_a,
    )
    form = CapaActionForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors


def test_capamanagement_forms_action_accepts_none_root_cause(capa_investigation_a, admin_user):
    """Action without a linked root cause is valid."""
    data = _capamanagement_action_base_data(
        capa_investigation_a,
        admin_user,
        root_cause=None,
    )
    form = CapaActionForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors


def test_capamanagement_forms_action_parent_capa_immutability_on_edit(
    capa_action_a, admin_user, tenant_a, quality_department
):
    """Parent CAPA investigation cannot be changed once established."""
    capa_alt = CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Alternative CAPA for Action Reassignment Test",
        issue_summary="Another investigation in the same tenant.",
        action_type="corrective",
        source_type="ncr",
        risk_priority="low",
        department=quality_department,
        lead_investigator=admin_user,
        quality_owner=admin_user,
    )
    data = _capamanagement_action_base_data(
        capa_alt,
        admin_user,
        root_cause=None,
    )
    form = CapaActionForm(instance=capa_action_a, data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "capa" in form.errors
    assert "The parent CAPA investigation cannot be changed once established." in str(form.errors["capa"])


def test_capamanagement_forms_action_clean_status_disallows_verified_on_create(capa_investigation_a, admin_user):
    """clean_status must reject status='verified' on creation of a new action."""
    data = _capamanagement_action_base_data(capa_investigation_a, admin_user, status="verified")
    form = CapaActionForm(data=data, tenant=capa_investigation_a.tenant)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'verified' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_action_clean_status_disallows_verified_on_edit_when_not_verified(
    capa_action_a, admin_user
):
    """clean_status must reject updating status to 'verified' via standard form when not currently verified."""
    data = _capamanagement_action_base_data(capa_action_a.capa, admin_user, status="verified")
    form = CapaActionForm(instance=capa_action_a, data=data, tenant=capa_action_a.tenant)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'verified' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_action_clean_status_allows_verified_when_already_verified(
    capa_investigation_a, admin_user
):
    """clean_status allows saving with status='verified' if the existing action is already verified."""
    verified_action = CapaAction.objects.create(
        tenant=capa_investigation_a.tenant,
        capa=capa_investigation_a,
        action_type="corrective",
        title="Previously Verified Action",
        description="This action was already verified by QA.",
        assigned_to=admin_user,
        due_date=timezone.now().date(),
        status="verified",
        verified_by=admin_user,
        verified_on=timezone.now().date(),
    )
    data = _capamanagement_action_base_data(
        capa_investigation_a,
        admin_user,
        title="Updated Title on Verified Action",
        status="verified",
    )
    form = CapaActionForm(instance=verified_action, data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.title == "Updated Title on Verified Action"
    assert saved.status == "verified"


def test_capamanagement_forms_action_clean_status_allows_standard_statuses(capa_investigation_a, admin_user):
    """Standard statuses (pending, in_progress, implemented, cancelled) are accepted."""
    for st in ["pending", "in_progress", "implemented", "cancelled"]:
        data = _capamanagement_action_base_data(capa_investigation_a, admin_user, status=st)
        form = CapaActionForm(data=data, tenant=capa_investigation_a.tenant)
        assert form.is_valid(), f"Status '{st}' should be valid, but got: {form.errors}"


def test_capamanagement_forms_action_tenant_scoping_querysets(
    tenant_a,
    tenant_b,
    capa_investigation_a,
    capa_investigation_b,
    root_cause_analysis_a,
    root_cause_analysis_b,
    admin_user,
    admin_b,
    quality_department,
    quality_department_b,
    quality_doc_draft,
    quality_doc_b,
    quality_dco,
    quality_dco_b,
    design_project_a,
    design_project_b,
):
    """Verify all 7 foreign keys in CapaActionForm are tenant-scoped and root_cause selects related capa."""
    form = CapaActionForm(tenant=tenant_a)

    # capa
    capa_pks = list(form.fields["capa"].queryset.values_list("pk", flat=True))
    assert capa_investigation_a.pk in capa_pks
    assert capa_investigation_b.pk not in capa_pks

    # root_cause
    rca_qs = form.fields["root_cause"].queryset
    rca_pks = list(rca_qs.values_list("pk", flat=True))
    assert root_cause_analysis_a.pk in rca_pks
    assert root_cause_analysis_b.pk not in rca_pks
    # Verify select_related('capa') optimization on root_cause queryset
    assert "capa" in rca_qs.query.select_related

    # assigned_to
    user_pks = list(form.fields["assigned_to"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in user_pks
    assert admin_b.pk not in user_pks

    # department
    dept_pks = list(form.fields["department"].queryset.values_list("pk", flat=True))
    assert quality_department.pk in dept_pks
    assert quality_department_b.pk not in dept_pks

    # controlled_document
    doc_pks = list(form.fields["controlled_document"].queryset.values_list("pk", flat=True))
    assert quality_doc_draft.pk in doc_pks
    assert quality_doc_b.pk not in doc_pks

    # change_order
    dco_pks = list(form.fields["change_order"].queryset.values_list("pk", flat=True))
    assert quality_dco.pk in dco_pks
    assert quality_dco_b.pk not in dco_pks

    # design_project
    proj_pks = list(form.fields["design_project"].queryset.values_list("pk", flat=True))
    assert design_project_a.pk in proj_pks
    assert design_project_b.pk not in proj_pks


def test_capamanagement_forms_action_empty_querysets_without_tenant():
    """Verify all 7 foreign key querysets are empty when form is instantiated with tenant=None."""
    form = CapaActionForm(tenant=None)
    assert form.fields["capa"].queryset.count() == 0
    assert form.fields["root_cause"].queryset.count() == 0
    assert form.fields["assigned_to"].queryset.count() == 0
    assert form.fields["department"].queryset.count() == 0
    assert form.fields["controlled_document"].queryset.count() == 0
    assert form.fields["change_order"].queryset.count() == 0
    assert form.fields["design_project"].queryset.count() == 0


def test_capamanagement_forms_action_cross_tenant_rejection(
    tenant_a,
    capa_investigation_b,
    root_cause_analysis_b,
    admin_b,
    quality_department_b,
    quality_doc_b,
    quality_dco_b,
    design_project_b,
):
    """Directly verify reject_foreign raises workspace error on all 7 foreign fields."""
    form = CapaActionForm(tenant=tenant_a)
    form.cleaned_data = {
        "capa": capa_investigation_b,
        "root_cause": root_cause_analysis_b,
        "assigned_to": admin_b,
        "department": quality_department_b,
        "controlled_document": quality_doc_b,
        "change_order": quality_dco_b,
        "design_project": design_project_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        [
            "capa",
            "root_cause",
            "assigned_to",
            "department",
            "controlled_document",
            "change_order",
            "design_project",
        ],
    )
    for field_name in [
        "capa",
        "root_cause",
        "assigned_to",
        "department",
        "controlled_document",
        "change_order",
        "design_project",
    ]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


def test_capamanagement_forms_action_inactive_users_excluded(tenant_a, admin_user):
    """Inactive users under tenant must be excluded from assigned_to queryset."""
    inactive_user = _capamanagement_create_user(
        tenant_a, "inactive_action_owner", "inactive.action@acme.com", is_active=False
    )
    form = CapaActionForm(tenant=tenant_a)
    user_pks = list(form.fields["assigned_to"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in user_pks
    assert inactive_user.pk not in user_pks


def test_capamanagement_forms_action_save_persistence(capa_investigation_a, admin_user):
    """Verify saving CapaActionForm attaches tenant and auto-numbers QACT-."""
    data = _capamanagement_action_base_data(capa_investigation_a, admin_user)
    form = CapaActionForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == capa_investigation_a.tenant
    assert instance.number.startswith("QACT-")


# =====================================================================
# 5. CapaEffectivenessReviewForm Tests
# =====================================================================


def test_capamanagement_forms_review_valid_submission(capa_investigation_a, admin_user):
    """Verify valid submission of CapaEffectivenessReviewForm."""
    data = _capamanagement_review_base_data(
        capa_investigation_a,
        admin_user,
        verification_method="statistical_sample",
        planned_review_date=(timezone.now() + timedelta(days=60)).date().isoformat(),
        metrics_evaluated="Zero defect reports in 60-day post-market surveillance window.",
        recurrence_observed=False,
        outcome="effective",
        status="scheduled",
    )
    form = CapaEffectivenessReviewForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    review = form.save()
    assert review.pk is not None
    assert review.tenant == capa_investigation_a.tenant
    assert review.number.startswith("QEFF-")
    assert review.outcome == "effective"
    assert review.is_effective is True


def test_capamanagement_forms_review_required_fields(tenant_a):
    """Verify required fields on CapaEffectivenessReviewForm."""
    form = CapaEffectivenessReviewForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "capa" in form.errors
    assert "review_criteria" in form.errors
    assert "planned_review_date" in form.errors
    assert "evaluator" in form.errors


def test_capamanagement_forms_review_recurrence_safety_rejects_effective_when_recurrence_observed(
    capa_investigation_a, admin_user
):
    """Recurrence safety rule: outcome='effective' with recurrence_observed=True raises validation error on outcome."""
    data = _capamanagement_review_base_data(
        capa_investigation_a,
        admin_user,
        recurrence_observed=True,
        recurrence_details="2 defect instances observed during lot 104 burn-in inspection.",
        outcome="effective",
    )
    form = CapaEffectivenessReviewForm(data=data, tenant=capa_investigation_a.tenant)
    assert not form.is_valid()
    assert "outcome" in form.errors
    assert "Cannot mark review as 'Effective' when recurrence has been observed." in form.errors["outcome"][0]


def test_capamanagement_forms_review_recurrence_safety_allows_effective_when_no_recurrence(
    capa_investigation_a, admin_user
):
    """outcome='effective' is permitted when recurrence_observed=False."""
    data = _capamanagement_review_base_data(
        capa_investigation_a,
        admin_user,
        recurrence_observed=False,
        outcome="effective",
    )
    form = CapaEffectivenessReviewForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors


def test_capamanagement_forms_review_recurrence_safety_allows_ineffective_when_recurrence_observed(
    capa_investigation_a, admin_user
):
    """outcome='ineffective' is permitted and expected when recurrence_observed=True."""
    data = _capamanagement_review_base_data(
        capa_investigation_a,
        admin_user,
        recurrence_observed=True,
        recurrence_details="Sensor calibration drift recurred in 3 units from Lot 105.",
        outcome="ineffective",
    )
    form = CapaEffectivenessReviewForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.outcome == "ineffective"
    assert instance.recurrence_observed is True


def test_capamanagement_forms_review_recurrence_safety_allows_inconclusive_when_recurrence_observed(
    capa_investigation_a, admin_user
):
    """outcome='inconclusive' is permitted when recurrence_observed=True (requiring extended window)."""
    data = _capamanagement_review_base_data(
        capa_investigation_a,
        admin_user,
        recurrence_observed=True,
        recurrence_details="Indeterminate signal noise observed; sample size underpowered.",
        outcome="inconclusive",
    )
    form = CapaEffectivenessReviewForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.outcome == "inconclusive"


def test_capamanagement_forms_review_parent_capa_immutability_on_edit(
    capa_effectiveness_review_a, admin_user, tenant_a, quality_department
):
    """Parent CAPA investigation cannot be changed once established on an existing review."""
    capa_alt = CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Alternative CAPA for Review Immutability Test",
        issue_summary="Another investigation in the same tenant.",
        action_type="corrective",
        source_type="complaint",
        risk_priority="low",
        department=quality_department,
        lead_investigator=admin_user,
        quality_owner=admin_user,
    )
    data = _capamanagement_review_base_data(capa_alt, admin_user)
    form = CapaEffectivenessReviewForm(
        instance=capa_effectiveness_review_a, data=data, tenant=tenant_a
    )
    assert not form.is_valid()
    assert "capa" in form.errors
    assert "The parent CAPA investigation cannot be changed once established." in str(form.errors["capa"])


def test_capamanagement_forms_review_clean_status_disallows_completed_on_create(
    capa_investigation_a, admin_user
):
    """clean_status must reject status='completed' on creation of a new review."""
    data = _capamanagement_review_base_data(capa_investigation_a, admin_user, status="completed")
    form = CapaEffectivenessReviewForm(data=data, tenant=capa_investigation_a.tenant)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'completed' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_review_clean_status_disallows_completed_on_edit_when_not_completed(
    capa_effectiveness_review_a, admin_user
):
    """clean_status must reject updating status to 'completed' via standard form when not currently completed."""
    data = _capamanagement_review_base_data(
        capa_effectiveness_review_a.capa, admin_user, status="completed"
    )
    form = CapaEffectivenessReviewForm(
        instance=capa_effectiveness_review_a, data=data, tenant=capa_effectiveness_review_a.tenant
    )
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Status 'completed' cannot be set directly" in form.errors["status"][0]


def test_capamanagement_forms_review_clean_status_allows_completed_when_already_completed(
    capa_investigation_a, admin_user
):
    """clean_status allows saving with status='completed' if the existing review is already completed."""
    completed_review = CapaEffectivenessReview.objects.create(
        tenant=capa_investigation_a.tenant,
        capa=capa_investigation_a,
        review_criteria="Zero recurrence criteria.",
        verification_method="zero_recurrence_window",
        planned_review_date=timezone.now().date(),
        actual_review_date=timezone.now().date(),
        evaluator=admin_user,
        outcome="effective",
        status="completed",
    )
    data = _capamanagement_review_base_data(
        capa_investigation_a,
        admin_user,
        review_criteria="Updated Criteria on Completed Review",
        status="completed",
    )
    form = CapaEffectivenessReviewForm(
        instance=completed_review, data=data, tenant=capa_investigation_a.tenant
    )
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.review_criteria == "Updated Criteria on Completed Review"
    assert saved.status == "completed"


def test_capamanagement_forms_review_clean_status_allows_standard_statuses(capa_investigation_a, admin_user):
    """Standard statuses (scheduled, in_progress, cancelled) are valid for effectiveness review."""
    for st in ["scheduled", "in_progress", "cancelled"]:
        data = _capamanagement_review_base_data(capa_investigation_a, admin_user, status=st)
        form = CapaEffectivenessReviewForm(data=data, tenant=capa_investigation_a.tenant)
        assert form.is_valid(), f"Review status '{st}' should be valid, but got: {form.errors}"


def test_capamanagement_forms_review_tenant_scoping_querysets(
    tenant_a, tenant_b, capa_investigation_a, capa_investigation_b, admin_user, admin_b
):
    """Verify that capa and evaluator querysets are filtered to current tenant."""
    form = CapaEffectivenessReviewForm(tenant=tenant_a)

    capa_pks = list(form.fields["capa"].queryset.values_list("pk", flat=True))
    assert capa_investigation_a.pk in capa_pks
    assert capa_investigation_b.pk not in capa_pks

    eval_pks = list(form.fields["evaluator"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in eval_pks
    assert admin_b.pk not in eval_pks


def test_capamanagement_forms_review_empty_querysets_without_tenant():
    """Verify querysets are empty when form is instantiated with tenant=None."""
    form = CapaEffectivenessReviewForm(tenant=None)
    assert form.fields["capa"].queryset.count() == 0
    assert form.fields["evaluator"].queryset.count() == 0


def test_capamanagement_forms_review_cross_tenant_rejection(tenant_a, capa_investigation_b, admin_b):
    """Directly verify reject_foreign raises workspace error for capa and evaluator."""
    form = CapaEffectivenessReviewForm(tenant=tenant_a)
    form.cleaned_data = {
        "capa": capa_investigation_b,
        "evaluator": admin_b,
    }
    reject_foreign(form, form.cleaned_data, ["capa", "evaluator"])
    assert "capa" in form.errors
    assert "evaluator" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["capa"])


def test_capamanagement_forms_review_inactive_users_excluded(tenant_a, admin_user):
    """Inactive users under tenant must be excluded from evaluator queryset."""
    inactive_user = _capamanagement_create_user(
        tenant_a, "inactive_evaluator", "inactive.eval@acme.com", is_active=False
    )
    form = CapaEffectivenessReviewForm(tenant=tenant_a)
    eval_pks = list(form.fields["evaluator"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in eval_pks
    assert inactive_user.pk not in eval_pks


def test_capamanagement_forms_review_save_persistence(capa_investigation_a, admin_user):
    """Verify saving CapaEffectivenessReviewForm attaches tenant and auto-numbers QEFF-."""
    data = _capamanagement_review_base_data(capa_investigation_a, admin_user)
    form = CapaEffectivenessReviewForm(data=data, tenant=capa_investigation_a.tenant)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == capa_investigation_a.tenant
    assert instance.number.startswith("QEFF-")


# =====================================================================
# 6. Form Widgets and Attributes Tests
# =====================================================================


def test_capamanagement_forms_widgets_investigation_css_classes(tenant_a):
    """Verify CSS widget classes on CapaInvestigationForm."""
    form = CapaInvestigationForm(tenant=tenant_a)
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["issue_summary"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["action_type"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["source_type"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["risk_priority"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["containment_implemented"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["lead_investigator"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["quality_owner"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["department"].widget.attrs.get("class", "")
    assert (
        form.fields["target_closure_date"].widget.attrs.get("type")
        or getattr(form.fields["target_closure_date"].widget, "input_type", None)
    ) == "date"


def test_capamanagement_forms_widgets_rca_css_classes(tenant_a):
    """Verify CSS widget classes on RootCauseAnalysisForm."""
    form = RootCauseAnalysisForm(tenant=tenant_a)
    assert "form-select" in form.fields["capa"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["rca_method"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["problem_statement"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["why_1"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["fishbone_manpower"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["root_cause_category"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["root_cause_summary"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["status"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["lead_investigator"].widget.attrs.get("class", "")


def test_capamanagement_forms_widgets_action_css_classes(tenant_a):
    """Verify CSS widget classes on CapaActionForm."""
    form = CapaActionForm(tenant=tenant_a)
    assert "form-select" in form.fields["capa"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["root_cause"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["action_type"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["description"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["assigned_to"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["department"].widget.attrs.get("class", "")
    assert (
        form.fields["due_date"].widget.attrs.get("type")
        or getattr(form.fields["due_date"].widget, "input_type", None)
    ) == "date"
    assert "form-select" in form.fields["status"].widget.attrs.get("class", "")


def test_capamanagement_forms_widgets_review_css_classes(tenant_a):
    """Verify CSS widget classes on CapaEffectivenessReviewForm."""
    form = CapaEffectivenessReviewForm(tenant=tenant_a)
    assert "form-select" in form.fields["capa"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["review_criteria"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["verification_method"].widget.attrs.get("class", "")
    assert (
        form.fields["planned_review_date"].widget.attrs.get("type")
        or getattr(form.fields["planned_review_date"].widget, "input_type", None)
    ) == "date"
    assert "form-select" in form.fields["evaluator"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["recurrence_observed"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["outcome"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["status"].widget.attrs.get("class", "")
