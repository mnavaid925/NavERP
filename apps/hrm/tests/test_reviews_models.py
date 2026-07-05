"""Tests for HRM 3.19 Performance Review models: ReviewCycle (phase machine/clean() window
guards/review_count), ReviewTemplate (usage_count), PerformanceReview (clean() self/manager
guards, _ratings()-cached overall_rating weighted mean / simple-mean fallback / None-when-empty,
effective_rating calibrated-override, reviewer_anonymized, goal_period passthrough), ReviewRating
(clean() rating_value/weight bounds), auto-numbering RVT-/RVW-/RVR- per tenant."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

pytestmark = pytest.mark.django_db


# ================================================================ ReviewCycle
class TestReviewCycleModel:
    def test_default_status_is_draft(self, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle.objects.create(tenant=tenant_a, name="Fresh Cycle")
        assert rc.status == "draft"

    def test_default_cycle_type_is_annual(self, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle.objects.create(tenant=tenant_a, name="Fresh Cycle")
        assert rc.cycle_type == "annual"

    def test_str_contains_name_and_cycle_type_display(self, review_cycle_a):
        s = str(review_cycle_a)
        assert review_cycle_a.name in s
        assert "Half-Yearly" in s

    def test_no_auto_number(self, review_cycle_a):
        """ReviewCycle is TenantOwned, not TenantNumbered — it has no `number` attribute."""
        assert not hasattr(review_cycle_a, "number")

    def test_unique_together_tenant_name(self, tenant_a, review_cycle_a):
        from apps.hrm.models import ReviewCycle
        with pytest.raises(IntegrityError):
            ReviewCycle.objects.create(tenant=tenant_a, name=review_cycle_a.name)

    def test_phase_order_class_tuple(self):
        from apps.hrm.models import ReviewCycle
        assert ReviewCycle.PHASE_ORDER == (
            "draft", "self_assessment", "manager_review", "calibration", "released", "closed")

    def test_review_count_zero_with_no_reviews(self, review_cycle_a):
        assert review_cycle_a.review_count == 0

    def test_review_count_reflects_reviews(self, review_cycle_a, performance_review_a):
        assert review_cycle_a.review_count == 1

    def test_goal_period_set_null_on_goal_period_delete(self, tenant_a, review_cycle_a, goal_period_a):
        goal_period_a.delete()
        review_cycle_a.refresh_from_db()
        assert review_cycle_a.goal_period_id is None


class TestReviewCycleCleanWindowGuards:
    def test_rejects_self_review_end_before_start(self, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle(
            tenant=tenant_a, name="Bad Self Window",
            self_review_start=datetime.date(2026, 7, 15), self_review_end=datetime.date(2026, 7, 1))
        with pytest.raises(ValidationError):
            rc.clean()

    def test_rejects_self_review_end_equal_start(self, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle(
            tenant=tenant_a, name="Flat Self Window",
            self_review_start=datetime.date(2026, 7, 1), self_review_end=datetime.date(2026, 7, 1))
        with pytest.raises(ValidationError):
            rc.clean()

    def test_rejects_manager_review_end_before_start(self, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle(
            tenant=tenant_a, name="Bad Manager Window",
            manager_review_start=datetime.date(2026, 8, 1), manager_review_end=datetime.date(2026, 7, 20))
        with pytest.raises(ValidationError):
            rc.clean()

    def test_rejects_manager_start_before_self_review_end(self, tenant_a):
        """Manager review can't start before self-assessment closes."""
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle(
            tenant=tenant_a, name="Overlapping Windows",
            self_review_start=datetime.date(2026, 7, 1), self_review_end=datetime.date(2026, 7, 20),
            manager_review_start=datetime.date(2026, 7, 10), manager_review_end=datetime.date(2026, 7, 31))
        with pytest.raises(ValidationError):
            rc.clean()

    def test_accepts_manager_start_equal_self_review_end(self, tenant_a):
        """manager_review_start == self_review_end is allowed (only strictly-before is rejected)."""
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle(
            tenant=tenant_a, name="Back-to-back Windows",
            self_review_start=datetime.date(2026, 7, 1), self_review_end=datetime.date(2026, 7, 15),
            manager_review_start=datetime.date(2026, 7, 15), manager_review_end=datetime.date(2026, 7, 31))
        rc.clean()  # must not raise

    def test_accepts_valid_windows(self, review_cycle_a):
        review_cycle_a.clean()  # must not raise

    def test_accepts_no_windows_set(self, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle(tenant=tenant_a, name="No Windows Yet")
        rc.clean()  # must not raise — all window fields are null=True, blank=True


# ================================================================ ReviewTemplate
class TestReviewTemplateModel:
    def test_number_auto_assigns_rvt_prefix(self, review_template_a):
        assert review_template_a.number.startswith("RVT-")

    def test_default_review_type_is_self(self, tenant_a):
        from apps.hrm.models import ReviewTemplate
        rt = ReviewTemplate.objects.create(tenant=tenant_a, name="Default Type Template")
        assert rt.review_type == "self"

    def test_default_rating_scale_max_is_5(self, tenant_a):
        from apps.hrm.models import ReviewTemplate
        rt = ReviewTemplate.objects.create(tenant=tenant_a, name="Default Scale Template")
        assert rt.rating_scale_max == 5

    def test_default_include_goals_false(self, tenant_a):
        from apps.hrm.models import ReviewTemplate
        rt = ReviewTemplate.objects.create(tenant=tenant_a, name="No Goals Template")
        assert rt.include_goals is False

    def test_default_is_anonymous_false(self, tenant_a):
        from apps.hrm.models import ReviewTemplate
        rt = ReviewTemplate.objects.create(tenant=tenant_a, name="Not Anon Template")
        assert rt.is_anonymous is False

    def test_default_is_active_true(self, tenant_a):
        from apps.hrm.models import ReviewTemplate
        rt = ReviewTemplate.objects.create(tenant=tenant_a, name="Active Template")
        assert rt.is_active is True

    def test_str_contains_number_name_and_review_type_display(self, review_template_a):
        s = str(review_template_a)
        assert review_template_a.number in s
        assert review_template_a.name in s
        assert "Manager" in s

    def test_unique_together_tenant_number(self, tenant_a, review_template_a):
        from apps.hrm.models import ReviewTemplate
        with pytest.raises(IntegrityError):
            ReviewTemplate.objects.create(
                tenant=tenant_a, number=review_template_a.number, name="Duplicate number")

    def test_usage_count_zero_with_no_reviews(self, review_template_a):
        assert review_template_a.usage_count == 0

    def test_usage_count_reflects_reviews(self, review_template_a, performance_review_a):
        assert review_template_a.usage_count == 1

    @pytest.mark.parametrize("bad_max", [1, 11])
    def test_rating_scale_max_validators_reject_out_of_range(self, tenant_a, bad_max):
        from apps.hrm.models import ReviewTemplate
        rt = ReviewTemplate(tenant=tenant_a, name="Out of Range", rating_scale_max=bad_max)
        with pytest.raises(ValidationError):
            rt.full_clean()

    @pytest.mark.parametrize("ok_max", [2, 5, 10])
    def test_rating_scale_max_validators_accept_in_range(self, tenant_a, ok_max):
        from apps.hrm.models import ReviewTemplate
        rt = ReviewTemplate(tenant=tenant_a, name=f"In Range {ok_max}", rating_scale_max=ok_max)
        rt.full_clean()  # must not raise


# ================================================================ PerformanceReview — numbering / defaults
class TestPerformanceReviewDefaults:
    def test_number_auto_assigns_rvw_prefix(self, performance_review_a):
        assert performance_review_a.number.startswith("RVW-")

    def test_default_status_is_draft(self, tenant_a, review_cycle_a, employee_a):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a,
            review_type="self")
        assert pr.status == "draft"

    def test_default_review_type_is_self(self, tenant_a, review_cycle_a, employee_a):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a)
        assert pr.review_type == "self"

    def test_default_is_anonymous_false(self, performance_review_a):
        assert performance_review_a.is_anonymous is False

    def test_str_contains_number_subject_name_and_type_display(self, performance_review_a):
        s = str(performance_review_a)
        assert performance_review_a.number in s
        assert performance_review_a.subject.party.name in s
        assert "Manager" in s

    def test_unique_together_tenant_number(self, tenant_a, performance_review_a):
        from apps.hrm.models import PerformanceReview
        with pytest.raises(IntegrityError):
            PerformanceReview.objects.create(
                tenant=tenant_a, number=performance_review_a.number,
                cycle=performance_review_a.cycle, subject=performance_review_a.subject,
                reviewer=performance_review_a.reviewer, review_type="manager")

    def test_cycle_is_protect(self, review_cycle_a, performance_review_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            review_cycle_a.delete()

    def test_template_is_set_null(self, tenant_a, review_template_a, performance_review_a):
        review_template_a.delete()
        performance_review_a.refresh_from_db()
        assert performance_review_a.template_id is None

    def test_subject_is_protect(self, employee_a, performance_review_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a.delete()


class TestPerformanceReviewClean:
    def test_self_review_rejects_reviewer_not_equal_subject(self, tenant_a, review_cycle_a, employee_a, employee_a2):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="self")
        with pytest.raises(ValidationError):
            pr.clean()

    def test_self_review_accepts_reviewer_equal_subject(self, tenant_a, review_cycle_a, employee_a):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a,
            review_type="self")
        pr.clean()  # must not raise

    def test_non_self_review_rejects_reviewer_equal_subject(self, tenant_a, review_cycle_a, employee_a):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a,
            review_type="manager")
        with pytest.raises(ValidationError):
            pr.clean()

    def test_non_self_review_accepts_reviewer_not_equal_subject(self, performance_review_a):
        performance_review_a.clean()  # must not raise — manager review, reviewer != subject

    @pytest.mark.parametrize("review_type", ["peer", "upward", "skip_level"])
    def test_non_self_review_types_reject_reviewer_equal_subject(
        self, tenant_a, review_cycle_a, employee_a, review_type
    ):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a,
            review_type=review_type)
        with pytest.raises(ValidationError):
            pr.clean()

    def test_manager_rating_rejected_on_non_manager_review(self, tenant_a, review_cycle_a, employee_a):
        """manager_rating only applies to a manager review — a self review with it set is rejected."""
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a,
            review_type="self", manager_rating=Decimal("4.00"))
        with pytest.raises(ValidationError):
            pr.clean()

    def test_manager_rating_accepted_on_manager_review(self, performance_review_a):
        performance_review_a.manager_rating = Decimal("4.50")
        performance_review_a.clean()  # must not raise

    def test_manager_rating_none_accepted_regardless_of_type(self, tenant_a, review_cycle_a, employee_a):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a,
            review_type="self", manager_rating=None)
        pr.clean()  # must not raise


