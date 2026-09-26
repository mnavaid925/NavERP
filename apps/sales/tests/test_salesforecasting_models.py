"""8.4 Sales Forecasting -- model lane.

Every ruling the four entities are built on is asserted here as executable law, not
commentary: the auto-number prefixes, the ``editable=False`` computed window, the
derived-vs-stored line (a property is never a column), the ``None``-not-``Infinity``
percentage guard, the ``clean()`` refusals, the Python-side owner/period uniqueness, the
single-selected scenario constraint, the PROTECT delete guards and tenant isolation.

Names: every test is ``test_salesforecasting_*`` and every module-level helper is
``_salesforecasting_*`` so sub-modules 8.1 / 8.2 / 8.3 in this package cannot be shadowed.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.core.models import Tenant
from apps.crm.models import SalesQuota
from apps.sales.forms.SalesForecasting.ForecastScenarios import ForecastScenarioForm
from apps.sales.models import (
    ForecastAdjustment,
    ForecastPeriod,
    ForecastScenario,
    ForecastSubmission,
)
from apps.sales.models.SalesForecasting.ForecastSubmissions import AMOUNT_FIELDS
from apps.sales.tests.conftest import (
    SALESFORECASTING_CHOICES,
    SALESFORECASTING_MODEL_FIELDS,
    _salesforecasting_adjustment,
    _salesforecasting_period,
    _salesforecasting_scenario,
    _salesforecasting_submission,
)

pytestmark = pytest.mark.django_db

ALL_MODELS = (ForecastPeriod, ForecastSubmission, ForecastAdjustment, ForecastScenario)


# ============================================================================
# Module helpers (_salesforecasting_*)
# ============================================================================

def _salesforecasting_concrete_fields(model):
    """The model's own columns, in declaration order (no reverse accessors, no pk)."""
    return tuple(
        field.name
        for field in model._meta.get_fields()
        if field.concrete and not field.primary_key
    )


def _salesforecasting_constraint(model, name):
    for constraint in model._meta.constraints:
        if constraint.name == name:
            return constraint
    raise AssertionError(f"{model.__name__} has no constraint named {name}")


def _salesforecasting_field(model, name):
    return model._meta.get_field(name)


def _salesforecasting_stamp_window(period, start, end):
    """Pin the computed window on an in-memory row so the elapsed maths is deterministic.

    ``start_date`` / ``end_date`` are ``editable=False`` (never a form field) but they are
    ordinary Python attributes, so a property test may set them without going near the DB.
    """
    period.start_date = start
    period.end_date = end
    return period


# ============================================================================
# 1. The contract itself: field sets, choices, constraints, indexes
# ============================================================================

def test_salesforecasting_model_field_sets_match_the_contract():
    for model in ALL_MODELS:
        assert _salesforecasting_concrete_fields(model) == SALESFORECASTING_MODEL_FIELDS[model.__name__]


def test_salesforecasting_choices_are_the_pinned_vocabularies():
    # 8.4 reuses crm.SalesQuota.PERIOD_CHOICES verbatim -- never a re-spelled vocabulary.
    assert list(_salesforecasting_field(ForecastPeriod, "period_type").choices) == list(SalesQuota.PERIOD_CHOICES)
    for model, field_name in (
        (ForecastPeriod, "rollup_dimension"),
        (ForecastSubmission, "status"),
        (ForecastAdjustment, "adjustment_kind"),
        (ForecastAdjustment, "target_field"),
        (ForecastAdjustment, "reason_code"),
        (ForecastScenario, "scenario_type"),
    ):
        expected = SALESFORECASTING_CHOICES[model.__name__][field_name]
        assert list(_salesforecasting_field(model, field_name).choices) == list(expected), field_name


def test_salesforecasting_constraint_and_index_names_are_pinned():
    expected = {
        ForecastPeriod: (
            ["sales_fcp_tenant_number_uniq", "sales_fcp_tpt_ypn_uniq", "sales_fcp_period_number_valid"],
            ["sales_fcp_tenant_active_idx", "sales_fcp_tnt_type_year_idx"],
        ),
        ForecastSubmission: (
            ["sales_fcs_tenant_number_uniq", "sales_fcs_amounts_nonneg"],
            ["sales_fcs_tnt_p_status_idx", "sales_fcs_tnt_owner_idx", "sales_fcs_tnt_p_org_idx"],
        ),
        ForecastAdjustment: (
            ["sales_fad_tenant_number_uniq", "sales_fad_reverted_stamped"],
            ["sales_fad_tnt_submission_idx", "sales_fad_tnt_reason_idx", "sales_fad_tnt_kind_idx", "sales_fad_tnt_opp_idx"],
        ),
        ForecastScenario: (
            [
                "sales_fsc_tenant_number_uniq",
                "sales_fsc_tnt_period_name_uniq",
                "sales_fsc_probability_valid",
                "sales_fsc_baseline_selected",
            ],
            ["sales_fsc_tnt_period_idx", "sales_fsc_tnt_selected_idx"],
        ),
    }
    for model, (constraint_names, index_names) in expected.items():
        assert [c.name for c in model._meta.constraints] == constraint_names
        assert [i.name for i in model._meta.indexes] == index_names


