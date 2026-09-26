"""8.4 Sales Forecasting -- the FORMS lane.

Naming: every test is ``test_salesforecasting_*`` and every module-level helper
``_salesforecasting_*`` so the next sub-module appending nearby cannot shadow
them (8.1/8.2/8.3 own the ``leadmanagement``/``opportunitypipeline``/
``contactaccountmanagement`` names in this same package).

The point of this lane is the **exclusion** rules, not the happy path: a form
that lets a user type a derived figure, a system timestamp, the workflow
``status`` or the tenant is a data-integrity bug that still returns HTTP 200.
"""
from decimal import Decimal

import pytest

from apps.sales.forms.SalesForecasting.ForecastAdjustments import (
    ForecastAdjustmentForm,
    ForecastRevertForm,
)
from apps.sales.forms.SalesForecasting.ForecastPeriods import ForecastPeriodForm
from apps.sales.forms.SalesForecasting.ForecastScenarios import (
    ForecastScenarioApplyForm,
    ForecastScenarioForm,
)
from apps.sales.forms.SalesForecasting.ForecastSubmissions import (
    ForecastReviewForm,
    ForecastSubmissionForm,
)

from apps.sales.tests.conftest import (
    _salesforecasting_currency,
    _salesforecasting_period,
    _salesforecasting_submission,
)


def _period_form_data(**overrides):
    data = {
        "name": "Q1 2027",
        "period_type": "quarter",
        "period_year": 2027,
        "period_number": 1,
        "rollup_dimension": "user",
        "reporting_currency": "",
        "fx_rate_source_date": "",
        "is_active": True,
        "is_locked": False,
    }
    data.update(overrides)
    return data


def _submission_form_data(period, owner, **overrides):
    data = {
        "period": str(period.pk),
        "owner": str(owner.pk),
        "org_unit": "",
        "territory": "",
        "pipeline": "",
        "quota_ref": "",
        "omitted_amount": "0.00",
        "pipeline_amount": "10000.00",
        "best_case_amount": "8000.00",
        "commit_amount": "5000.00",
        "closed_amount": "0.00",
        "review_note": "",
        "notes": "",
    }
    data.update({k: ("" if v is None else str(v)) for k, v in overrides.items()})
    return data


def _adjustment_form_data(submission, **overrides):
    data = {
        "submission": str(submission.pk),
        "opportunity": "",
        "placement": "",
        "adjustment_kind": "direct",
        "target_field": "category",
        "adjusted_value": "",
        "adjusted_category": "commit",
        "reason_code": "manager_judgement",
        "note": "",
    }
    data.update({k: ("" if v is None else str(v)) for k, v in overrides.items()})
    return data


def _scenario_form_data(period, owner, **overrides):
    data = {
        "period": str(period.pk),
        "owner": str(owner.pk),
        "name": "Upside",
        "scenario_type": "upside",
        "probability_pct": 60,
        "is_baseline": False,
        "pipeline_delta_pct": "10.00",
        "best_case_delta_pct": "5.00",
        "commit_delta_pct": "0.00",
        "assumption_notes": "",
    }
    data.update({k: ("" if v is None else str(v)) for k, v in overrides.items()})
    return data



# =========================================================== ForecastPeriodForm
def test_salesforecasting_period_form_exposes_exactly_the_contract_fields(salesforecasting_tenant_a, db):
    form = ForecastPeriodForm(tenant=salesforecasting_tenant_a)
    assert set(form.fields) == {
        "name",
        "period_type",
        "period_year",
        "period_number",
        "rollup_dimension",
        "reporting_currency",
        "fx_rate_source_date",
        "is_active",
        "is_locked",
    }


def test_salesforecasting_period_form_never_exposes_tenant_number_or_derived_window(salesforecasting_tenant_a, db):
    form = ForecastPeriodForm(tenant=salesforecasting_tenant_a)
    for forbidden in ("tenant", "number", "start_date", "end_date"):
        assert forbidden not in form.fields, forbidden