# ================================================================ PerformanceReview.overall_rating
class TestPerformanceReviewOverallRating:
    def test_none_with_no_ratings(self, performance_review_a):
        assert performance_review_a.overall_rating is None

    def test_none_is_not_zero(self, performance_review_a):
        """An unrated review must read as None ('Not yet rated'), never coerced to 0."""
        assert performance_review_a.overall_rating != Decimal("0")
        assert performance_review_a.overall_rating is not Decimal("0")

    def test_weighted_mean_three_ratings(self, tenant_a, performance_review_a):
        """4.5@40 + 4.0@30 + 4.0@30 -> (4.5*40 + 4.0*30 + 4.0*30) / 100 = 4.20."""
        from apps.hrm.models import ReviewRating
        ReviewRating.objects.create(
            tenant=tenant_a, review=performance_review_a, criterion_label="C1",
            rating_value=Decimal("4.50"), weight=Decimal("40"))
        ReviewRating.objects.create(
            tenant=tenant_a, review=performance_review_a, criterion_label="C2",
            rating_value=Decimal("4.00"), weight=Decimal("30"))
        ReviewRating.objects.create(
            tenant=tenant_a, review=performance_review_a, criterion_label="C3",
            rating_value=Decimal("4.00"), weight=Decimal("30"))
        performance_review_a.refresh_from_db()
        assert performance_review_a.overall_rating == Decimal("4.20")

    def test_single_rating_matches_its_own_value(self, performance_review_a, review_rating_a):
        performance_review_a.refresh_from_db()
        assert performance_review_a.overall_rating == review_rating_a.rating_value

    def test_simple_mean_fallback_when_all_weights_zero(self, tenant_a, performance_review_a):
        """Both ratings at weight 0 -> falls back to a plain arithmetic mean (not a weighted
        rollup, which would otherwise divide by a zero total_weight)."""
        from apps.hrm.models import ReviewRating
        ReviewRating.objects.create(
            tenant=tenant_a, review=performance_review_a, criterion_label="C1",
            rating_value=Decimal("5.00"), weight=Decimal("0"))
        ReviewRating.objects.create(
            tenant=tenant_a, review=performance_review_a, criterion_label="C2",
            rating_value=Decimal("3.00"), weight=Decimal("0"))
        performance_review_a.refresh_from_db()
        assert performance_review_a.overall_rating == Decimal("4.00")

    def test_ratings_cached_per_instance(self, tenant_a, performance_review_a, review_rating_a):
        """_ratings() caches on the instance — a rating added AFTER the first access is not picked
        up without a fresh instance/refresh_from_db (mirrors Objective._krs() caching contract)."""
        performance_review_a.overall_rating  # warms the cache
        from apps.hrm.models import ReviewRating
        ReviewRating.objects.create(
            tenant=tenant_a, review=performance_review_a, criterion_label="Late addition",
            rating_value=Decimal("1.00"), weight=Decimal("100"))
        # Still reflects only the originally-cached rating (review_rating_a, 4.00) — not blended
        # with the late addition until refreshed.
        assert performance_review_a.overall_rating == review_rating_a.rating_value