def test_salesforecasting_auto_numbers_are_minted_per_tenant(salesforecasting_tenant_a, salesforecasting_tenant_b):
    period_a = _salesforecasting_period(salesforecasting_tenant_a, name="A Q1", period_year=2031, period_number=1)
    period_b = _salesforecasting_period(salesforecasting_tenant_b, name="B Q1", period_year=2031, period_number=1)
    submission = _salesforecasting_submission(salesforecasting_tenant_a, period_a)
    adjustment = _salesforecasting_adjustment(salesforecasting_tenant_a, submission)
    scenario = _salesforecasting_scenario(salesforecasting_tenant_a, period_a, name="A Upside")

    for obj, prefix in (
        (period_a, "FCP-"),
        (period_b, "FCP-"),
        (submission, "FCS-"),
        (adjustment, "FAD-"),
        (scenario, "FSC-"),
    ):
        assert obj.number.startswith(prefix), obj.number
        assert len(obj.number) == len(prefix) + 5
        assert obj.number[len(prefix):].isdigit()

    # Per-tenant sequence: the other workspace mints its own FCP-00001, and the same
    # workspace's second period is a different number.
    assert period_a.number == "FCP-00001"
    assert period_b.number == "FCP-00001"
    second = _salesforecasting_period(salesforecasting_tenant_a, name="A Q2", period_year=2031, period_number=2)
    assert second.number == "FCP-00002"
    assert second.number != period_a.number


def test_salesforecasting_every_model_carries_a_tenant_fk(salesforecasting_tenant_a, salesforecasting_submission_a):
    for model in ALL_MODELS:
        field = _salesforecasting_field(model, "tenant")
        assert field.remote_field.model is Tenant
        assert field.remote_field.related_name == "+"
        assert field.null is False
        assert field.db_index is True

    # A tenant that still carries 8.4 data cannot be dropped: the submission -> period
    # PROTECT chain is honoured by the cascade collector, so history is never swept away
    # by a tenant delete.
    assert ForecastPeriod.objects.filter(tenant=salesforecasting_tenant_a).exists()
    assert ForecastSubmission.objects.filter(tenant=salesforecasting_tenant_a).exists()
    tenant_pk = salesforecasting_tenant_a.pk
    with pytest.raises(ProtectedError):
        with transaction.atomic():
            salesforecasting_tenant_a.delete()
    assert ForecastPeriod.objects.filter(tenant_id=tenant_pk).exists()

    # Once the live forecast is gone the tenant's whole 8.4 footprint goes with it.
    submission_pk = salesforecasting_submission_a.pk
    salesforecasting_submission_a.delete()
    assert not ForecastSubmission.objects.filter(pk=submission_pk).exists()
    salesforecasting_tenant_a.delete()
    assert ForecastPeriod.objects.filter(tenant_id=tenant_pk).count() == 0
    assert ForecastSubmission.objects.filter(tenant_id=tenant_pk).count() == 0



# ============================================================================
# 2. ForecastPeriod -- the computed window, the elapsed clock, the range guard
# ============================================================================

def test_salesforecasting_period_window_is_derived_for_every_period_type(salesforecasting_tenant_a):
    # month 1-12, quarter 1-4, year exactly 1 -- and the window is NEVER typed in.
    assert _salesforecasting_field(ForecastPeriod, "start_date").editable is False
    assert _salesforecasting_field(ForecastPeriod, "end_date").editable is False

    february = _salesforecasting_period(
        salesforecasting_tenant_a, name="Feb", period_type="month", period_year=2025, period_number=2,
    )
    assert (february.start_date, february.end_date) == (date(2025, 2, 1), date(2025, 2, 28))

    q3 = _salesforecasting_period(
        salesforecasting_tenant_a, name="Q3", period_type="quarter", period_year=2025, period_number=3,
    )
    assert (q3.start_date, q3.end_date) == (date(2025, 7, 1), date(2025, 9, 30))

    year = _salesforecasting_period(
        salesforecasting_tenant_a, name="FY", period_type="year", period_year=2024, period_number=1,
    )
    assert (year.start_date, year.end_date) == (date(2024, 1, 1), date(2024, 12, 31))

    # A leap February still ends on the last real day of the month.
    leap = _salesforecasting_period(
        salesforecasting_tenant_a, name="Feb 2028", period_type="month", period_year=2028, period_number=2,
    )
    assert leap.end_date == date(2028, 2, 29)
    for period in (february, q3, year, leap):
        assert period.end_date >= period.start_date


def test_salesforecasting_period_window_is_re_derived_when_the_period_is_edited(salesforecasting_tenant_a):
    """Regression for review C1: a row must never contradict its own type/year/number.

    ``clean()`` recomputes the window onto the instance, so an edit that moves the period
    forward persists the NEW window -- the stale ``start_date`` / ``end_date`` pair is
    never carried along.
    """
    period = _salesforecasting_period(
        salesforecasting_tenant_a, name="Movable", period_type="quarter", period_year=2025, period_number=1,
    )
    assert (period.start_date, period.end_date) == (date(2025, 1, 1), date(2025, 3, 31))

    period.period_number = 3
    period.full_clean()
    assert (period.start_date, period.end_date) == (date(2025, 7, 1), date(2025, 9, 30))
    period.save()

    period.refresh_from_db()
    assert (period.period_type, period.period_year, period.period_number) == ("quarter", 2025, 3)
    assert (period.start_date, period.end_date) == (date(2025, 7, 1), date(2025, 9, 30))
    assert period.label == "Quarterly 2025 · P3"
    # Q3 2025 is behind us, so the moved-to window reads as fully elapsed -- which is
    # exactly the figure the stale window used to get wrong.
    assert period.period_elapsed_pct == Decimal("100")