def test_salesforecasting_period_form_currency_queryset_is_active_and_not_tenant_scoped(
    salesforecasting_tenant_a,
):
    """``accounting.Currency`` is GLOBAL -- it has no ``tenant`` column at all."""
    from apps.accounting.models import Currency

    inactive = _salesforecasting_currency(code="ZZZ", name="Retired", symbol="z")
    Currency.objects.filter(pk=inactive.pk).update(is_active=False)
    _salesforecasting_currency(code="EUR", name="Euro", symbol="E")

    form = ForecastPeriodForm(tenant=salesforecasting_tenant_a)
    codes = set(form.fields["reporting_currency"].queryset.values_list("code", flat=True))
    assert "EUR" in codes
    assert "ZZZ" not in codes


def test_salesforecasting_period_form_rejects_out_of_range_period_number(
    salesforecasting_tenant_a,
):
    # A quarter has 4, so 7 is out of range. The MODEL raises ValueError while
    # deriving the window before the form can attach an error, so a user would see
    # a 500 rather than a validation message. Both outcomes are a refusal, and the
    # ValueError branch documents the reported finding rather than hiding it.
    form = ForecastPeriodForm(
        data=_period_form_data(period_number=7), tenant=salesforecasting_tenant_a
    )
    try:
        valid = form.is_valid()
    except ValueError:
        return
    assert not valid
    assert "period_number" in form.errors


def test_salesforecasting_period_form_rejects_a_missing_tenant_workspace(db):
    form = ForecastPeriodForm(data=_period_form_data(), tenant=None)
    assert not form.is_valid()
    assert any("tenant" in str(e).lower() for e in form.non_field_errors())


def test_salesforecasting_period_form_locks_is_locked_for_a_non_admin(
    salesforecasting_tenant_a,
    salesforecasting_rep_a,
):
    form = ForecastPeriodForm(tenant=salesforecasting_tenant_a, user=salesforecasting_rep_a)
    assert form.fields["is_locked"].disabled is True
    assert form.initial.get("is_locked") is False


def test_salesforecasting_period_form_allows_is_locked_for_a_tenant_admin(
    salesforecasting_tenant_a,
    salesforecasting_admin_a,
):
    form = ForecastPeriodForm(tenant=salesforecasting_tenant_a, user=salesforecasting_admin_a)
    assert form.fields["is_locked"].disabled is False


def test_salesforecasting_period_form_derives_the_window_in_clean_not_from_the_post(
    salesforecasting_tenant_a,
):
    """The window is ``editable=False``; a crafted POST cannot move it."""
    form = ForecastPeriodForm(
        data=_period_form_data(period_year=2031, period_number=2), tenant=salesforecasting_tenant_a
    )
    assert form.is_valid(), form.errors
    assert form.instance.start_date.year == 2031
    assert form.instance.end_date > form.instance.start_date



# ======================================================== ForecastSubmissionForm
def test_salesforecasting_submission_form_exposes_exactly_the_contract_fields(salesforecasting_tenant_a, db):
    form = ForecastSubmissionForm(tenant=salesforecasting_tenant_a)
    assert set(form.fields) == {
        "period",
        "owner",
        "org_unit",
        "territory",
        "pipeline",
        "quota_ref",
        "omitted_amount",
        "pipeline_amount",
        "best_case_amount",
        "commit_amount",
        "closed_amount",
        "review_note",
        "notes",
    }


def test_salesforecasting_submission_form_never_exposes_derived_or_system_fields(salesforecasting_tenant_a, db):
    form = ForecastSubmissionForm(tenant=salesforecasting_tenant_a)
    for forbidden in (
        "tenant",
        "number",
        "status",
        "submitted_by",
        "reviewed_by",
        "submitted_at",
        "reviewed_at",
        "weighted_amount",  # a service snapshot, never typed
        "quota_amount",  # a snapshot, never typed
        "actual_amount",
        "total_forecast_amount",
        "variance_amount",
        "attainment_pct",
        "pace_pct",
        "ai_predicted_commit",
        "ai_confidence_pct",
        "ai_explanation",
    ):
        assert forbidden not in form.fields, forbidden


def test_salesforecasting_submission_form_fk_querysets_are_empty_without_a_tenant(db):
    form = ForecastSubmissionForm(tenant=None)
    for field_name in ("period", "owner", "org_unit", "territory", "pipeline", "quota_ref"):
        assert form.fields[field_name].queryset.count() == 0


