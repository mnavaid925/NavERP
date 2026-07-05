"""Tests for HRM 3.18 Goal Setting models: GoalPeriod (clean()/avg_progress_pct), Objective
(progress_pct weighted rollup/health_status pace/clean() self-parent+cycle guard), KeyResult
(progress_pct interpolation per metric_type/health_status), GoalCheckIn (save() advances
KeyResult.current_value on create only, auto-numbering)."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ================================================================ GoalPeriod
class TestGoalPeriodModel:
    def test_default_status_is_draft(self, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="Q4 2026", start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 12, 31),
        )
        assert gp.status == "draft"

    def test_default_period_type_is_quarterly(self, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="Q4 2026", start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 12, 31),
        )
        assert gp.period_type == "quarterly"

    def test_str_contains_name_and_period_type_display(self, goal_period_a):
        s = str(goal_period_a)
        assert goal_period_a.name in s
        assert "Quarterly" in s

    def test_clean_rejects_end_date_equal_start_date(self, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod(
            tenant=tenant_a, name="Bad Period",
            start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 7, 1),
        )
        with pytest.raises(ValidationError):
            gp.clean()

    def test_clean_rejects_end_date_before_start_date(self, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod(
            tenant=tenant_a, name="Bad Period",
            start_date=datetime.date(2026, 7, 10), end_date=datetime.date(2026, 7, 1),
        )
        with pytest.raises(ValidationError):
            gp.clean()

    def test_clean_accepts_end_date_after_start_date(self, goal_period_a):
        goal_period_a.clean()  # must not raise

    def test_unique_together_tenant_name(self, tenant_a, goal_period_a):
        from apps.hrm.models import GoalPeriod
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            GoalPeriod.objects.create(
                tenant=tenant_a, name=goal_period_a.name,
                start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 3, 31),
            )

    def test_objective_count_zero_with_no_objectives(self, goal_period_a):
        assert goal_period_a.objective_count == 0

    def test_objective_count_reflects_objectives(self, goal_period_a, objective_a):
        assert goal_period_a.objective_count == 1

    def test_avg_progress_pct_zero_with_no_objectives(self, goal_period_a):
        assert goal_period_a.avg_progress_pct == Decimal("0")

    def test_avg_progress_pct_is_simple_mean_of_objectives(self, tenant_a, goal_period_a, employee_a):
        """Two objectives (0 KRs => 0%, and one with a 100%-complete KR => 100%) -> simple mean 50%."""
        from apps.hrm.models import KeyResult, Objective
        obj1 = Objective.objects.create(
            tenant=tenant_a, title="No KRs", owner=employee_a, goal_period=goal_period_a)
        obj2 = Objective.objects.create(
            tenant=tenant_a, title="Fully done", owner=employee_a, goal_period=goal_period_a)
        KeyResult.objects.create(
            tenant=tenant_a, objective=obj2, title="Done KR", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("100"),
            weight=Decimal("100"),
        )
        goal_period_a.refresh_from_db()
        assert goal_period_a.avg_progress_pct == Decimal("50")
        assert obj1.progress_pct == Decimal("0")


# ================================================================ Objective — numbering / defaults
class TestObjectiveDefaults:
    def test_number_auto_assigns_obj_prefix(self, objective_a):
        assert objective_a.number.startswith("OBJ-")

    def test_default_status_is_draft(self, tenant_a, employee_a, goal_period_a):
        from apps.hrm.models import Objective
        obj = Objective.objects.create(
            tenant=tenant_a, title="New Objective", owner=employee_a, goal_period=goal_period_a)
        assert obj.status == "draft"

    def test_default_scope_is_individual(self, tenant_a, employee_a, goal_period_a):
        from apps.hrm.models import Objective
        obj = Objective.objects.create(
            tenant=tenant_a, title="New Objective", owner=employee_a, goal_period=goal_period_a)
        assert obj.scope == "individual"

    def test_default_target_type_is_committed(self, tenant_a, employee_a, goal_period_a):
        from apps.hrm.models import Objective
        obj = Objective.objects.create(
            tenant=tenant_a, title="New Objective", owner=employee_a, goal_period=goal_period_a)
        assert obj.target_type == "committed"

    def test_default_weight_is_100(self, tenant_a, employee_a, goal_period_a):
        from apps.hrm.models import Objective
        obj = Objective.objects.create(
            tenant=tenant_a, title="New Objective", owner=employee_a, goal_period=goal_period_a)
        assert obj.weight == Decimal("100")

    def test_str_contains_number_and_title(self, objective_a):
        s = str(objective_a)
        assert objective_a.number in s
        assert objective_a.title in s

    def test_unique_together_tenant_number(self, tenant_a, objective_a):
        from apps.hrm.models import Objective
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            Objective.objects.create(
                tenant=tenant_a, number=objective_a.number, title="Duplicate number",
                owner=objective_a.owner, goal_period=objective_a.goal_period)

    def test_key_result_count_zero_with_no_krs(self, objective_a):
        assert objective_a.key_result_count == 0

    def test_key_result_count_reflects_key_results(self, objective_a, key_result_a):
        assert objective_a.key_result_count == 1


# ================================================================ Objective.progress_pct
class TestObjectiveProgressPct:
    def test_zero_with_no_key_results(self, objective_a):
        assert objective_a.progress_pct == Decimal("0")

    def test_weighted_rollup_two_krs(self, tenant_a, objective_a):
        """KR1 60% @ weight 70, KR2 0% @ weight 30 -> (60*70 + 0*30)/100 = 42%."""
        from apps.hrm.models import KeyResult
        KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="KR1", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("60"),
            weight=Decimal("70"),
        )
        KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="KR2", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("0"),
            weight=Decimal("30"),
        )
        objective_a.refresh_from_db()
        assert objective_a.progress_pct == Decimal("42")

    def test_single_kr_matches_its_own_progress(self, objective_a, key_result_a):
        objective_a.refresh_from_db()
        assert objective_a.progress_pct == key_result_a.progress_pct == Decimal("60")

    def test_simple_mean_fallback_when_all_weights_zero(self, tenant_a, objective_a):
        """Both KRs at weight 0 -> falls back to a plain arithmetic mean, not a weighted rollup
        (which would otherwise divide by a zero total_weight)."""
        from apps.hrm.models import KeyResult
        KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="KR1", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("80"),
            weight=Decimal("0"),
        )
        KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="KR2", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("20"),
            weight=Decimal("0"),
        )
        objective_a.refresh_from_db()
        assert objective_a.progress_pct == Decimal("50")


# ================================================================ Objective.health_status
class TestObjectiveHealthStatus:
    def test_completed_status_short_circuits_to_completed(self, tenant_a, employee_a, goal_period_a):
        from apps.hrm.models import Objective
        obj = Objective.objects.create(
            tenant=tenant_a, title="Done", owner=employee_a, goal_period=goal_period_a,
            status="completed",
        )
        assert obj.health_status == "completed"
        assert obj.health_status_display == "Completed"

    def test_on_track_when_progress_matches_pace(self, tenant_a, employee_a):
        """A period that started 50% of the way through with progress at ~50% is on_track (gap<=10)."""
        from apps.hrm.models import GoalPeriod, KeyResult, Objective
        today = timezone.localdate()
        period = GoalPeriod.objects.create(
            tenant=tenant_a, name="Pace Period", status="active",
            start_date=today - datetime.timedelta(days=50), end_date=today + datetime.timedelta(days=50),
        )
        obj = Objective.objects.create(
            tenant=tenant_a, title="On pace", owner=employee_a, goal_period=period, status="active")
        KeyResult.objects.create(
            tenant=tenant_a, objective=obj, title="KR", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("50"),
            weight=Decimal("100"),
        )
        obj.refresh_from_db()
        assert obj.health_status == "on_track"

    def test_at_risk_when_behind_pace(self, tenant_a, employee_a):
        """Period 80% elapsed but progress only 60% -> gap 20, within (10, 25] -> at_risk."""
        from apps.hrm.models import GoalPeriod, KeyResult, Objective
        today = timezone.localdate()
        period = GoalPeriod.objects.create(
            tenant=tenant_a, name="At Risk Period", status="active",
            start_date=today - datetime.timedelta(days=80), end_date=today + datetime.timedelta(days=20),
        )
        obj = Objective.objects.create(
            tenant=tenant_a, title="Behind", owner=employee_a, goal_period=period, status="active")
        KeyResult.objects.create(
            tenant=tenant_a, objective=obj, title="KR", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("60"),
            weight=Decimal("100"),
        )
        obj.refresh_from_db()
        assert obj.health_status == "at_risk"

    def test_off_track_when_far_behind_pace(self, tenant_a, employee_a):
        """Period 100% elapsed (ended) but progress only 10% -> gap 90 -> off_track."""
        from apps.hrm.models import GoalPeriod, KeyResult, Objective
        today = timezone.localdate()
        period = GoalPeriod.objects.create(
            tenant=tenant_a, name="Off Track Period", status="active",
            start_date=today - datetime.timedelta(days=100), end_date=today - datetime.timedelta(days=1),
        )
        obj = Objective.objects.create(
            tenant=tenant_a, title="Way behind", owner=employee_a, goal_period=period, status="active")
        KeyResult.objects.create(
            tenant=tenant_a, objective=obj, title="KR", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("10"),
            weight=Decimal("100"),
        )
        obj.refresh_from_db()
        assert obj.health_status == "off_track"

    def test_zero_length_period_no_zero_division_error(self, tenant_a, employee_a):
        """start_date == due_date on the objective itself (falls back from the period window) must
        not raise ZeroDivisionError — the guard treats a <=0-day window as 100% elapsed."""
        from apps.hrm.models import GoalPeriod, Objective
        period = GoalPeriod.objects.create(
            tenant=tenant_a, name="Normal Period", status="active",
            start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 12, 31),
        )
        same_day = datetime.date(2026, 6, 15)
        obj = Objective.objects.create(
            tenant=tenant_a, title="Zero-length window", owner=employee_a, goal_period=period,
            status="active", start_date=same_day, due_date=same_day,
        )
        # Must not raise — this is the assertion under test.
        health = obj.health_status
        assert health in ("on_track", "at_risk", "off_track", "completed")

    def test_falls_back_to_goal_period_window_when_own_dates_null(self, objective_a):
        """objective_a has no start_date/due_date of its own -> health_status uses goal_period's window
        without raising."""
        assert objective_a.start_date is None
        assert objective_a.due_date is None
        health = objective_a.health_status  # must not raise
        assert health in ("on_track", "at_risk", "off_track", "completed")


# ================================================================ Objective.clean() — parenting
class TestObjectiveCleanParenting:
    def test_rejects_self_parenting(self, objective_a):
        objective_a.parent_objective_id = objective_a.pk
        with pytest.raises(ValidationError):
            objective_a.clean()

    def test_rejects_multi_hop_cycle(self, tenant_a, employee_a, goal_period_a):
        """A -> B -> A: assigning A as B's parent, then trying to assign B as A's parent must raise."""
        from apps.hrm.models import Objective
        obj_a = Objective.objects.create(
            tenant=tenant_a, title="A", owner=employee_a, goal_period=goal_period_a)
        obj_b = Objective.objects.create(
            tenant=tenant_a, title="B", owner=employee_a, goal_period=goal_period_a,
            parent_objective=obj_a,
        )
        obj_a.parent_objective = obj_b
        with pytest.raises(ValidationError):
            obj_a.clean()

    def test_accepts_valid_parent(self, tenant_a, employee_a, goal_period_a):
        from apps.hrm.models import Objective
        parent = Objective.objects.create(
            tenant=tenant_a, title="Parent", owner=employee_a, goal_period=goal_period_a)
        child = Objective(
            tenant=tenant_a, title="Child", owner=employee_a, goal_period=goal_period_a,
            parent_objective=parent,
        )
        child.clean()  # must not raise

    def test_accepts_no_parent(self, objective_a):
        objective_a.clean()  # must not raise


# ================================================================ KeyResult — defaults / numbering
class TestKeyResultDefaults:
    def test_number_auto_assigns_kr_prefix(self, key_result_a):
        assert key_result_a.number.startswith("KR-")

    def test_default_status_not_started(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Fresh KR", metric_type="numeric",
            target_value=Decimal("100"),
        )
        assert kr.status == "not_started"

    def test_default_metric_type_numeric(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Fresh KR", target_value=Decimal("100"))
        assert kr.metric_type == "numeric"

    def test_default_weight_zero(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Fresh KR", target_value=Decimal("100"))
        assert kr.weight == Decimal("0")

    def test_str_contains_number_title_and_metric_display(self, key_result_a):
        s = str(key_result_a)
        assert key_result_a.number in s
        assert key_result_a.title in s
        assert "Numeric" in s

    def test_unique_together_tenant_number(self, tenant_a, key_result_a):
        from apps.hrm.models import KeyResult
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            KeyResult.objects.create(
                tenant=tenant_a, number=key_result_a.number, objective=key_result_a.objective,
                title="Dup number", metric_type="numeric", target_value=Decimal("100"))


# ================================================================ KeyResult.clean()
class TestKeyResultClean:
    @pytest.mark.parametrize("metric_type", ["numeric", "percentage", "currency"])
    def test_rejects_missing_target_value_for_numeric_family(self, tenant_a, objective_a, metric_type):
        from apps.hrm.models import KeyResult
        kr = KeyResult(
            tenant=tenant_a, objective=objective_a, title="No target",
            metric_type=metric_type, target_value=None)
        with pytest.raises(ValidationError):
            kr.clean()

    def test_accepts_missing_target_value_for_boolean(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult(
            tenant=tenant_a, objective=objective_a, title="Bool KR",
            metric_type="boolean", target_value=None)
        kr.clean()  # must not raise

    def test_accepts_missing_target_value_for_milestone(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult(
            tenant=tenant_a, objective=objective_a, title="Milestone KR",
            metric_type="milestone", target_value=None)
        kr.clean()  # must not raise

    def test_rejects_negative_weight(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult(
            tenant=tenant_a, objective=objective_a, title="Neg weight",
            metric_type="numeric", target_value=Decimal("100"), weight=Decimal("-5"))
        with pytest.raises(ValidationError):
            kr.clean()


# ================================================================ KeyResult.progress_pct
class TestKeyResultProgressPct:
    def test_numeric_interpolation(self, key_result_a):
        """start=0, target=100, current=60 -> 60%."""
        assert key_result_a.progress_pct == Decimal("60")

    def test_numeric_zero_denominator_current_meets_target_returns_100(self, tenant_a, objective_a):
        """start_value == target_value guard: current_value >= target_value -> 100."""
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Flat target", metric_type="numeric",
            start_value=Decimal("50"), target_value=Decimal("50"), current_value=Decimal("50"),
        )
        assert kr.progress_pct == Decimal("100")

    def test_numeric_zero_denominator_current_below_target_returns_zero(self, tenant_a, objective_a):
        """start_value == target_value guard: current_value < target_value -> 0 (no ZeroDivisionError)."""
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Flat target missed", metric_type="numeric",
            start_value=Decimal("50"), target_value=Decimal("50"), current_value=Decimal("40"),
        )
        assert kr.progress_pct == Decimal("0")

    def test_numeric_clamps_above_100(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Overachieved", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("150"),
        )
        assert kr.progress_pct == Decimal("100")

    def test_numeric_clamps_below_zero(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Regressed", metric_type="numeric",
            start_value=Decimal("50"), target_value=Decimal("100"), current_value=Decimal("0"),
        )
        assert kr.progress_pct == Decimal("0")

    def test_numeric_no_current_value_falls_back_to_start(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Not started yet", metric_type="numeric",
            start_value=Decimal("20"), target_value=Decimal("100"), current_value=None,
        )
        assert kr.progress_pct == Decimal("0")

    def test_boolean_completed_returns_100(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Bool KR", metric_type="boolean",
            status="completed",
        )
        assert kr.progress_pct == Decimal("100")

    def test_boolean_not_completed_returns_zero(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Bool KR", metric_type="boolean",
            status="in_progress",
        )
        assert kr.progress_pct == Decimal("0")

    def test_milestone_completed_returns_100(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Milestone KR", metric_type="milestone",
            status="completed",
        )
        assert kr.progress_pct == Decimal("100")

    def test_milestone_not_completed_returns_zero(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Milestone KR", metric_type="milestone",
            status="not_started",
        )
        assert kr.progress_pct == Decimal("0")


# ================================================================ KeyResult.health_status
class TestKeyResultHealthStatus:
    def test_completed_status_short_circuits(self, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Done KR", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("10"),
            status="completed",
        )
        assert kr.health_status == "completed"
        assert kr.health_status_display == "Completed"

    def test_uses_parent_objective_goal_period_window(self, key_result_a, goal_period_a):
        """No ZeroDivisionError / crash — resolves the period via objective.goal_period."""
        health = key_result_a.health_status
        assert health in ("on_track", "at_risk", "off_track", "completed")


# ================================================================ GoalCheckIn
class TestGoalCheckInModel:
    def test_number_auto_assigns_gci_prefix(self, goal_checkin_a):
        assert goal_checkin_a.number.startswith("GCI-")

    def test_default_confidence_on_track(self, tenant_a, key_result_a):
        from apps.hrm.models import GoalCheckIn
        checkin = GoalCheckIn.objects.create(
            tenant=tenant_a, key_result=key_result_a, checkin_date=datetime.date(2026, 7, 20))
        assert checkin.confidence == "on_track"

    def test_str_contains_number_kr_title_and_confidence(self, goal_checkin_a):
        s = str(goal_checkin_a)
        assert goal_checkin_a.number in s
        assert goal_checkin_a.key_result.title in s
        assert "On Track" in s

    def test_unique_together_tenant_number(self, tenant_a, goal_checkin_a):
        from apps.hrm.models import GoalCheckIn
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            GoalCheckIn.objects.create(
                tenant=tenant_a, number=goal_checkin_a.number, key_result=goal_checkin_a.key_result,
                checkin_date=datetime.date(2026, 7, 21))

    def test_save_advances_key_result_current_value_on_create(self, tenant_a, objective_a):
        """A NEW check-in with a value_at_checkin advances the parent KR's current_value."""
        from apps.hrm.models import GoalCheckIn, KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Advance me", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("10"),
        )
        GoalCheckIn.objects.create(
            tenant=tenant_a, key_result=kr, checkin_date=datetime.date(2026, 7, 20),
            value_at_checkin=Decimal("45"),
        )
        kr.refresh_from_db()
        assert kr.current_value == Decimal("45")

    def test_save_does_not_advance_when_value_at_checkin_is_none(self, tenant_a, objective_a):
        from apps.hrm.models import GoalCheckIn, KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="No value", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("10"),
        )
        GoalCheckIn.objects.create(
            tenant=tenant_a, key_result=kr, checkin_date=datetime.date(2026, 7, 20),
            value_at_checkin=None,
        )
        kr.refresh_from_db()
        assert kr.current_value == Decimal("10")  # unchanged

    def test_save_does_not_re_advance_on_later_edit(self, tenant_a, objective_a):
        """A subsequent save() (edit) of an EXISTING check-in must NOT re-run the advance logic —
        only the create path (is_create) triggers it."""
        from apps.hrm.models import GoalCheckIn, KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Edit me", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("10"),
        )
        checkin = GoalCheckIn.objects.create(
            tenant=tenant_a, key_result=kr, checkin_date=datetime.date(2026, 7, 20),
            value_at_checkin=Decimal("45"),
        )
        kr.refresh_from_db()
        assert kr.current_value == Decimal("45")
        # Manually move the KR's current_value elsewhere (simulating a separate update)...
        kr.current_value = Decimal("99")
        kr.save(update_fields=["current_value"])
        # ...then edit/re-save the EXISTING check-in with a different value_at_checkin.
        checkin.value_at_checkin = Decimal("70")
        checkin.comment = "revised note"
        checkin.save()
        kr.refresh_from_db()
        assert kr.current_value == Decimal("99")  # NOT re-advanced to 70

    def test_save_advances_only_when_value_differs(self, tenant_a, objective_a):
        """No redundant write when value_at_checkin already equals current_value (no-op update_fields
        path still exercised, but current_value stays exactly equal)."""
        from apps.hrm.models import GoalCheckIn, KeyResult
        kr = KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="Same value", metric_type="numeric",
            start_value=Decimal("0"), target_value=Decimal("100"), current_value=Decimal("30"),
        )
        GoalCheckIn.objects.create(
            tenant=tenant_a, key_result=kr, checkin_date=datetime.date(2026, 7, 20),
            value_at_checkin=Decimal("30"),
        )
        kr.refresh_from_db()
        assert kr.current_value == Decimal("30")