def test_salesforecasting_period_elapsed_pct_guards_zero_and_elapsed(salesforecasting_tenant_a, salesforecasting_past_period_a):
    today = timezone.localdate()

    # No window at all -> 0, never a ZeroDivisionError and never a division by a 0-day span.
    unsaved = ForecastPeriod(tenant=salesforecasting_tenant_a, name="Unset")
    assert unsaved.start_date is None and unsaved.end_date is None
    assert unsaved.period_elapsed_pct == Decimal("0")

    # A window that has closed reads 100, a window that has not opened reads 0.
    assert salesforecasting_past_period_a.end_date < today
    assert salesforecasting_past_period_a.period_elapsed_pct == Decimal("100")

    future = _salesforecasting_stamp_window(
        ForecastPeriod(tenant=salesforecasting_tenant_a, name="Future"),
        today + timedelta(days=10),
        today + timedelta(days=40),
    )
    assert future.period_elapsed_pct == Decimal("0")

    # Mid-window: inclusive day counts, so 10 of 20 days is exactly 50.00.
    mid = _salesforecasting_stamp_window(
        ForecastPeriod(tenant=salesforecasting_tenant_a, name="Mid"),
        today - timedelta(days=9),
        today + timedelta(days=10),
    )
    assert mid.period_elapsed_pct == Decimal("50.00")

    # The closing day itself is elapsed, not still in progress.
    closing = _salesforecasting_stamp_window(
        ForecastPeriod(tenant=salesforecasting_tenant_a, name="Closing"),
        today - timedelta(days=5),
        today,
    )
    assert closing.period_elapsed_pct == Decimal("100")

    # A degenerate window (end before start) is floored at 0 rather than going negative.
    inverted = _salesforecasting_stamp_window(
        ForecastPeriod(tenant=salesforecasting_tenant_a, name="Inverted"),
        today,
        today - timedelta(days=3),
    )
    assert inverted.period_elapsed_pct == Decimal("0")


def test_salesforecasting_period_label_and_is_current(salesforecasting_tenant_a):
    year = _salesforecasting_period(
        salesforecasting_tenant_a, name="FY", period_type="year", period_year=2024, period_number=1,
    )
    # A year carries no "P<n>" suffix; a quarter does.
    assert year.label == "Annual 2024"
    assert year.is_current is False

    today = timezone.localdate()
    current = _salesforecasting_period(
        salesforecasting_tenant_a,
        name="Now",
        period_type="month",
        period_year=today.year,
        period_number=today.month,
    )
    assert current.label == f"Monthly {today.year} · P{today.month}"
    assert current.is_current is True
    assert str(current) == f"{current.number} · {current.label}"



def test_salesforecasting_period_rejects_an_out_of_range_period_number(salesforecasting_tenant_a):
    for period_type, bad_number in (("month", 13), ("quarter", 5), ("year", 2)):
        period = ForecastPeriod(
            tenant=salesforecasting_tenant_a,
            name=f"Bad {period_type}",
            period_type=period_type,
            period_year=2025,
            period_number=bad_number,
        )
        with pytest.raises(ValidationError) as excinfo:
            period.clean()
        assert "period_number" in excinfo.value.message_dict

    # The in-range boundaries are accepted for every type.
    for period_type, good_numbers in (("month", (1, 12)), ("quarter", (1, 4)), ("year", (1,))):
        for good in good_numbers:
            period = ForecastPeriod(
                tenant=salesforecasting_tenant_a,
                name=f"Good {period_type} {good}",
                period_type=period_type,
                period_year=2025,
                period_number=good,
            )
            period.clean()  # must not raise
            assert period.start_date is not None and period.end_date is not None

    # The database refuses a period number outside the hard 1-12 band as well.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ForecastPeriod.objects.create(
                tenant=salesforecasting_tenant_a,
                name="Zero",
                period_type="quarter",
                period_year=2025,
                period_number=0,
            )


def test_salesforecasting_period_delete_is_guarded_while_a_forecast_exists(salesforecasting_tenant_a, salesforecasting_submission_a):
    period = salesforecasting_submission_a.period

    # A period that still carries a forecast call cannot be deleted out from under it.
    with pytest.raises(ValidationError) as excinfo:
        period.delete()
    assert "submission" in str(excinfo.value)
    assert ForecastPeriod.objects.filter(pk=period.pk, tenant=salesforecasting_tenant_a).exists()

    # A period that only carries a scenario is guarded by the same rule.
    with_scenario = _salesforecasting_period(
        salesforecasting_tenant_a, name="Scenario only", period_type="quarter", period_year=2023, period_number=1,
    )
    _salesforecasting_scenario(salesforecasting_tenant_a, with_scenario, name="Only What-If")
    with pytest.raises(ValidationError) as excinfo:
        with_scenario.delete()
    assert "scenario" in str(excinfo.value)

    # An empty period deletes cleanly.
    empty = _salesforecasting_period(
        salesforecasting_tenant_a, name="Empty", period_type="quarter", period_year=2022, period_number=1,
    )
    empty_pk = empty.pk
    empty.delete()
    assert not ForecastPeriod.objects.filter(pk=empty_pk, tenant=salesforecasting_tenant_a).exists()



# ============================================================================
# 3. ForecastSubmission -- derived amounts, the None-not-Infinity guard, clean()
# ============================================================================