# ================================================================ PerformanceReview.rating_count
class TestPerformanceReviewRatingCount:
    def test_zero_with_no_ratings(self, performance_review_a):
        assert performance_review_a.rating_count == 0

    def test_reflects_rating_rows(self, performance_review_a, review_rating_a):
        performance_review_a.refresh_from_db()
        assert performance_review_a.rating_count == 1


# ================================================================ PerformanceReview.effective_rating
class TestPerformanceReviewEffectiveRating:
    def test_falls_back_to_overall_rating_when_not_calibrated(self, performance_review_a, review_rating_a):
        performance_review_a.refresh_from_db()
        assert performance_review_a.calibrated_rating is None
        assert performance_review_a.effective_rating == performance_review_a.overall_rating

    def test_uses_calibrated_rating_when_set(self, performance_review_a, review_rating_a):
        performance_review_a.calibrated_rating = Decimal("2.00")
        performance_review_a.save(update_fields=["calibrated_rating"])
        performance_review_a.refresh_from_db()
        assert performance_review_a.overall_rating != Decimal("2.00")
        assert performance_review_a.effective_rating == Decimal("2.00")

    def test_none_when_no_ratings_and_no_calibration(self, performance_review_a):
        assert performance_review_a.effective_rating is None


# ================================================================ PerformanceReview.goal_period passthrough
class TestPerformanceReviewGoalPeriodPassthrough:
    def test_returns_cycle_goal_period(self, performance_review_a, goal_period_a):
        assert performance_review_a.goal_period.pk == goal_period_a.pk

    def test_none_when_cycle_has_no_goal_period(self, tenant_a, employee_a):
        from apps.hrm.models import PerformanceReview, ReviewCycle
        cycle = ReviewCycle.objects.create(tenant=tenant_a, name="No Goal Period Cycle")
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=cycle, subject=employee_a, reviewer=employee_a, review_type="self")
        assert pr.goal_period is None