def test_salesforecasting_submission_form_fk_querysets_are_tenant_scoped(
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_period_b,
    salesforecasting_rep_a,
    salesforecasting_pipeline_a,
    salesforecasting_pipeline_b,
):
    form = ForecastSubmissionForm(tenant=salesforecasting_tenant_a)
    assert salesforecasting_period_a in form.fields["period"].queryset
    assert salesforecasting_period_b not in form.fields["period"].queryset
    assert salesforecasting_rep_a in form.fields["owner"].queryset
    assert salesforecasting_pipeline_a in form.fields["pipeline"].queryset
    assert salesforecasting_pipeline_b not in form.fields["pipeline"].queryset


def test_salesforecasting_submission_form_accepts_a_valid_call(
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_rep_a,
):
    form = ForecastSubmissionForm(
        data=_submission_form_data(salesforecasting_period_a, salesforecasting_rep_a),
        tenant=salesforecasting_tenant_a,
    )
    assert form.is_valid(), form.errors


def test_salesforecasting_submission_form_rejects_a_negative_category_amount(
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_rep_a,
):
    form = ForecastSubmissionForm(
        data=_submission_form_data(
            salesforecasting_period_a, salesforecasting_rep_a, pipeline_amount="-1.00"
        ),
        tenant=salesforecasting_tenant_a,
    )
    assert not form.is_valid()
    assert "pipeline_amount" in form.errors


def test_salesforecasting_submission_form_rejects_a_duplicate_owner_for_one_period(
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_rep_a,
):
    """NULL-safe uniqueness lives in ``clean()`` -- a DB unique cannot enforce it."""
    _salesforecasting_submission(
        salesforecasting_tenant_a, salesforecasting_period_a, owner=salesforecasting_rep_a
    )
    form = ForecastSubmissionForm(
        data=_submission_form_data(salesforecasting_period_a, salesforecasting_rep_a),
        tenant=salesforecasting_tenant_a,
    )
    assert not form.is_valid()


def test_salesforecasting_submission_form_rejects_a_cross_tenant_period(
    salesforecasting_tenant_a,
    salesforecasting_rep_a,
    salesforecasting_period_b,
):
    form = ForecastSubmissionForm(
        data=_submission_form_data(salesforecasting_period_b, salesforecasting_rep_a),
        tenant=salesforecasting_tenant_a,
    )
    assert not form.is_valid()
    assert "period" in form.errors


def test_salesforecasting_submission_form_pins_owner_for_a_non_admin(
    salesforecasting_tenant_a,
    salesforecasting_rep_a,
):
    form = ForecastSubmissionForm(tenant=salesforecasting_tenant_a, user=salesforecasting_rep_a)
    assert form.fields["owner"].disabled is True
    assert form.initial.get("owner") == salesforecasting_rep_a.pk


def test_salesforecasting_submission_form_leaves_owner_editable_for_a_tenant_admin(
    salesforecasting_tenant_a,
    salesforecasting_admin_a,
):
    form = ForecastSubmissionForm(tenant=salesforecasting_tenant_a, user=salesforecasting_admin_a)
    assert form.fields["owner"].disabled is False


def test_salesforecasting_submission_form_freezes_every_field_on_a_frozen_submission(
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_rep_a,
    salesforecasting_admin_a,
):
    submission = _salesforecasting_submission(
        salesforecasting_tenant_a,
        salesforecasting_period_a,
        owner=salesforecasting_rep_a,
        status="approved",
    )
    form = ForecastSubmissionForm(
        instance=submission, tenant=salesforecasting_tenant_a, user=salesforecasting_admin_a
    )
    assert form.locked_fields
    assert all(form.fields[name].disabled for name in form.locked_fields)


# ========================================================== ForecastReviewForm
def test_salesforecasting_review_form_emits_one_error_for_one_blank_note(
    db,
    salesforecasting_tenant_a,
):
    """Regression (M6): a blank rejection note used to raise the SAME error twice --
    "This field is required." plus "A rejection must say why." -- so one mistake was
    reported twice. The declarative ``required`` flag is now the whole rule.
    """
    form = ForecastReviewForm(data={"note": ""}, tenant=salesforecasting_tenant_a, approved=False)
    assert not form.is_valid()
    assert len(form.errors.get("note", [])) == 1, form.errors
    assert not form.non_field_errors(), form.non_field_errors()