def test_salesforecasting_submission_forecast_figures_are_derived_not_stored(salesforecasting_submission_a):
    """The derived-vs-stored ruling: a property is never a column.

    ``total_forecast_amount`` reads like a field; the contract forbids making it one,
    because a stored total silently drifts the moment an amount is edited.
    """
    model_fields = _salesforecasting_concrete_fields(ForecastSubmission)
    for derived in ("total_forecast_amount", "variance_amount", "attainment_pct", "pace_pct"):
        assert derived not in model_fields
        assert isinstance(getattr(ForecastSubmission, derived), property)

    # The stored snapshots ARE columns -- they are service-written, not derived.
    for snapshot in ("weighted_amount", "quota_amount", "actual_amount"):
        assert snapshot in model_fields
    assert AMOUNT_FIELDS == (
        "omitted_amount", "pipeline_amount", "best_case_amount", "commit_amount",
        "closed_amount", "weighted_amount", "quota_amount", "actual_amount",
    )


def test_salesforecasting_submission_total_variance_attainment_and_pace(salesforecasting_submission_a):
    submission = salesforecasting_submission_a

    # commit + best case + pipeline -- the closed and omitted buckets are not in the total.
    assert submission.total_forecast_amount == Decimal("23000.00")
    assert submission.variance_amount == Decimal("14000.00")
    assert submission.attainment_pct == Decimal("45.00")
    assert submission.pace_pct == submission.period.period_elapsed_pct
    assert submission.pace_pct == salesforecasting_submission_a.period.period_elapsed_pct
    assert str(submission).startswith(submission.number)

    # A negative variance is the over-promise case and must read as a negative number.
    submission.actual_amount = Decimal("30000.00")
    assert submission.variance_amount == Decimal("-7000.00")
    assert submission.attainment_pct == Decimal("150.00")

    # No period row at all -> no pace, rather than a crash on a missing FK.
    assert ForecastSubmission(tenant=submission.tenant).pace_pct is None


def test_salesforecasting_submission_attainment_pct_is_none_on_a_zero_quota(salesforecasting_submission_a):
    """R6: a zero quota renders an em dash. It must never be Infinity or NaN."""
    submission = salesforecasting_submission_a

    submission.quota_amount = Decimal("0.00")
    assert submission.attainment_pct is None

    submission.quota_amount = Decimal("0.01")
    assert submission.attainment_pct == Decimal("90000000.00")  # a huge number, still finite

    submission.quota_amount = Decimal("0.00")
    submission.actual_amount = Decimal("0.00")
    assert submission.attainment_pct is None
    assert submission.attainment_pct is not False

    # An unset (NULL-ish) quota behaves exactly like zero rather than raising.
    submission.quota_amount = None
    assert submission.attainment_pct is None
    assert submission.variance_amount == submission.total_forecast_amount



def test_salesforecasting_submission_rejects_negative_amounts(salesforecasting_tenant_a, salesforecasting_period_a):
    for field_name in ("omitted_amount", "pipeline_amount", "best_case_amount", "commit_amount", "closed_amount"):
        submission = ForecastSubmission(
            tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, **{field_name: Decimal("-1.00")},
        )
        with pytest.raises(ValidationError) as excinfo:
            submission.clean()
        assert field_name in excinfo.value.message_dict
        assert "negative" in excinfo.value.message_dict[field_name][0]

    # The service-written snapshots are non-negative too -- a negative quota is a bad write.
    for field_name in ("weighted_amount", "quota_amount", "actual_amount"):
        submission = ForecastSubmission(
            tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, **{field_name: Decimal("-0.01")},
        )
        with pytest.raises(ValidationError) as excinfo:
            submission.clean()
        assert field_name in excinfo.value.message_dict

    # And the database backstops the eight amount columns.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ForecastSubmission.objects.create(
                tenant=salesforecasting_tenant_a,
                period=salesforecasting_period_a,
                commit_amount=Decimal("-5.00"),
            )


def test_salesforecasting_submission_rejects_a_cross_tenant_relation(
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_period_b,
    salesforecasting_admin_b,
    salesforecasting_org_unit_b,
    salesforecasting_pipeline_b,
):
    cases = {
        "period": salesforecasting_period_b,
        "owner": salesforecasting_admin_b,
        "org_unit": salesforecasting_org_unit_b,
        "pipeline": salesforecasting_pipeline_b,
    }
    for field_name, foreign in cases.items():
        kwargs = {"tenant": salesforecasting_tenant_a, "period": salesforecasting_period_a}
        kwargs[field_name] = foreign
        submission = ForecastSubmission(**kwargs)
        with pytest.raises(ValidationError) as excinfo:
            submission.clean()
        assert field_name in excinfo.value.message_dict
        assert "workspace" in excinfo.value.message_dict[field_name][0]

    # The same-tenant relation is accepted, so the guard is a tenant check and not a
    # blanket refusal.
    ok = ForecastSubmission(tenant=salesforecasting_tenant_a, period=salesforecasting_period_a)
    ok.clean()  # must not raise