# ================================================================ PerformanceReview.reviewer_anonymized
class TestPerformanceReviewReviewerAnonymized:
    def test_false_for_manager_review_even_if_anonymous_flag_set(self, performance_review_a):
        performance_review_a.is_anonymous = True
        assert performance_review_a.reviewer_anonymized is False

    def test_false_for_self_review(self, tenant_a, review_cycle_a, employee_a):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a,
            review_type="self", is_anonymous=True)
        assert pr.reviewer_anonymized is False

    @pytest.mark.parametrize("review_type", ["peer", "upward"])
    def test_true_for_anonymous_peer_or_upward(self, tenant_a, review_cycle_a, employee_a, employee_a2, review_type):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type=review_type, is_anonymous=True)
        assert pr.reviewer_anonymized is True

    @pytest.mark.parametrize("review_type", ["peer", "upward"])
    def test_false_for_non_anonymous_peer_or_upward(self, tenant_a, review_cycle_a, employee_a, employee_a2, review_type):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type=review_type, is_anonymous=False)
        assert pr.reviewer_anonymized is False

    def test_false_for_anonymous_skip_level(self, tenant_a, review_cycle_a, employee_a, employee_a2):
        """skip_level is deliberately excluded from the anonymize set per the model's docstring."""
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="skip_level", is_anonymous=True)
        assert pr.reviewer_anonymized is False