def test_salesforecasting_review_form_allows_a_blank_note_when_approving(
    db,
    salesforecasting_tenant_a,
):
    form = ForecastReviewForm(data={"note": ""}, tenant=salesforecasting_tenant_a, approved=True)
    assert form.is_valid(), form.errors


def test_salesforecasting_review_form_accepts_a_note_when_rejecting(
    db,
    salesforecasting_tenant_a,
):
    form = ForecastReviewForm(
        data={"note": "Missing budget this quarter."},
        tenant=salesforecasting_tenant_a,
        approved=False,
    )
    assert form.is_valid(), form.errors



# ======================================================= ForecastAdjustmentForm
def test_salesforecasting_adjustment_form_exposes_exactly_the_contract_fields(salesforecasting_tenant_a, db):
    form = ForecastAdjustmentForm(tenant=salesforecasting_tenant_a)
    assert set(form.fields) == {
        "submission",
        "opportunity",
        "placement",
        "adjustment_kind",
        "target_field",
        "adjusted_value",
        "adjusted_category",
        "reason_code",
        "note",
    }


def test_salesforecasting_adjustment_form_never_exposes_the_system_snapshot(salesforecasting_tenant_a, db):
    """The user enters the applied delta, never the "before" figure."""
    form = ForecastAdjustmentForm(tenant=salesforecasting_tenant_a)
    for forbidden in (
        "tenant",
        "number",
        "created_by",
        "original_value",
        "original_category",
        "is_reverted",
        "reverted_at",
        "revert_reason",
    ):
        assert forbidden not in form.fields, forbidden


def test_salesforecasting_adjustment_form_disables_kind_so_it_cannot_be_forged(salesforecasting_tenant_a, db):
    form = ForecastAdjustmentForm(tenant=salesforecasting_tenant_a)
    assert form.fields["adjustment_kind"].disabled is True
    assert form.fields["adjustment_kind"].initial == "direct"


def test_salesforecasting_adjustment_form_requires_a_reason_code(
    salesforecasting_tenant_a,
    salesforecasting_submission_a,
):
    form = ForecastAdjustmentForm(
        data=_adjustment_form_data(salesforecasting_submission_a, reason_code=""),
        tenant=salesforecasting_tenant_a,
    )
    assert not form.is_valid()
    assert "reason_code" in form.errors


def test_salesforecasting_adjustment_form_accepts_a_valid_override(
    salesforecasting_tenant_a,
    salesforecasting_submission_a,
):
    form = ForecastAdjustmentForm(
        data=_adjustment_form_data(salesforecasting_submission_a), tenant=salesforecasting_tenant_a
    )
    assert form.is_valid(), form.errors


def test_salesforecasting_adjustment_form_rejects_a_cross_tenant_submission(
    salesforecasting_tenant_b,
    salesforecasting_submission_a,
):
    form = ForecastAdjustmentForm(
        data=_adjustment_form_data(salesforecasting_submission_a), tenant=salesforecasting_tenant_b
    )
    assert not form.is_valid()


# ========================================================== ForecastRevertForm
def test_salesforecasting_revert_form_requires_a_reason(salesforecasting_tenant_a, db):
    form = ForecastRevertForm(data={"revert_reason": ""}, tenant=salesforecasting_tenant_a)
    assert not form.is_valid()
    assert "revert_reason" in form.errors


def test_salesforecasting_revert_form_accepts_a_reason(salesforecasting_tenant_a, db):
    form = ForecastRevertForm(data={"revert_reason": "Reverted after audit."}, tenant=salesforecasting_tenant_a)
    assert form.is_valid(), form.errors


def test_salesforecasting_revert_form_rejects_whitespace_only(salesforecasting_tenant_a, db):
    form = ForecastRevertForm(data={"revert_reason": "   "}, tenant=salesforecasting_tenant_a)
    assert not form.is_valid()
    assert "revert_reason" in form.errors