def test_salesforecasting_owner_period_uniqueness_is_enforced_in_python_only(
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_rep_a,
    salesforecasting_submission_a,
):
    """Contract 13.2: a DB unique on (tenant, period, owner) is FORBIDDEN, not merely unsafe.

    ``owner`` is nullable and NULLs never collide in a SQL unique index, so the constraint
    would be theatre. The rule therefore lives in ``clean()`` -- and the tests below prove
    both halves: the database really does accept the duplicate, and ``clean()`` refuses it.
    """
    constraint_fields = {
        tuple(constraint.fields)
        for constraint in ForecastSubmission._meta.constraints
        if hasattr(constraint, "fields")
    }
    assert ("tenant", "period", "owner") not in constraint_fields
    index_fields = {tuple(index.fields) for index in ForecastSubmission._meta.indexes}
    assert ("tenant", "period", "owner") not in index_fields
    assert ("tenant", "owner") in index_fields  # a lookup aid only, never unique

    # The DB permits it -- which is exactly why Python has to.
    duplicate = _salesforecasting_submission(
        salesforecasting_tenant_a, salesforecasting_period_a, owner=salesforecasting_rep_a,
    )
    assert duplicate.pk != salesforecasting_submission_a.pk
    assert ForecastSubmission.objects.filter(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, owner=salesforecasting_rep_a,
    ).count() == 2

    # clean() is the guard that actually holds.
    third = ForecastSubmission(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, owner=salesforecasting_rep_a,
    )
    with pytest.raises(ValidationError) as excinfo:
        third.clean()
    assert "owner" in excinfo.value.message_dict

    # A NULL owner (a team call) is one per period too -- the case a SQL unique cannot see.
    team_call = _salesforecasting_submission(salesforecasting_tenant_a, salesforecasting_period_a, owner=None)
    assert team_call.owner_id is None
    second_team_call = ForecastSubmission(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, owner=None,
    )
    with pytest.raises(ValidationError) as excinfo:
        second_team_call.clean()
    assert "owner" in excinfo.value.message_dict

    # A different owner in the same period is fine, and the same owner in a different
    # period is fine.
    other_owner = ForecastSubmission(
        tenant=salesforecasting_tenant_a,
        period=_salesforecasting_period(
            salesforecasting_tenant_a, name="An earlier quarter", period_type="quarter",
            period_year=salesforecasting_period_a.period_year - 1, period_number=2,
        ),
        owner=salesforecasting_rep_a,
    )
    other_owner.clean()  # must not raise
    assert other_owner._duplicate_owner_rows().count() == 0


def test_salesforecasting_submission_review_requires_a_reviewer_and_a_timestamp(
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_admin_a,
):
    pending = ForecastSubmission(tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, status="approved")
    with pytest.raises(ValidationError) as excinfo:
        pending.clean()
    assert "status" in excinfo.value.message_dict

    reviewed = ForecastSubmission(tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, status="approved")
    reviewed.mark_reviewed(salesforecasting_admin_a, approved=True, note="on plan")
    reviewed.clean()  # must not raise
    assert reviewed.status == "approved"
    assert reviewed.reviewed_by_id == salesforecasting_admin_a.pk
    assert reviewed.reviewed_at is not None
    assert reviewed.is_frozen is True
    assert reviewed.allowed_actions == []

    # Reverting a rejected call releases the freeze and hands it back to the rep.
    rejected = ForecastSubmission(tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, status="rejected")
    rejected.mark_reviewed(salesforecasting_admin_a, approved=False, note="too low")
    rejected.mark_reverted()
    assert rejected.status == "draft"
    assert rejected.submitted_at is None and rejected.reviewed_by_id is None
    assert rejected.is_frozen is False
    assert rejected.allowed_actions == ["edit", "submit", "delete"]


def test_salesforecasting_locked_period_freezes_its_forecast_calls(salesforecasting_tenant_a):
    locked_period = _salesforecasting_period(
        salesforecasting_tenant_a, name="Locked", period_type="quarter", period_year=2019,
        period_number=1, is_locked=True,
    )
    frozen = ForecastSubmission(tenant=salesforecasting_tenant_a, period=locked_period, status="draft")
    with pytest.raises(ValidationError) as excinfo:
        frozen.clean()
    assert "status" in excinfo.value.message_dict
    assert "locked" in excinfo.value.message_dict["status"][0]

    allowed = ForecastSubmission(tenant=salesforecasting_tenant_a, period=locked_period, status="locked")
    allowed.clean()  # must not raise
    assert allowed.is_frozen is True
    assert allowed.allowed_actions == []



# ============================================================================
# 4. ForecastAdjustment -- the mandatory reason, net_delta, the one-shot Reset
# ============================================================================

def test_salesforecasting_adjustment_net_delta_is_a_property_and_never_stored(salesforecasting_tenant_a, salesforecasting_submission_a):
    fields = _salesforecasting_concrete_fields(ForecastAdjustment)
    assert "net_delta" not in fields
    assert isinstance(getattr(ForecastAdjustment, "net_delta"), property)
    # The post-override figure is never cached -- that absence is what makes Reset possible.
    assert "adjusted_total" not in fields
    assert "calculated_value" not in fields
    for snapshot in ("original_value", "original_category"):
        assert snapshot in fields

    amount_row = _salesforecasting_adjustment(
        salesforecasting_tenant_a,
        salesforecasting_submission_a,
        target_field="amount",
        adjusted_category=None,
        adjusted_value=Decimal("7500.00"),
        original_value=Decimal("5000.00"),
    )
    assert amount_row.net_delta == Decimal("2500.00")

    # A category row has no money to difference, so the delta is None, not a fake zero.
    category_row = _salesforecasting_adjustment(
        salesforecasting_tenant_a, salesforecasting_submission_a, adjusted_category="commit",
    )
    assert category_row.net_delta is None
    assert category_row.is_resettable is True