# ================================================================ ReviewRating — defaults / numbering
class TestReviewRatingDefaults:
    def test_number_auto_assigns_rvr_prefix(self, review_rating_a):
        assert review_rating_a.number.startswith("RVR-")

    def test_default_criterion_category_is_competency(self, tenant_a, performance_review_a):
        from apps.hrm.models import ReviewRating
        rr = ReviewRating.objects.create(
            tenant=tenant_a, review=performance_review_a, criterion_label="Fresh",
            rating_value=Decimal("3.00"))
        assert rr.criterion_category == "competency"

    def test_default_weight_is_zero(self, tenant_a, performance_review_a):
        from apps.hrm.models import ReviewRating
        rr = ReviewRating.objects.create(
            tenant=tenant_a, review=performance_review_a, criterion_label="Fresh",
            rating_value=Decimal("3.00"))
        assert rr.weight == Decimal("0")

    def test_str_contains_number_label_and_rating_value(self, review_rating_a):
        s = str(review_rating_a)
        assert review_rating_a.number in s
        assert review_rating_a.criterion_label in s
        assert str(review_rating_a.rating_value) in s

    def test_unique_together_tenant_number(self, tenant_a, review_rating_a):
        from apps.hrm.models import ReviewRating
        with pytest.raises(IntegrityError):
            ReviewRating.objects.create(
                tenant=tenant_a, number=review_rating_a.number, review=review_rating_a.review,
                criterion_label="Duplicate number", rating_value=Decimal("2.00"))

    def test_review_is_cascade(self, performance_review_a, review_rating_a):
        from apps.hrm.models import ReviewRating
        pk = review_rating_a.pk
        performance_review_a.delete()
        assert not ReviewRating.objects.filter(pk=pk).exists()


class TestReviewRatingClean:
    def test_rejects_negative_rating_value(self, performance_review_a):
        from apps.hrm.models import ReviewRating
        rr = ReviewRating(
            tenant=performance_review_a.tenant, review=performance_review_a,
            criterion_label="Negative", rating_value=Decimal("-1.00"))
        with pytest.raises(ValidationError):
            rr.clean()

    def test_rejects_rating_value_above_template_scale_max(self, performance_review_a):
        """review_template_a's rating_scale_max is 5 — a rating of 6 is rejected."""
        from apps.hrm.models import ReviewRating
        assert performance_review_a.template.rating_scale_max == 5
        rr = ReviewRating(
            tenant=performance_review_a.tenant, review=performance_review_a,
            criterion_label="Too High", rating_value=Decimal("6.00"))
        with pytest.raises(ValidationError):
            rr.clean()

    def test_accepts_rating_value_equal_to_scale_max(self, performance_review_a):
        from apps.hrm.models import ReviewRating
        rr = ReviewRating(
            tenant=performance_review_a.tenant, review=performance_review_a,
            criterion_label="At Max", rating_value=Decimal("5.00"))
        rr.clean()  # must not raise

    def test_accepts_rating_value_within_scale(self, review_rating_a):
        review_rating_a.clean()  # must not raise

    def test_no_scale_check_when_review_has_no_template(self, tenant_a, employee_a):
        """No template linked -> the scale-max guard is skipped (no crash on template_id lookup)."""
        from apps.hrm.models import PerformanceReview, ReviewCycle, ReviewRating
        cycle = ReviewCycle.objects.create(tenant=tenant_a, name="Templateless Cycle")
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=cycle, subject=employee_a, reviewer=employee_a, review_type="self")
        rr = ReviewRating(
            tenant=tenant_a, review=pr, criterion_label="No template check",
            rating_value=Decimal("9999.00"))
        rr.clean()  # must not raise — no template to check against

    def test_rejects_negative_weight(self, performance_review_a):
        from apps.hrm.models import ReviewRating
        rr = ReviewRating(
            tenant=performance_review_a.tenant, review=performance_review_a,
            criterion_label="Neg Weight", rating_value=Decimal("3.00"), weight=Decimal("-5"))
        with pytest.raises(ValidationError):
            rr.clean()

    def test_accepts_zero_weight(self, performance_review_a):
        from apps.hrm.models import ReviewRating
        rr = ReviewRating(
            tenant=performance_review_a.tenant, review=performance_review_a,
            criterion_label="Zero Weight", rating_value=Decimal("3.00"), weight=Decimal("0"))
        rr.clean()  # must not raise
