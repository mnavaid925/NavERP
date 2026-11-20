"""Unit tests for Quality Management Sub-module 12.14: Management Review & Quality Planning Forms.

Tests cover:
1. QualityObjectiveForm:
   - Valid data creation
   - Tenant filtering on owner and org_unit
   - reject_foreign rejection of cross-tenant owner and org_unit (both direct and bound)
   - Exclusion of system/governance fields (tenant, number, rag_status, last_evaluated_date)
   - Validation of missing required fields and optional field defaults
2. QualityObjectiveEvaluateForm:
   - Valid decimal values and evaluation notes
   - Step attribute validation ('0.001') on NumberInput widget
   - Required field enforcement for current_value
   - Invalid decimal inputs
3. ManagementReviewForm:
   - Valid data creation
   - Tenant filtering on executive_sponsor, lead_facilitator, and org_unit
   - reject_foreign rejection of cross-tenant sponsor, facilitator, and org_unit (both direct and bound)
   - Exclusion of system/governance fields (tenant, number, status, approved_by, approved_at, electronic_signature)
   - Period date validation (period_start <= period_end)
4. ManagementReviewMinutesForm:
   - Validation of minutes drafting fields (actual_meeting_date, attendees_roster, quorum_met,
     qms_suitability_conclusion, executive_summary, minutes_discussion, resource_decisions)
   - Suitability conclusion choices validation
   - Excluded header and system fields
5. ManagementReviewApproveForm:
   - Certification boolean requirement and optional comment
6. ManagementReviewInputForm:
   - Valid data creation with/without linked quality records
   - Tenant filtering on management_review, presenter, linked_audit, linked_capa, linked_complaint, linked_ncr
   - reject_foreign rejection of foreign linked objects (both direct and bound)
   - Exclusion of system fields (tenant, number, status)
7. ManagementReviewActionForm:
   - Valid data creation with/without spawned records
   - Tenant filtering on management_review, assignee, spawned_capa, spawned_change_order
   - reject_foreign rejection of foreign assignee and linked records (both direct and bound)
   - Exclusion of system and verification fields (tenant, number, status, verified_by, completion_date, resolution_summary, verification_notes)
8. ManagementReviewActionCompleteForm and ManagementReviewActionVerifyForm:
   - Required narrative validation and whitespace rejection
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.forms import NumberInput
from django.utils import timezone

from apps.quality.forms._common import reject_foreign
from apps.quality.forms.ManagementReview import (
    ManagementReviewActionCompleteForm,
    ManagementReviewActionForm,
    ManagementReviewActionVerifyForm,
    ManagementReviewApproveForm,
    ManagementReviewForm,
    ManagementReviewInputForm,
    ManagementReviewMinutesForm,
    QualityObjectiveEvaluateForm,
    QualityObjectiveForm,
)
from apps.quality.models import (
    ManagementReview,
    ManagementReviewAction,
    ManagementReviewInput,
    QualityObjective,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (Prefixed with _managementreview_*)
# ==============================================================================

def _managementreview_objective_payload(owner_pk, org_unit_pk=None, **overrides):
    """Generate a default valid payload for QualityObjectiveForm."""
    today = timezone.now().date()
    data = {
        "title": "Reduce Customer RMA Incident Rate < 0.50%",
        "description": "Continuous improvement initiative to lower device return authorizations.",
        "category": "product_quality",
        "period_year": today.year,
        "cadence": "quarterly",
        "metric_unit": "%",
        "baseline_value": "1.200",
        "target_value": "0.500",
        "current_value": "0.450",
        "target_direction": "lower_better",
        "status": "draft",
        "owner": owner_pk,
        "target_date": today + timedelta(days=90),
        "action_plan_summary": "Automated in-circuit testing enhancement on sub-assembly lines.",
        "notes": "Reviewed in quarterly QMS planning committee.",
    }
    if org_unit_pk is not None:
        data["org_unit"] = org_unit_pk
    data.update(overrides)
    return data


def _managementreview_review_payload(sponsor_pk, facilitator_pk, org_unit_pk=None, **overrides):
    """Generate a default valid payload for ManagementReviewForm."""
    today = timezone.now().date()
    data = {
        "title": "Q3 Executive QMS Suitability & Performance Review",
        "cadence": "quarterly",
        "period_start": today - timedelta(days=90),
        "period_end": today,
        "scheduled_date": today + timedelta(days=14),
        "location": "Boardroom A / Microsoft Teams",
        "executive_sponsor": sponsor_pk,
        "lead_facilitator": facilitator_pk,
        "notes": "Formal periodic executive review.",
    }
    if org_unit_pk is not None:
        data["org_unit"] = org_unit_pk
    data.update(overrides)
    return data


def _managementreview_input_payload(review_pk, presenter_pk, **overrides):
    """Generate a default valid payload for ManagementReviewInputForm."""
    data = {
        "management_review": review_pk,
        "agenda_order": 1,
        "title": "Internal & Supplier Quality Audit Performance Summary",
        "category": "audit_results",
        "presenter": presenter_pk,
        "summary_findings": "12 internal audits executed; 3 minor findings identified and resolved.",
        "metrics_data": "Audit pass rate: 95.8%, Repeat findings: 0",
        "attachments_summary": "Slides: Audit_Q3_Summary.pdf",
        "notes": "All actions closed within statutory 30-day window.",
    }
    data.update(overrides)
    return data


def _managementreview_action_payload(review_pk, assignee_pk, **overrides):
    """Generate a default valid payload for ManagementReviewActionForm."""
    today = timezone.now().date()
    data = {
        "management_review": review_pk,
        "title": "Procure Automated Optical Inspection (AOI) Station",
        "action_type": "resource_allocation",
        "priority": "high",
        "assignee": assignee_pk,
        "due_date": today + timedelta(days=45),
        "budget_allocated": "25000.00",
        "description": "Capital expenditure approval for surface-mount line inspection upgrade.",
        "notes": "PO to be issued upon vendor validation review.",
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. QualityObjectiveForm Unit Tests
# ==============================================================================

def test_managementreview_quality_objective_form_valid(tenant_a, admin_user, quality_department):
    """Valid data creates QualityObjective instance and persists correctly."""
    data = _managementreview_objective_payload(
        owner_pk=admin_user.pk,
        org_unit_pk=quality_department.pk,
    )
    form = QualityObjectiveForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()

    assert obj.pk is not None
    assert obj.number.startswith("QOBJ-")
    assert obj.title == "Reduce Customer RMA Incident Rate < 0.50%"
    assert obj.category == "product_quality"
    assert obj.owner == admin_user
    assert obj.org_unit == quality_department
    assert obj.target_value == Decimal("0.500")
    assert obj.baseline_value == Decimal("1.200")
    assert obj.current_value == Decimal("0.450")


def test_managementreview_quality_objective_form_excluded_fields(tenant_a):
    """System and autocalculated fields must be excluded from the form."""
    form = QualityObjectiveForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "rag_status" not in form.fields
    assert "last_evaluated_date" not in form.fields


def test_managementreview_quality_objective_form_tenant_filtering(
    tenant_a, tenant_b, admin_user, staff_user, admin_b, quality_department, quality_department_b
):
    """Querysets for owner and org_unit must be strictly scoped to the active tenant."""
    # Create an inactive user for tenant_a to verify exclusion
    inactive_user = User.objects.create_user(
        username="inactive_qa_user",
        email="inactive@example.com",
        password="secretpassword",
        tenant=tenant_a,
        is_active=False,
    )

    form = QualityObjectiveForm(tenant=tenant_a)
    owner_qs = form.fields["owner"].queryset
    org_unit_qs = form.fields["org_unit"].queryset

    # Owner queryset contains active users of tenant_a
    assert admin_user in owner_qs
    assert staff_user in owner_qs
    # Excludes inactive user and cross-tenant user
    assert inactive_user not in owner_qs
    assert admin_b not in owner_qs

    # Org unit queryset contains tenant_a org units only
    assert quality_department in org_unit_qs
    assert quality_department_b not in org_unit_qs


def test_managementreview_quality_objective_form_reject_foreign_direct(
    tenant_a, admin_b, quality_department_b
):
    """Directly test reject_foreign on QualityObjectiveForm cleaned_data."""
    form = QualityObjectiveForm(tenant=tenant_a)
    form.cleaned_data = {
        "owner": admin_b,
        "org_unit": quality_department_b,
    }
    form.clean()
    assert "owner" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["owner"])
    assert "org_unit" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["org_unit"])


def test_managementreview_quality_objective_form_reject_foreign_bound(
    tenant_a, admin_b, quality_department_b
):
    """Bound QualityObjectiveForm rejects foreign owner and org_unit PKs."""
    data = _managementreview_objective_payload(
        owner_pk=admin_b.pk,
        org_unit_pk=quality_department_b.pk,
    )
    form = QualityObjectiveForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors
    assert "org_unit" in form.errors


def test_managementreview_quality_objective_form_missing_required_fields(tenant_a):
    """Title, description, target_value, and owner are mandatory."""
    form = QualityObjectiveForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "description" in form.errors
    assert "target_value" in form.errors
    assert "owner" in form.errors


def test_managementreview_quality_objective_form_optional_fields_blank(tenant_a, admin_user):
    """Baseline value, current value, org_unit, target_date, action_plan_summary, notes can be omitted."""
    today = timezone.now().date()
    data = {
        "title": "Minimal Required Quality Objective",
        "description": "Baseline specification without optional fields.",
        "category": "continuous_improvement",
        "period_year": today.year,
        "cadence": "annual",
        "metric_unit": "Hours",
        "target_value": "100.000",
        "target_direction": "higher_better",
        "status": "draft",
        "owner": admin_user.pk,
    }
    form = QualityObjectiveForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()

    assert obj.pk is not None
    assert obj.baseline_value is None
    assert obj.current_value is None
    assert obj.org_unit is None
    assert obj.target_date is None
    assert obj.action_plan_summary == ""
    assert obj.notes == ""


# ==============================================================================
# 2. QualityObjectiveEvaluateForm Unit Tests
# ==============================================================================

def test_managementreview_quality_objective_evaluate_form_valid():
    """Valid decimal values and notes pass evaluation form."""
    form = QualityObjectiveEvaluateForm(data={
        "current_value": "98.500",
        "notes": "Significant gain following calibration improvements.",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["current_value"] == Decimal("98.500")
    assert form.cleaned_data["notes"] == "Significant gain following calibration improvements."


def test_managementreview_quality_objective_evaluate_form_widget_step():
    """Evaluate form current_value widget must configure 3-decimal step precision."""
    form = QualityObjectiveEvaluateForm()
    widget = form.fields["current_value"].widget
    assert isinstance(widget, NumberInput)
    assert widget.attrs.get("step") == "0.001"
    assert "form-input" in widget.attrs.get("class", "")


def test_managementreview_quality_objective_evaluate_form_required_value():
    """Current value is strictly required when evaluating an objective."""
    form = QualityObjectiveEvaluateForm(data={"notes": "No numeric value provided."})
    assert not form.is_valid()
    assert "current_value" in form.errors


def test_managementreview_quality_objective_evaluate_form_invalid_decimal():
    """Non-numeric values or exceeding precision are rejected."""
    form = QualityObjectiveEvaluateForm(data={"current_value": "not-a-number"})
    assert not form.is_valid()
    assert "current_value" in form.errors

    # Exceeding 12 digits max
    form_overflow = QualityObjectiveEvaluateForm(data={"current_value": "1234567890123.456"})
    assert not form_overflow.is_valid()
    assert "current_value" in form_overflow.errors


def test_managementreview_quality_objective_evaluate_form_notes_optional():
    """Evaluation notes are optional and form is valid without commentary."""
    form = QualityObjectiveEvaluateForm(data={"current_value": "12.340"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["notes"] == ""


# ==============================================================================
# 3. ManagementReviewForm Unit Tests
# ==============================================================================

def test_managementreview_review_form_valid(tenant_a, admin_user, staff_user, quality_department):
    """Valid data creates ManagementReview instance with tenant isolation."""
    data = _managementreview_review_payload(
        sponsor_pk=admin_user.pk,
        facilitator_pk=staff_user.pk,
        org_unit_pk=quality_department.pk,
    )
    form = ManagementReviewForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    review = form.save(commit=False)
    review.tenant = tenant_a
    review.save()

    assert review.pk is not None
    assert review.number.startswith("QMRV-")
    assert review.title == "Q3 Executive QMS Suitability & Performance Review"
    assert review.cadence == "quarterly"
    assert review.executive_sponsor == admin_user
    assert review.lead_facilitator == staff_user
    assert review.org_unit == quality_department
    assert review.status == "scheduled"
    assert review.qms_suitability_conclusion == "pending"


def test_managementreview_review_form_excluded_fields(tenant_a):
    """System, workflow status, approval, and meeting minutes fields must be excluded."""
    form = ManagementReviewForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "status",
        "approved_by",
        "approved_at",
        "electronic_signature",
        "actual_meeting_date",
        "attendees_roster",
        "quorum_met",
        "qms_suitability_conclusion",
        "executive_summary",
        "minutes_discussion",
        "resource_decisions",
    ]
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} should be excluded from ManagementReviewForm"


def test_managementreview_review_form_tenant_filtering(
    tenant_a, tenant_b, admin_user, staff_user, admin_b, quality_department, quality_department_b
):
    """Executive sponsor, lead facilitator, and org unit must be filtered to tenant_a."""
    inactive_user = User.objects.create_user(
        username="inactive_exec_user",
        email="inactive_exec@example.com",
        password="secretpassword",
        tenant=tenant_a,
        is_active=False,
    )

    form = ManagementReviewForm(tenant=tenant_a)
    sponsor_qs = form.fields["executive_sponsor"].queryset
    facilitator_qs = form.fields["lead_facilitator"].queryset
    org_unit_qs = form.fields["org_unit"].queryset

    assert admin_user in sponsor_qs
    assert staff_user in sponsor_qs
    assert inactive_user not in sponsor_qs
    assert admin_b not in sponsor_qs

    assert admin_user in facilitator_qs
    assert staff_user in facilitator_qs
    assert inactive_user not in facilitator_qs
    assert admin_b not in facilitator_qs

    assert quality_department in org_unit_qs
    assert quality_department_b not in org_unit_qs


def test_managementreview_review_form_reject_foreign_direct(
    tenant_a, admin_b, quality_department_b
):
    """Directly test reject_foreign on ManagementReviewForm cleaned_data."""
    form = ManagementReviewForm(tenant=tenant_a)
    form.cleaned_data = {
        "executive_sponsor": admin_b,
        "lead_facilitator": admin_b,
        "org_unit": quality_department_b,
    }
    form.clean()
    assert "executive_sponsor" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["executive_sponsor"])
    assert "lead_facilitator" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["lead_facilitator"])
    assert "org_unit" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["org_unit"])


def test_managementreview_review_form_reject_foreign_bound(
    tenant_a, admin_b, quality_department_b
):
    """Bound ManagementReviewForm rejects foreign sponsor, facilitator, and org unit PKs."""
    data = _managementreview_review_payload(
        sponsor_pk=admin_b.pk,
        facilitator_pk=admin_b.pk,
        org_unit_pk=quality_department_b.pk,
    )
    form = ManagementReviewForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "executive_sponsor" in form.errors
    assert "lead_facilitator" in form.errors
    assert "org_unit" in form.errors


def test_managementreview_review_form_period_date_validation(tenant_a, admin_user, staff_user):
    """period_start after period_end must fail validation with specific error."""
    today = timezone.now().date()
    data = _managementreview_review_payload(
        sponsor_pk=admin_user.pk,
        facilitator_pk=staff_user.pk,
        period_start=today,
        period_end=today - timedelta(days=1),
    )
    form = ManagementReviewForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "period_end" in form.errors
    assert "Period end date cannot precede period start date." in form.errors["period_end"]


def test_managementreview_review_form_period_dates_equal_valid(tenant_a, admin_user, staff_user):
    """Single-day review periods (period_start == period_end) are valid."""
    today = timezone.now().date()
    data = _managementreview_review_payload(
        sponsor_pk=admin_user.pk,
        facilitator_pk=staff_user.pk,
        period_start=today,
        period_end=today,
    )
    form = ManagementReviewForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


# ==============================================================================
# 4. ManagementReviewMinutesForm Unit Tests
# ==============================================================================

def test_managementreview_minutes_form_valid(management_review_a):
    """Minutes drafting fields update review instance correctly."""
    today = timezone.now().date()
    data = {
        "actual_meeting_date": today,
        "attendees_roster": "Executive Committee:\n1. John Smith (CEO)\n2. Jane Doe (QA VP)\n3. Mark Lee (Ops VP)",
        "quorum_met": True,
        "qms_suitability_conclusion": "suitable_effective",
        "executive_summary": "QMS demonstrated continuous adequacy and effectiveness during Q3 audit period.",
        "minutes_discussion": "Thorough discussion of supplier scorecard trending, CAPA cycle times, and validation protocols.",
        "resource_decisions": "Approved $50,000 capital expenditure for vision inspection station upgrade.",
        "notes": "Follow-up meeting scheduled in 90 days.",
    }
    form = ManagementReviewMinutesForm(data=data, instance=management_review_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.actual_meeting_date == today
    assert updated.quorum_met is True
    assert updated.qms_suitability_conclusion == "suitable_effective"
    assert "Executive Committee" in updated.attendees_roster
    assert "$50,000" in updated.resource_decisions


def test_managementreview_minutes_form_excluded_fields(management_review_a):
    """Initial header and system fields must be excluded from minutes drafting form."""
    form = ManagementReviewMinutesForm(instance=management_review_a)
    excluded = [
        "title",
        "tenant",
        "number",
        "cadence",
        "period_start",
        "period_end",
        "scheduled_date",
        "executive_sponsor",
        "lead_facilitator",
        "status",
        "approved_by",
        "approved_at",
        "electronic_signature",
    ]
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} should not be in MinutesForm"


def test_managementreview_minutes_form_quorum_false_valid(management_review_a):
    """Minutes form correctly captures quorum_met = False."""
    today = timezone.now().date()
    data = {
        "actual_meeting_date": today,
        "attendees_roster": "Jane Doe only (Adjourned due to lack of quorum)",
        "quorum_met": False,
        "qms_suitability_conclusion": "pending",
        "executive_summary": "Meeting adjourned.",
        "minutes_discussion": "Quorum was not attained.",
        "resource_decisions": "",
        "notes": "",
    }
    form = ManagementReviewMinutesForm(data=data, instance=management_review_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.quorum_met is False


def test_managementreview_minutes_form_suitability_choices_validation(management_review_a):
    """Only defined SUITABILITY_CHOICES are permitted."""
    valid_choices = ["pending", "suitable_effective", "minor_improvements", "systemic_deficiencies"]
    for choice in valid_choices:
        form = ManagementReviewMinutesForm(
            data={"qms_suitability_conclusion": choice, "quorum_met": True},
            instance=management_review_a,
        )
        assert form.is_valid(), f"Choice '{choice}' should be valid: {form.errors}"

    form_invalid = ManagementReviewMinutesForm(
        data={"qms_suitability_conclusion": "unsupported_value", "quorum_met": True},
        instance=management_review_a,
    )
    assert not form_invalid.is_valid()
    assert "qms_suitability_conclusion" in form_invalid.errors


def test_managementreview_minutes_form_optional_fields(management_review_a):
    """Text areas and notes can be blank in minutes drafting."""
    data = {
        "actual_meeting_date": "",
        "attendees_roster": "",
        "quorum_met": True,
        "qms_suitability_conclusion": "pending",
        "executive_summary": "",
        "minutes_discussion": "",
        "resource_decisions": "",
        "notes": "",
    }
    form = ManagementReviewMinutesForm(data=data, instance=management_review_a)
    assert form.is_valid(), form.errors


# ==============================================================================
# 5. ManagementReviewApproveForm Unit Tests
# ==============================================================================

def test_managementreview_approve_form_valid():
    """Approve form requires confirmation boolean and accepts optional comments."""
    form = ManagementReviewApproveForm(data={
        "confirm_suitability": True,
        "comment": "Formally approved by Executive Committee Chair.",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["confirm_suitability"] is True
    assert form.cleaned_data["comment"] == "Formally approved by Executive Committee Chair."


def test_managementreview_approve_form_requires_confirmation():
    """Failing to check confirm_suitability blocks executive approval."""
    form = ManagementReviewApproveForm(data={
        "confirm_suitability": False,
        "comment": "Remarks without ticking checkbox.",
    })
    assert not form.is_valid()
    assert "confirm_suitability" in form.errors

    form_missing = ManagementReviewApproveForm(data={"comment": "No checkbox."})
    assert not form_missing.is_valid()
    assert "confirm_suitability" in form_missing.errors


def test_managementreview_approve_form_comment_optional():
    """Executive sign-off comment is optional if confirmation is checked."""
    form = ManagementReviewApproveForm(data={"confirm_suitability": True})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["comment"] == ""


# ==============================================================================
# 6. ManagementReviewInputForm Unit Tests
# ==============================================================================

def test_managementreview_input_form_valid(
    tenant_a, management_review_a, admin_user, quality_audit_a, capa_investigation_a,
    customer_complaint_a, ncr_a
):
    """Valid data with all linked quality entities creates review input instance."""
    data = _managementreview_input_payload(
        review_pk=management_review_a.pk,
        presenter_pk=admin_user.pk,
        linked_audit=quality_audit_a.pk,
        linked_capa=capa_investigation_a.pk,
        linked_complaint=customer_complaint_a.pk,
        linked_ncr=ncr_a.pk,
    )
    form = ManagementReviewInputForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    inp = form.save(commit=False)
    inp.tenant = tenant_a
    inp.save()

    assert inp.pk is not None
    assert inp.number.startswith("QMRI-")
    assert inp.management_review == management_review_a
    assert inp.presenter == admin_user
    assert inp.linked_audit == quality_audit_a
    assert inp.linked_capa == capa_investigation_a
    assert inp.linked_complaint == customer_complaint_a
    assert inp.linked_ncr == ncr_a
    assert inp.status == "draft"


def test_managementreview_input_form_without_linked_records(
    tenant_a, management_review_a, admin_user
):
    """Review input without linked quality records is valid."""
    data = _managementreview_input_payload(
        review_pk=management_review_a.pk,
        presenter_pk=admin_user.pk,
    )
    form = ManagementReviewInputForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    inp = form.save(commit=False)
    inp.tenant = tenant_a
    inp.save()

    assert inp.pk is not None
    assert inp.linked_audit is None
    assert inp.linked_capa is None
    assert inp.linked_complaint is None
    assert inp.linked_ncr is None


def test_managementreview_input_form_excluded_fields(tenant_a):
    """System fields tenant, number, and status must be excluded from input form."""
    form = ManagementReviewInputForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "status" not in form.fields


def test_managementreview_input_form_tenant_filtering(
    tenant_a, tenant_b, admin_user, admin_b, management_review_a, management_review_b,
    quality_audit_a, quality_audit_b, capa_investigation_a, capa_investigation_b,
    customer_complaint_a, customer_complaint_b, ncr_a, ncr_b
):
    """All foreign key querysets on input form must be scoped to tenant_a."""
    inactive_user = User.objects.create_user(
        username="inactive_presenter",
        email="inactive_presenter@example.com",
        password="secretpassword",
        tenant=tenant_a,
        is_active=False,
    )

    form = ManagementReviewInputForm(tenant=tenant_a)

    # Management review queryset
    mrv_qs = form.fields["management_review"].queryset
    assert management_review_a in mrv_qs
    assert management_review_b not in mrv_qs

    # Presenter queryset
    pres_qs = form.fields["presenter"].queryset
    assert admin_user in pres_qs
    assert inactive_user not in pres_qs
    assert admin_b not in pres_qs

    # Linked quality records querysets
    assert quality_audit_a in form.fields["linked_audit"].queryset
    assert quality_audit_b not in form.fields["linked_audit"].queryset

    assert capa_investigation_a in form.fields["linked_capa"].queryset
    assert capa_investigation_b not in form.fields["linked_capa"].queryset

    assert customer_complaint_a in form.fields["linked_complaint"].queryset
    assert customer_complaint_b not in form.fields["linked_complaint"].queryset

    assert ncr_a in form.fields["linked_ncr"].queryset
    assert ncr_b not in form.fields["linked_ncr"].queryset


def test_managementreview_input_form_reject_foreign_direct(
    tenant_a, management_review_b, admin_b, quality_audit_b, capa_investigation_b,
    customer_complaint_b, ncr_b
):
    """Directly test reject_foreign on ManagementReviewInputForm cleaned_data."""
    form = ManagementReviewInputForm(tenant=tenant_a)
    form.cleaned_data = {
        "management_review": management_review_b,
        "presenter": admin_b,
        "linked_audit": quality_audit_b,
        "linked_capa": capa_investigation_b,
        "linked_complaint": customer_complaint_b,
        "linked_ncr": ncr_b,
    }
    form.clean()
    for field_name in ["management_review", "presenter", "linked_audit", "linked_capa", "linked_complaint", "linked_ncr"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


def test_managementreview_input_form_reject_foreign_bound(
    tenant_a, management_review_b, admin_b, quality_audit_b, capa_investigation_b,
    customer_complaint_b, ncr_b
):
    """Bound ManagementReviewInputForm rejects foreign linked PKs."""
    data = _managementreview_input_payload(
        review_pk=management_review_b.pk,
        presenter_pk=admin_b.pk,
        linked_audit=quality_audit_b.pk,
        linked_capa=capa_investigation_b.pk,
        linked_complaint=customer_complaint_b.pk,
        linked_ncr=ncr_b.pk,
    )
    form = ManagementReviewInputForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "management_review" in form.errors
    assert "presenter" in form.errors
    assert "linked_audit" in form.errors
    assert "linked_capa" in form.errors
    assert "linked_complaint" in form.errors
    assert "linked_ncr" in form.errors


def test_managementreview_input_form_missing_required_fields(tenant_a):
    """management_review, title, summary_findings, and presenter are required."""
    form = ManagementReviewInputForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "management_review" in form.errors
    assert "title" in form.errors
    assert "summary_findings" in form.errors
    assert "presenter" in form.errors


# ==============================================================================
# 7. ManagementReviewActionForm Unit Tests
# ==============================================================================

def test_managementreview_action_form_valid(
    tenant_a, management_review_a, admin_user, capa_investigation_a, quality_dco
):
    """Valid data with spawned CAPA and change order creates action instance."""
    data = _managementreview_action_payload(
        review_pk=management_review_a.pk,
        assignee_pk=admin_user.pk,
        spawned_capa=capa_investigation_a.pk,
        spawned_change_order=quality_dco.pk,
    )
    form = ManagementReviewActionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    act = form.save(commit=False)
    act.tenant = tenant_a
    act.save()

    assert act.pk is not None
    assert act.number.startswith("QMRA-")
    assert act.management_review == management_review_a
    assert act.assignee == admin_user
    assert act.spawned_capa == capa_investigation_a
    assert act.spawned_change_order == quality_dco
    assert act.budget_allocated == Decimal("25000.00")
    assert act.status == "open"


def test_managementreview_action_form_without_spawned_records(
    tenant_a, management_review_a, admin_user
):
    """Action without spawned CAPA or change order is valid."""
    data = _managementreview_action_payload(
        review_pk=management_review_a.pk,
        assignee_pk=admin_user.pk,
    )
    form = ManagementReviewActionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    act = form.save(commit=False)
    act.tenant = tenant_a
    act.save()

    assert act.pk is not None
    assert act.spawned_capa is None
    assert act.spawned_change_order is None


def test_managementreview_action_form_excluded_fields(tenant_a):
    """System, workflow status, completion, and QA verification fields must be excluded."""
    form = ManagementReviewActionForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "status",
        "verified_by",
        "completion_date",
        "resolution_summary",
        "verification_notes",
    ]
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} should be excluded from ManagementReviewActionForm"


def test_managementreview_action_form_tenant_filtering(
    tenant_a, tenant_b, admin_user, admin_b, management_review_a, management_review_b,
    capa_investigation_a, capa_investigation_b, quality_dco, quality_dco_b
):
    """management_review, assignee, spawned_capa, and spawned_change_order must be tenant-filtered."""
    inactive_user = User.objects.create_user(
        username="inactive_assignee",
        email="inactive_assignee@example.com",
        password="secretpassword",
        tenant=tenant_a,
        is_active=False,
    )

    form = ManagementReviewActionForm(tenant=tenant_a)

    # Management review queryset
    mrv_qs = form.fields["management_review"].queryset
    assert management_review_a in mrv_qs
    assert management_review_b not in mrv_qs

    # Assignee queryset
    assignee_qs = form.fields["assignee"].queryset
    assert admin_user in assignee_qs
    assert inactive_user not in assignee_qs
    assert admin_b not in assignee_qs

    # Spawned CAPA and change order querysets
    assert capa_investigation_a in form.fields["spawned_capa"].queryset
    assert capa_investigation_b not in form.fields["spawned_capa"].queryset

    assert quality_dco in form.fields["spawned_change_order"].queryset
    assert quality_dco_b not in form.fields["spawned_change_order"].queryset


def test_managementreview_action_form_reject_foreign_direct(
    tenant_a, management_review_b, admin_b, capa_investigation_b, quality_dco_b
):
    """Directly test reject_foreign on ManagementReviewActionForm cleaned_data."""
    form = ManagementReviewActionForm(tenant=tenant_a)
    form.cleaned_data = {
        "management_review": management_review_b,
        "assignee": admin_b,
        "spawned_capa": capa_investigation_b,
        "spawned_change_order": quality_dco_b,
    }
    form.clean()
    for field_name in ["management_review", "assignee", "spawned_capa", "spawned_change_order"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


def test_managementreview_action_form_reject_foreign_bound(
    tenant_a, management_review_b, admin_b, capa_investigation_b, quality_dco_b
):
    """Bound ManagementReviewActionForm rejects foreign assignee and linked records."""
    data = _managementreview_action_payload(
        review_pk=management_review_b.pk,
        assignee_pk=admin_b.pk,
        spawned_capa=capa_investigation_b.pk,
        spawned_change_order=quality_dco_b.pk,
    )
    form = ManagementReviewActionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "management_review" in form.errors
    assert "assignee" in form.errors
    assert "spawned_capa" in form.errors
    assert "spawned_change_order" in form.errors


def test_managementreview_action_form_missing_required_fields(tenant_a):
    """management_review, title, description, assignee, and due_date are mandatory."""
    form = ManagementReviewActionForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "management_review" in form.errors
    assert "title" in form.errors
    assert "description" in form.errors
    assert "assignee" in form.errors
    assert "due_date" in form.errors


# ==============================================================================
# 8. Complete & Verify Action Forms Unit Tests
# ==============================================================================

def test_managementreview_action_complete_form_valid():
    """Action completion form accepts valid implementation resolution summary."""
    form = ManagementReviewActionCompleteForm(data={
        "resolution_summary": "AOI station installed, calibrated, and IQ/OQ protocols signed off successfully.",
    })
    assert form.is_valid(), form.errors
    assert "IQ/OQ protocols" in form.cleaned_data["resolution_summary"]


def test_managementreview_action_complete_form_required():
    """Resolution summary is strictly required and cannot be blank or missing."""
    form_blank = ManagementReviewActionCompleteForm(data={"resolution_summary": ""})
    assert not form_blank.is_valid()
    assert "resolution_summary" in form_blank.errors

    form_whitespace = ManagementReviewActionCompleteForm(data={"resolution_summary": "   "})
    assert not form_whitespace.is_valid()
    assert "resolution_summary" in form_whitespace.errors

    form_missing = ManagementReviewActionCompleteForm(data={})
    assert not form_missing.is_valid()
    assert "resolution_summary" in form_missing.errors


def test_managementreview_action_verify_form_valid():
    """Action verification form accepts valid QA verification effectiveness evidence."""
    form = ManagementReviewActionVerifyForm(data={
        "verification_notes": "QA Director verified 30 consecutive inspection lots with zero false-positive stops.",
    })
    assert form.is_valid(), form.errors
    assert "QA Director verified" in form.cleaned_data["verification_notes"]


def test_managementreview_action_verify_form_required():
    """Verification notes are strictly required and cannot be blank or missing."""
    form_blank = ManagementReviewActionVerifyForm(data={"verification_notes": ""})
    assert not form_blank.is_valid()
    assert "verification_notes" in form_blank.errors

    form_whitespace = ManagementReviewActionVerifyForm(data={"verification_notes": "   "})
    assert not form_whitespace.is_valid()
    assert "verification_notes" in form_whitespace.errors

    form_missing = ManagementReviewActionVerifyForm(data={})
    assert not form_missing.is_valid()
    assert "verification_notes" in form_missing.errors