def test_salesforecasting_adjustment_reason_code_is_mandatory(salesforecasting_tenant_a, salesforecasting_submission_a):
    # The field itself carries no default -- an override with no reason is the
    # sandbagging signal bullet 4 hunts.
    reason_field = _salesforecasting_field(ForecastAdjustment, "reason_code")
    assert reason_field.has_default() is False
    assert reason_field.null is False
    assert reason_field.blank is False

    blank = ForecastAdjustment(
        tenant=salesforecasting_tenant_a, submission=salesforecasting_submission_a,
        target_field="category", adjusted_category="commit", reason_code="",
    )
    with pytest.raises(ValidationError) as excinfo:
        blank.clean()
    assert "reason_code" in excinfo.value.message_dict

    invented = ForecastAdjustment(
        tenant=salesforecasting_tenant_a, submission=salesforecasting_submission_a,
        target_field="category", adjusted_category="commit", reason_code="because_i_said_so",
    )
    with pytest.raises(ValidationError) as excinfo:
        invented.clean()
    assert "reason_code" in excinfo.value.message_dict

    valid = ForecastAdjustment(
        tenant=salesforecasting_tenant_a, submission=salesforecasting_submission_a,
        target_field="category", adjusted_category="commit", reason_code="deal_won",
    )
    valid.clean()  # must not raise


def test_salesforecasting_adjustment_target_field_decides_which_pair_is_live(salesforecasting_tenant_a, salesforecasting_submission_a):
    # A category override carries the category pair and no money.
    category_without_category = ForecastAdjustment(
        tenant=salesforecasting_tenant_a, submission=salesforecasting_submission_a,
        target_field="category", adjusted_category=None, reason_code="deal_slipped",
    )
    with pytest.raises(ValidationError) as excinfo:
        category_without_category.clean()
    assert "adjusted_category" in excinfo.value.message_dict

    category_with_money = ForecastAdjustment(
        tenant=salesforecasting_tenant_a, submission=salesforecasting_submission_a,
        target_field="category", adjusted_category="commit", adjusted_value=Decimal("1.00"),
        reason_code="deal_slipped",
    )
    with pytest.raises(ValidationError) as excinfo:
        category_with_money.clean()
    assert "adjusted_value" in excinfo.value.message_dict

    # An amount override is the mirror image.
    amount_without_value = ForecastAdjustment(
        tenant=salesforecasting_tenant_a, submission=salesforecasting_submission_a,
        target_field="amount", adjusted_category=None, adjusted_value=None, reason_code="amount_revised",
    )
    with pytest.raises(ValidationError) as excinfo:
        amount_without_value.clean()
    assert "adjusted_value" in excinfo.value.message_dict

    amount_with_category = ForecastAdjustment(
        tenant=salesforecasting_tenant_a, submission=salesforecasting_submission_a,
        target_field="amount", adjusted_category="commit", adjusted_value=Decimal("1.00"),
        reason_code="amount_revised",
    )
    with pytest.raises(ValidationError) as excinfo:
        amount_with_category.clean()
    assert "adjusted_category" in excinfo.value.message_dict



def test_salesforecasting_reverted_adjustment_is_not_resettable(salesforecasting_tenant_a, salesforecasting_admin_a, salesforecasting_adjustment_a):
    adjustment = salesforecasting_adjustment_a
    assert adjustment.is_reverted is False
    assert adjustment.is_resettable is True
    assert _salesforecasting_field(ForecastAdjustment, "reverted_at").editable is False

    # A Reset must say why, and the row keeps both halves of the claim.
    with pytest.raises(ValidationError) as excinfo:
        adjustment.mark_reverted(salesforecasting_admin_a, "   ")
    assert "revert_reason" in excinfo.value.message_dict
    assert adjustment.is_reverted is False  # nothing half-written

    adjustment.mark_reverted(salesforecasting_admin_a, "Deal was never real")
    assert adjustment.is_reverted is True
    assert adjustment.is_resettable is False
    assert adjustment.reverted_at is not None
    assert adjustment.revert_reason == "Deal was never real"
    assert adjustment.created_by_id == salesforecasting_admin_a.pk
    adjustment.save()
    adjustment.refresh_from_db()
    assert adjustment.is_resettable is False
    adjustment.clean()  # a properly stamped revert validates

    # An unstamped revert is refused by clean() and by the CheckConstraint behind it.
    unstamped = ForecastAdjustment(
        tenant=salesforecasting_tenant_a, submission=adjustment.submission,
        target_field="category", adjusted_category="commit", reason_code="correction",
        is_reverted=True,
    )
    with pytest.raises(ValidationError) as excinfo:
        unstamped.clean()
    assert "revert_reason" in excinfo.value.message_dict

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ForecastAdjustment.objects.create(
                tenant=salesforecasting_tenant_a,
                submission=adjustment.submission,
                target_field="category",
                adjusted_category="commit",
                reason_code="correction",
                is_reverted=True,
                reverted_at=None,
            )