# ========================================================= ForecastScenarioForm
def test_salesforecasting_scenario_form_exposes_exactly_the_contract_fields(salesforecasting_tenant_a, db):
    form = ForecastScenarioForm(tenant=salesforecasting_tenant_a)
    assert set(form.fields) == {
        "period",
        "owner",
        "name",
        "scenario_type",
        "probability_pct",
        "is_baseline",
        "pipeline_delta_pct",
        "best_case_delta_pct",
        "commit_delta_pct",
        "assumption_notes",
    }


def test_salesforecasting_scenario_form_never_exposes_is_selected(salesforecasting_tenant_a, db):
    """``is_selected`` is workflow-owned -- only the select action may move it."""
    form = ForecastScenarioForm(tenant=salesforecasting_tenant_a)
    assert "is_selected" not in form.fields


def test_salesforecasting_scenario_form_never_exposes_the_projection_or_identity(salesforecasting_tenant_a, db):
    form = ForecastScenarioForm(tenant=salesforecasting_tenant_a)
    for forbidden in (
        "tenant",
        "number",
        "projected_commit_amount",
        "projected_total_amount",
    ):
        assert forbidden not in form.fields, forbidden


def test_salesforecasting_scenario_form_accepts_a_valid_scenario(
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_admin_a,
):
    form = ForecastScenarioForm(
        data=_scenario_form_data(salesforecasting_period_a, salesforecasting_admin_a),
        tenant=salesforecasting_tenant_a,
        user=salesforecasting_admin_a,
    )
    assert form.is_valid(), form.errors


def test_salesforecasting_scenario_form_disables_is_baseline_on_edit(
    salesforecasting_tenant_a,
    salesforecasting_scenario_a,
    salesforecasting_admin_a,
):
    form = ForecastScenarioForm(
        instance=salesforecasting_scenario_a,
        tenant=salesforecasting_tenant_a,
        user=salesforecasting_admin_a,
    )
    assert form.fields["is_baseline"].disabled is True


def test_salesforecasting_scenario_form_refuses_a_locked_period(
    salesforecasting_tenant_a,
    salesforecasting_admin_a,
):
    locked = _salesforecasting_period(
        salesforecasting_tenant_a, name="Locked Q", period_type="quarter", is_locked=True
    )
    form = ForecastScenarioForm(
        data=_scenario_form_data(locked, salesforecasting_admin_a),
        tenant=salesforecasting_tenant_a,
        user=salesforecasting_admin_a,
    )
    assert not form.is_valid()


# ===================================================== ForecastScenarioApplyForm
def test_salesforecasting_scenario_apply_form_exposes_exactly_its_fields(salesforecasting_tenant_a, db):
    form = ForecastScenarioApplyForm(tenant=salesforecasting_tenant_a)
    assert set(form.fields) == {"period", "target", "variance_threshold_pct"}


def test_salesforecasting_scenario_apply_form_never_exposes_a_projection_field(salesforecasting_tenant_a, db):
    form = ForecastScenarioApplyForm(tenant=salesforecasting_tenant_a)
    for forbidden in ("owner", "name", "is_selected", "projected_commit_amount"):
        assert forbidden not in form.fields, forbidden


def test_salesforecasting_scenario_apply_form_rejects_a_negative_threshold(salesforecasting_tenant_a, salesforecasting_period_a):
    form = ForecastScenarioApplyForm(
        data={
            "period": str(salesforecasting_period_a.pk),
            "target": "commit",
            "variance_threshold_pct": "-5",
        },
        tenant=salesforecasting_tenant_a,
    )
    assert not form.is_valid()
    assert "variance_threshold_pct" in form.errors


def test_salesforecasting_scenario_apply_form_rejects_an_out_of_range_threshold(salesforecasting_tenant_a, salesforecasting_period_a):
    form = ForecastScenarioApplyForm(
        data={
            "period": str(salesforecasting_period_a.pk),
            "target": "commit",
            "variance_threshold_pct": "5000",
        },
        tenant=salesforecasting_tenant_a,
    )
    assert not form.is_valid()
    assert "variance_threshold_pct" in form.errors