def test_salesforecasting_adjustment_audit_row_is_never_cascaded_away(salesforecasting_tenant_a, salesforecasting_adjustment_a):
    submission = salesforecasting_adjustment_a.submission
    assert list(submission.adjustment_rows()) == [salesforecasting_adjustment_a]

    with pytest.raises(ProtectedError):
        with transaction.atomic():
            submission.delete()
    assert ForecastSubmission.objects.filter(
        pk=submission.pk, tenant=salesforecasting_tenant_a,
    ).exists()
    assert ForecastAdjustment.objects.filter(
        pk=salesforecasting_adjustment_a.pk, tenant=salesforecasting_tenant_a,
    ).exists()


def test_salesforecasting_adjustment_rejects_a_cross_tenant_submission(salesforecasting_tenant_a, salesforecasting_tenant_b, salesforecasting_period_b):
    other_submission = _salesforecasting_submission(salesforecasting_tenant_b, salesforecasting_period_b)
    adjustment = ForecastAdjustment(
        tenant=salesforecasting_tenant_a,
        submission=other_submission,
        target_field="category",
        adjusted_category="commit",
        reason_code="manager_judgement",
    )
    with pytest.raises(ValidationError) as excinfo:
        adjustment.clean()
    assert "submission" in excinfo.value.message_dict
    assert "workspace" in excinfo.value.message_dict["submission"][0]



# ============================================================================
# 5. ForecastScenario -- single-selected, deltas-only, and the isolation rule
# ============================================================================

def test_salesforecasting_scenario_only_the_baseline_may_be_selected(salesforecasting_tenant_a, salesforecasting_period_a):
    constraint = _salesforecasting_constraint(ForecastScenario, "sales_fsc_baseline_selected")
    assert constraint is not None

    # clean() surfaces the rule as a field error rather than letting the DB explode later.
    contradictory = ForecastScenario(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
        name="Claimed baseline", is_baseline=True, is_selected=False,
    )
    with pytest.raises(ValidationError) as excinfo:
        contradictory.clean()
    assert "is_baseline" in excinfo.value.message_dict

    # And the database refuses it too, so a crafted QuerySet.update() cannot do it either.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ForecastScenario.objects.create(
                tenant=salesforecasting_tenant_a,
                period=salesforecasting_period_a,
                name="Sneaky baseline",
                is_baseline=True,
                is_selected=False,
            )

    # The rule's other half lives in code: a baseline always syncs itself to selected.
    baseline = ForecastScenario(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
        name="The plan", is_baseline=True,
    )
    baseline.sync_selected_from_baseline()
    assert baseline.is_selected is True
    baseline.clean()  # must not raise
    baseline.save()
    assert ForecastScenario.objects.filter(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a, is_selected=True,
    ).count() == 1

    # A non-baseline scenario may still be selected on its own; the constraint only says
    # "baseline implies selected", and the select action keeps the set single-valued.
    other = _salesforecasting_scenario(
        salesforecasting_tenant_a, salesforecasting_period_a, name="An upside", is_selected=True,
    )
    assert other.is_baseline is False and other.is_selected is True


def test_salesforecasting_scenario_is_selected_is_workflow_owned_not_a_form_field(salesforecasting_tenant_a):
    # It is a real column -- the board reads it -- but never a user-editable one.
    assert "is_selected" in _salesforecasting_concrete_fields(ForecastScenario)
    assert "is_selected" not in ForecastScenarioForm.Meta.fields
    form = ForecastScenarioForm(tenant=salesforecasting_tenant_a)
    assert "is_selected" not in form.fields
    # The projection snapshots are editable=False, so they are structurally absent too.
    for snapshot in ("projected_commit_amount", "projected_total_amount"):
        assert _salesforecasting_field(ForecastScenario, snapshot).editable is False
        assert snapshot not in form.fields
    assert set(form._meta.fields) == {
        "period", "owner", "name", "scenario_type", "probability_pct", "is_baseline",
        "pipeline_delta_pct", "best_case_delta_pct", "commit_delta_pct", "assumption_notes",
    }



def test_salesforecasting_scenario_projects_the_baseline_without_touching_the_submission(salesforecasting_scenario_a, salesforecasting_submission_a):
    scenario = salesforecasting_scenario_a
    submission = salesforecasting_submission_a

    # +10% pipeline, +5% best case, +0% commit on 10000 / 8000 / 5000.
    assert scenario.effective_pipeline_amount == Decimal("11000.00")
    assert scenario.effective_best_case_amount == Decimal("8400.00")
    assert scenario.effective_commit_amount == Decimal("5000.00")
    assert scenario.effective_amounts() == (
        Decimal("11000.00"), Decimal("8400.00"), Decimal("5000.00"),
    )

    # The projection is a snapshot on the scenario row -- and on nothing else.
    before = (
        submission.pipeline_amount, submission.best_case_amount, submission.commit_amount,
        submission.quota_amount, submission.actual_amount, submission.status,
    )
    scenario.snapshot_projection()
    scenario.save()
    scenario.refresh_from_db()
    assert scenario.projected_commit_amount == Decimal("5000.00")
    assert scenario.projected_total_amount == Decimal("24400.00")

    submission.refresh_from_db()
    after = (
        submission.pipeline_amount, submission.best_case_amount, submission.commit_amount,
        submission.quota_amount, submission.actual_amount, submission.status,
    )
    assert after == before


def test_salesforecasting_scenario_without_a_baseline_is_unknown_not_zero(salesforecasting_tenant_a):
    empty_period = _salesforecasting_period(
        salesforecasting_tenant_a, name="No calls yet", period_type="quarter", period_year=2018, period_number=2,
    )
    scenario = _salesforecasting_scenario(salesforecasting_tenant_a, empty_period, name="Blind upside")

    assert scenario.baseline_submission() is None
    assert scenario.effective_pipeline_amount is None
    assert scenario.effective_best_case_amount is None
    assert scenario.effective_commit_amount is None
    assert scenario.effective_amounts() == (None, None, None)

    # The projection floors at zero rather than rendering a negative or a fake figure.
    scenario.snapshot_projection()
    assert scenario.projected_commit_amount == Decimal("0.00")
    assert scenario.projected_total_amount == Decimal("0.00")


def test_salesforecasting_scenario_rejects_a_locked_period_and_an_out_of_band_delta(salesforecasting_tenant_a, salesforecasting_period_a):
    locked_period = _salesforecasting_period(
        salesforecasting_tenant_a, name="Frozen", period_type="quarter", period_year=2017, period_number=1,
        is_locked=True,
    )
    on_locked = ForecastScenario(tenant=salesforecasting_tenant_a, period=locked_period, name="Too late")
    with pytest.raises(ValidationError) as excinfo:
        on_locked.clean()
    assert "period" in excinfo.value.message_dict

    for field_name in ("pipeline_delta_pct", "best_case_delta_pct", "commit_delta_pct"):
        wild = ForecastScenario(
            tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
            name=f"Wild {field_name}", **{field_name: Decimal("5000.00")},
        )
        with pytest.raises(ValidationError) as excinfo:
            wild.clean()
        assert field_name in excinfo.value.message_dict

    out_of_band = ForecastScenario(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
        name="Total wipeout", commit_delta_pct=Decimal("-150.00"),
    )
    with pytest.raises(ValidationError) as excinfo:
        out_of_band.clean()
    assert "commit_delta_pct" in excinfo.value.message_dict

    heavy_weight = ForecastScenario(
        tenant=salesforecasting_tenant_a, period=salesforecasting_period_a,
        name="Heavy", probability_pct=140,
    )
    with pytest.raises(ValidationError) as excinfo:
        heavy_weight.clean()
    assert "probability_pct" in excinfo.value.message_dict

    # The band edges themselves are legal, and a -100% delta is a total wipeout.
    edge = _salesforecasting_scenario(
        salesforecasting_tenant_a, salesforecasting_period_a, name="Wipeout",
        pipeline_delta_pct=Decimal("-100.00"), best_case_delta_pct=Decimal("1000.00"),
    )
    assert edge.pipeline_delta_pct == Decimal("-100.00")
    assert edge.best_case_delta_pct == Decimal("1000.00")



# ============================================================================
# 6. Tenant isolation -- a row from another workspace is never reachable
# ============================================================================

def test_salesforecasting_tenant_isolation_never_reaches_another_workspace(
    salesforecasting_tenant_a,
    salesforecasting_tenant_b,
    salesforecasting_period_a,
    salesforecasting_period_b,
    salesforecasting_submission_a,
    salesforecasting_adjustment_a,
):
    # Build a parallel footprint in the other workspace.
    submission_b = _salesforecasting_submission(salesforecasting_tenant_b, salesforecasting_period_b)
    adjustment_b = _salesforecasting_adjustment(salesforecasting_tenant_b, submission_b)
    scenario_b = _salesforecasting_scenario(salesforecasting_tenant_b, salesforecasting_period_b, name="Globex plan")

    assert salesforecasting_tenant_a.pk != salesforecasting_tenant_b.pk
    assert salesforecasting_period_a.tenant_id == salesforecasting_tenant_a.pk
    assert salesforecasting_period_b.tenant_id == salesforecasting_tenant_b.pk

    for model, mine, theirs in (
        (ForecastPeriod, salesforecasting_period_a, salesforecasting_period_b),
        (ForecastSubmission, salesforecasting_submission_a, submission_b),
        (ForecastAdjustment, salesforecasting_adjustment_a, adjustment_b),
        (ForecastScenario, None, scenario_b),
    ):
        visible = model.objects.filter(tenant=salesforecasting_tenant_a)
        assert theirs.pk not in set(visible.values_list("pk", flat=True))
        assert theirs.tenant_id == salesforecasting_tenant_b.pk
        if mine is not None:
            assert mine.pk in set(visible.values_list("pk", flat=True))

    # The reverse accessors are tenant-safe too: a period only ever lists its own rows.
    assert list(salesforecasting_period_a.submissions.all()) == [salesforecasting_submission_a]
    assert list(salesforecasting_period_b.submissions.all()) == [submission_b]
    assert salesforecasting_period_a.scenarios.count() == 0
    assert list(salesforecasting_period_b.scenarios.all()) == [scenario_b]

    # The per-tenant auto-number is unique per workspace, not globally: two tenants both
    # hold an FCP-00001 and neither can see the other's.
    assert salesforecasting_period_a.number == salesforecasting_period_b.number == "FCP-00001"
    assert ForecastPeriod.objects.filter(number="FCP-00001").count() == 2
    assert ForecastPeriod.objects.filter(
        tenant=salesforecasting_tenant_a, number="FCP-00001",
    ).count() == 1

    # A cross-tenant parent is refused on the way in, not filtered on the way out.
    intruder = ForecastScenario(tenant=salesforecasting_tenant_a, name="Intruder", period=salesforecasting_period_b)
    with pytest.raises(ValidationError) as excinfo:
        intruder.clean()
    assert "period" in excinfo.value.message_dict

