"""Tests for HRM 3.19 Performance Review views: ReviewCycle CRUD + advance_phase workflow;
ReviewTemplate CRUD; PerformanceReview CRUD + submit/share/acknowledge/calibrate workflow;
ReviewRating nested create (equal-split weight default)/edit/delete; calibration_board sort.
Bounded-query guard on list views."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ ReviewCycle CRUD
class TestReviewCycleListView:
    def test_list_200(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_cycle_a.pk in pks

    def test_list_filter_by_status(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_cycle_a.pk in pks
        resp2 = client_a.get(reverse("hrm:reviewcycle_list"), {"status": "closed"})
        pks2 = [obj.pk for obj in resp2.context["object_list"]]
        assert review_cycle_a.pk not in pks2

    def test_list_filter_by_cycle_type(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_list"), {"cycle_type": "half_yearly"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_cycle_a.pk in pks

    def test_list_search_by_name(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_list"), {"q": "H1 2026"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_cycle_a.pk in pks

    def test_list_has_choices_context(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_list"))
        assert "status_choices" in resp.context
        assert "cycle_type_choices" in resp.context


class TestReviewCycleCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:reviewcycle_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a):
        from apps.hrm.models import ReviewCycle
        resp = client_a.post(reverse("hrm:reviewcycle_create"), {
            "name": "Q4 2026 Review", "cycle_type": "quarterly",
            "self_review_start": "", "self_review_end": "",
            "manager_review_start": "", "manager_review_end": "",
            "calibration_date": "", "results_release_date": "", "goal_period": "", "description": "",
        })
        assert resp.status_code == 302
        rc = ReviewCycle.objects.filter(tenant=tenant_a, name="Q4 2026 Review").first()
        assert rc is not None
        assert rc.tenant_id == tenant_a.pk
        assert rc.status == "draft"

    def test_post_invalid_self_review_end_before_start_rejected(self, client_a, tenant_a):
        from apps.hrm.models import ReviewCycle
        resp = client_a.post(reverse("hrm:reviewcycle_create"), {
            "name": "Bad Cycle", "cycle_type": "quarterly",
            "self_review_start": "2026-07-15", "self_review_end": "2026-07-01",
            "manager_review_start": "", "manager_review_end": "",
            "calibration_date": "", "results_release_date": "", "goal_period": "", "description": "",
        })
        assert not ReviewCycle.objects.filter(tenant=tenant_a, name="Bad Cycle").exists()

    def test_status_not_a_form_field(self, client_a):
        resp = client_a.get(reverse("hrm:reviewcycle_create"))
        assert "status" not in resp.context["form"].fields

    def test_goal_period_dropdown_scoped_to_tenant(self, client_a, goal_period_a, goal_period_b):
        resp = client_a.get(reverse("hrm:reviewcycle_create"))
        pks = list(resp.context["form"].fields["goal_period"].queryset.values_list("pk", flat=True))
        assert goal_period_a.pk in pks
        assert goal_period_b.pk not in pks


class TestReviewCycleDetailEditDelete:
    def test_detail_200(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_detail", args=[review_cycle_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_reviews_and_phase_counts(self, client_a, review_cycle_a, performance_review_a):
        resp = client_a.get(reverse("hrm:reviewcycle_detail", args=[review_cycle_a.pk]))
        assert "reviews" in resp.context
        assert "phase_counts" in resp.context
        pks = [r.pk for r in resp.context["reviews"]]
        assert performance_review_a.pk in pks
        assert resp.context["phase_counts"]["draft"] == 1

    def test_detail_admin_sees_all_reviews_in_roster(self, client_a, review_cycle_a, performance_review_a):
        """A tenant admin sees the full cycle roster — no confidentiality filter applied."""
        resp = client_a.get(reverse("hrm:reviewcycle_detail", args=[review_cycle_a.pk]))
        pks = [r.pk for r in resp.context["reviews"]]
        assert performance_review_a.pk in pks

    def test_detail_next_phase_label_for_draft_cycle(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_detail", args=[review_cycle_a.pk]))
        assert resp.context["next_phase_label"] == "Self-Assessment"

    def test_detail_next_phase_label_none_when_closed(self, client_a, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle.objects.create(tenant=tenant_a, name="Closed Cycle", status="closed")
        resp = client_a.get(reverse("hrm:reviewcycle_detail", args=[rc.pk]))
        assert resp.context["next_phase_label"] is None

    def test_edit_get_200(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_edit", args=[review_cycle_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_name(self, client_a, review_cycle_a):
        resp = client_a.post(reverse("hrm:reviewcycle_edit", args=[review_cycle_a.pk]), {
            "name": "H1 2026 Renamed", "cycle_type": "half_yearly",
            "self_review_start": "2026-07-01", "self_review_end": "2026-07-15",
            "manager_review_start": "2026-07-16", "manager_review_end": "2026-07-31",
            "calibration_date": "2026-08-05", "results_release_date": "2026-08-10",
            "goal_period": review_cycle_a.goal_period_id, "description": "",
        })
        assert resp.status_code == 302
        review_cycle_a.refresh_from_db()
        assert review_cycle_a.name == "H1 2026 Renamed"

    def test_edit_post_status_field_ignored(self, client_a, review_cycle_a):
        """ReviewCycleForm does NOT accept `status` — POSTing status=closed via the edit form must
        NOT change status (only @tenant_admin_required advance_phase may flip it)."""
        assert review_cycle_a.status == "draft"
        resp = client_a.post(reverse("hrm:reviewcycle_edit", args=[review_cycle_a.pk]), {
            "name": review_cycle_a.name, "cycle_type": "half_yearly",
            "self_review_start": "", "self_review_end": "",
            "manager_review_start": "", "manager_review_end": "",
            "calibration_date": "", "results_release_date": "", "goal_period": "", "description": "",
            "status": "closed",
        })
        assert resp.status_code == 302
        review_cycle_a.refresh_from_db()
        assert review_cycle_a.status == "draft"  # unchanged

    def test_delete_post_removes_when_no_reviews(self, client_a, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle.objects.create(tenant=tenant_a, name="Deletable Cycle")
        resp = client_a.post(reverse("hrm:reviewcycle_delete", args=[rc.pk]))
        assert resp.status_code == 302
        assert not ReviewCycle.objects.filter(pk=rc.pk).exists()

    def test_delete_blocked_when_has_reviews(self, client_a, review_cycle_a, performance_review_a):
        from apps.hrm.models import ReviewCycle
        client_a.post(reverse("hrm:reviewcycle_delete", args=[review_cycle_a.pk]))
        assert ReviewCycle.objects.filter(pk=review_cycle_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_delete", args=[review_cycle_a.pk]))
        assert resp.status_code == 405


class TestReviewCycleAdvancePhase:
    def test_advance_steps_exactly_one_phase(self, client_a, review_cycle_a):
        assert review_cycle_a.status == "draft"
        resp = client_a.post(reverse("hrm:reviewcycle_advance_phase", args=[review_cycle_a.pk]))
        assert resp.status_code == 302
        review_cycle_a.refresh_from_db()
        assert review_cycle_a.status == "self_assessment"

    def test_advance_steps_through_full_phase_order_one_at_a_time(self, client_a, review_cycle_a):
        from apps.hrm.models import ReviewCycle
        expected = list(ReviewCycle.PHASE_ORDER[1:])
        for phase in expected:
            client_a.post(reverse("hrm:reviewcycle_advance_phase", args=[review_cycle_a.pk]))
            review_cycle_a.refresh_from_db()
            assert review_cycle_a.status == phase

    def test_advance_guards_past_closed(self, client_a, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle.objects.create(tenant=tenant_a, name="Already Closed", status="closed")
        resp = client_a.post(reverse("hrm:reviewcycle_advance_phase", args=[rc.pk]))
        assert resp.status_code == 302
        rc.refresh_from_db()
        assert rc.status == "closed"  # unchanged, no crash past the end of PHASE_ORDER

    def test_advance_get_not_allowed(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:reviewcycle_advance_phase", args=[review_cycle_a.pk]))
        assert resp.status_code == 405


# ================================================================ ReviewTemplate CRUD
class TestReviewTemplateListView:
    def test_list_200(self, client_a, review_template_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, review_template_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_template_a.pk in pks

    def test_list_filter_by_review_type(self, client_a, review_template_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_list"), {"review_type": "manager"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_template_a.pk in pks

    def test_list_filter_by_is_active(self, client_a, review_template_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_list"), {"is_active": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_template_a.pk in pks
        resp2 = client_a.get(reverse("hrm:reviewtemplate_list"), {"is_active": "False"})
        pks2 = [obj.pk for obj in resp2.context["object_list"]]
        assert review_template_a.pk not in pks2

    def test_list_search_by_name(self, client_a, review_template_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_list"), {"q": review_template_a.name})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_template_a.pk in pks

    def test_list_has_choices_context(self, client_a, review_template_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_list"))
        assert "review_type_choices" in resp.context


class TestReviewTemplateCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a):
        from apps.hrm.models import ReviewTemplate
        resp = client_a.post(reverse("hrm:reviewtemplate_create"), {
            "name": "Peer Feedback Form", "review_type": "peer", "rating_scale_max": "5",
            "include_goals": "", "is_anonymous": "on", "description": "", "is_active": "on",
        })
        assert resp.status_code == 302
        rt = ReviewTemplate.objects.filter(tenant=tenant_a, name="Peer Feedback Form").first()
        assert rt is not None
        assert rt.tenant_id == tenant_a.pk
        assert rt.number.startswith("RVT-")
        assert rt.is_anonymous is True

    def test_post_invalid_rating_scale_max_out_of_range_rejected(self, client_a, tenant_a):
        from apps.hrm.models import ReviewTemplate
        resp = client_a.post(reverse("hrm:reviewtemplate_create"), {
            "name": "Bad Scale Template", "review_type": "self", "rating_scale_max": "20",
            "include_goals": "", "is_anonymous": "", "description": "", "is_active": "on",
        })
        assert resp.status_code == 200
        assert not ReviewTemplate.objects.filter(tenant=tenant_a, name="Bad Scale Template").exists()


class TestReviewTemplateDetailEditDelete:
    def test_detail_200(self, client_a, review_template_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_detail", args=[review_template_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200(self, client_a, review_template_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_edit", args=[review_template_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_name(self, client_a, review_template_a):
        resp = client_a.post(reverse("hrm:reviewtemplate_edit", args=[review_template_a.pk]), {
            "name": "Manager Review Form Renamed", "review_type": "manager", "rating_scale_max": "5",
            "include_goals": "on", "is_anonymous": "", "description": "", "is_active": "on",
        })
        assert resp.status_code == 302
        review_template_a.refresh_from_db()
        assert review_template_a.name == "Manager Review Form Renamed"

    def test_delete_post_removes(self, client_a, tenant_a):
        from apps.hrm.models import ReviewTemplate
        rt = ReviewTemplate.objects.create(tenant=tenant_a, name="Deletable Template")
        resp = client_a.post(reverse("hrm:reviewtemplate_delete", args=[rt.pk]))
        assert resp.status_code == 302
        assert not ReviewTemplate.objects.filter(pk=rt.pk).exists()

    def test_delete_succeeds_even_when_used_by_review_set_null(self, client_a, review_template_a, performance_review_a):
        """template is SET_NULL on PerformanceReview — deleting the template must succeed and leave
        the historical review's data intact, just losing the template link."""
        from apps.hrm.models import PerformanceReview, ReviewTemplate
        client_a.post(reverse("hrm:reviewtemplate_delete", args=[review_template_a.pk]))
        assert not ReviewTemplate.objects.filter(pk=review_template_a.pk).exists()
        performance_review_a.refresh_from_db()
        assert performance_review_a.template_id is None

    def test_delete_get_not_allowed(self, client_a, review_template_a):
        resp = client_a.get(reverse("hrm:reviewtemplate_delete", args=[review_template_a.pk]))
        assert resp.status_code == 405


# ================================================================ PerformanceReview CRUD
class TestPerformanceReviewListView:
    def test_list_200(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_list"))
        assert resp.status_code == 200

    def test_list_shows_own_as_admin(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks

    def test_list_filter_by_cycle(self, client_a, performance_review_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:performancereview_list"), {"cycle": review_cycle_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks

    def test_list_filter_by_review_type(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_list"), {"review_type": "manager"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks

    def test_list_filter_by_status(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks

    def test_list_filter_by_subject(self, client_a, performance_review_a, employee_a):
        resp = client_a.get(reverse("hrm:performancereview_list"), {"subject": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks

    def test_list_filter_by_reviewer(self, client_a, performance_review_a, employee_a2):
        resp = client_a.get(reverse("hrm:performancereview_list"), {"reviewer": employee_a2.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks

    def test_list_search_by_number(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_list"), {"q": performance_review_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks

    def test_list_has_choices_context(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_list"))
        assert "review_type_choices" in resp.context
        assert "status_choices" in resp.context
        assert "cycles" in resp.context
        assert "employees" in resp.context
        assert "is_admin" in resp.context

    def test_mine_filter_returns_true_for_admin_when_linked(
        self, client_a, admin_user, employee_a, performance_review_a
    ):
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        resp = client_a.get(reverse("hrm:performancereview_list"), {"mine": "1"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks
        assert resp.context["mine"] is True


class TestPerformanceReviewCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:performancereview_create"))
        assert resp.status_code == 200

    def test_post_creates_self_review_with_tenant(self, client_a, tenant_a, review_cycle_a, employee_a):
        from apps.hrm.models import PerformanceReview
        resp = client_a.post(reverse("hrm:performancereview_create"), {
            "cycle": review_cycle_a.pk, "template": "", "subject": employee_a.pk,
            "reviewer": employee_a.pk, "review_type": "self",
            "strengths": "", "improvements": "", "private_notes": "", "is_anonymous": "",
        })
        assert resp.status_code == 302
        pr = PerformanceReview.objects.filter(tenant=tenant_a, subject=employee_a, review_type="self").first()
        assert pr is not None
        assert pr.tenant_id == tenant_a.pk
        assert pr.number.startswith("RVW-")
        assert pr.status == "draft"

    def test_post_invalid_self_review_reviewer_mismatch_rejected(
        self, client_a, tenant_a, review_cycle_a, employee_a, employee_a2
    ):
        """The model's clean() self-review guard is enforced through full_clean() on ModelForm save."""
        from apps.hrm.models import PerformanceReview
        resp = client_a.post(reverse("hrm:performancereview_create"), {
            "cycle": review_cycle_a.pk, "template": "", "subject": employee_a.pk,
            "reviewer": employee_a2.pk, "review_type": "self",
            "strengths": "", "improvements": "", "private_notes": "", "is_anonymous": "",
        })
        assert resp.status_code == 200
        assert not PerformanceReview.objects.filter(
            tenant=tenant_a, subject=employee_a, reviewer=employee_a2, review_type="self").exists()

    def test_subject_and_reviewer_dropdowns_scoped_to_tenant(self, client_a, employee_a, employee_b):
        resp = client_a.get(reverse("hrm:performancereview_create"))
        subj_pks = list(resp.context["form"].fields["subject"].queryset.values_list("pk", flat=True))
        rev_pks = list(resp.context["form"].fields["reviewer"].queryset.values_list("pk", flat=True))
        assert employee_a.pk in subj_pks
        assert employee_b.pk not in subj_pks
        assert employee_a.pk in rev_pks
        assert employee_b.pk not in rev_pks

    def test_cycle_dropdown_scoped_to_tenant(self, client_a, review_cycle_a, review_cycle_b):
        resp = client_a.get(reverse("hrm:performancereview_create"))
        pks = list(resp.context["form"].fields["cycle"].queryset.values_list("pk", flat=True))
        assert review_cycle_a.pk in pks
        assert review_cycle_b.pk not in pks

    def test_template_dropdown_excludes_inactive(self, client_a, tenant_a, review_template_a):
        from apps.hrm.models import ReviewTemplate
        inactive = ReviewTemplate.objects.create(
            tenant=tenant_a, name="Retired Template", review_type="self", is_active=False)
        resp = client_a.get(reverse("hrm:performancereview_create"))
        pks = list(resp.context["form"].fields["template"].queryset.values_list("pk", flat=True))
        assert review_template_a.pk in pks
        assert inactive.pk not in pks

    def test_form_has_no_status_or_manager_rating_fields(self, client_a):
        resp = client_a.get(reverse("hrm:performancereview_create"))
        fields = resp.context["form"].fields
        assert "status" not in fields
        assert "manager_rating" not in fields
        assert "calibrated_rating" not in fields
        assert "potential_rating" not in fields


class TestPerformanceReviewDetailView:
    def test_detail_200_for_admin(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, performance_review_a, review_rating_a):
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert "obj" in resp.context
        assert "ratings" in resp.context
        assert "show_private" in resp.context
        assert "show_reviewer" in resp.context
        assert "is_subject" in resp.context
        assert "is_reviewer" in resp.context
        assert "can_edit" in resp.context
        assert "rating_form" in resp.context
        pks = [r.pk for r in resp.context["ratings"]]
        assert review_rating_a.pk in pks

    def test_admin_sees_private_notes(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.context["show_private"] is True
        assert b"Confidential: needs coaching on delegation." in resp.content

    def test_can_edit_true_for_admin_on_draft(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.context["can_edit"] is True

    def test_can_edit_false_once_not_draft(self, client_a, performance_review_a):
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.context["can_edit"] is False

    def test_goal_objectives_included_when_template_includes_goals(
        self, client_a, performance_review_a, objective_a
    ):
        """review_template_a.include_goals=True and its cycle is aligned to goal_period_a — the
        subject's Objective for that period surfaces in the goal-review section."""
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        pks = [o.pk for o in resp.context["goal_objectives"]]
        assert objective_a.pk in pks

    def test_goal_objectives_empty_when_template_excludes_goals(
        self, client_a, tenant_a, review_cycle_a, employee_a, objective_a
    ):
        from apps.hrm.models import PerformanceReview, ReviewTemplate
        no_goals_template = ReviewTemplate.objects.create(
            tenant=tenant_a, name="No Goals Template", review_type="self", include_goals=False)
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, template=no_goals_template,
            subject=employee_a, reviewer=employee_a, review_type="self")
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[pr.pk]))
        assert list(resp.context["goal_objectives"]) == []


class TestPerformanceReviewEditDelete:
    def test_edit_get_200_for_admin(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_edit", args=[performance_review_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_strengths(self, client_a, performance_review_a, review_cycle_a, employee_a, employee_a2):
        resp = client_a.post(reverse("hrm:performancereview_edit", args=[performance_review_a.pk]), {
            "cycle": review_cycle_a.pk, "template": performance_review_a.template_id,
            "subject": employee_a.pk, "reviewer": employee_a2.pk, "review_type": "manager",
            "strengths": "Great collaborator", "improvements": "", "private_notes": "",
            "is_anonymous": "",
        })
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.strengths == "Great collaborator"

    def test_delete_post_removes_as_admin(self, client_a, performance_review_a):
        from apps.hrm.models import PerformanceReview
        pk = performance_review_a.pk
        resp = client_a.post(reverse("hrm:performancereview_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PerformanceReview.objects.filter(pk=pk).exists()

    def test_delete_cascades_ratings(self, client_a, performance_review_a, review_rating_a):
        from apps.hrm.models import ReviewRating
        client_a.post(reverse("hrm:performancereview_delete", args=[performance_review_a.pk]))
        assert not ReviewRating.objects.filter(pk=review_rating_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_delete", args=[performance_review_a.pk]))
        assert resp.status_code == 405


# ================================================================ PerformanceReview workflow
class TestPerformanceReviewSubmit:
    def test_submit_draft_to_submitted_as_admin(self, client_a, performance_review_a):
        resp = client_a.post(reverse("hrm:performancereview_submit", args=[performance_review_a.pk]))
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "submitted"
        assert performance_review_a.submitted_at is not None

    def test_submit_snapshots_manager_rating_on_manager_review(
        self, client_a, performance_review_a, review_rating_a
    ):
        """A manager review with no manager_rating yet snapshots overall_rating on submit."""
        assert performance_review_a.review_type == "manager"
        assert performance_review_a.manager_rating is None
        client_a.post(reverse("hrm:performancereview_submit", args=[performance_review_a.pk]))
        performance_review_a.refresh_from_db()
        assert performance_review_a.manager_rating == review_rating_a.rating_value

    def test_submit_does_not_overwrite_existing_manager_rating(self, client_a, performance_review_a, review_rating_a):
        performance_review_a.manager_rating = Decimal("1.00")
        performance_review_a.save(update_fields=["manager_rating"])
        client_a.post(reverse("hrm:performancereview_submit", args=[performance_review_a.pk]))
        performance_review_a.refresh_from_db()
        assert performance_review_a.manager_rating == Decimal("1.00")

    def test_submit_does_not_snapshot_on_non_manager_review(self, client_a, tenant_a, review_cycle_a, employee_a):
        from apps.hrm.models import PerformanceReview
        pr = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a,
            review_type="self")
        client_a.post(reverse("hrm:performancereview_submit", args=[pr.pk]))
        pr.refresh_from_db()
        assert pr.manager_rating is None

    def test_submit_blocked_when_not_draft(self, client_a, performance_review_a):
        performance_review_a.status = "submitted"
        performance_review_a.submitted_at = None
        performance_review_a.save(update_fields=["status", "submitted_at"])
        client_a.post(reverse("hrm:performancereview_submit", args=[performance_review_a.pk]))
        performance_review_a.refresh_from_db()
        assert performance_review_a.submitted_at is None  # unchanged, no double-submit

    def test_submit_get_not_allowed(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_submit", args=[performance_review_a.pk]))
        assert resp.status_code == 405


class TestPerformanceReviewShare:
    def test_share_submitted_to_shared_as_admin(self, client_a, performance_review_a):
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:performancereview_share", args=[performance_review_a.pk]))
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "shared"
        assert performance_review_a.shared_at is not None

    def test_share_blocked_when_not_submitted(self, client_a, performance_review_a):
        assert performance_review_a.status == "draft"
        client_a.post(reverse("hrm:performancereview_share", args=[performance_review_a.pk]))
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "draft"  # unchanged

    def test_share_get_not_allowed(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_share", args=[performance_review_a.pk]))
        assert resp.status_code == 405


class TestPerformanceReviewAcknowledge:
    def test_acknowledge_shared_to_acknowledged_by_subject(
        self, client_a, admin_user, employee_a, performance_review_a
    ):
        """The subject-only gate resolves via request.user.party -> EmployeeProfile."""
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        performance_review_a.status = "shared"
        performance_review_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:performancereview_acknowledge", args=[performance_review_a.pk]))
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "acknowledged"
        assert performance_review_a.acknowledged_at is not None
        assert performance_review_a.acknowledged_by_id == employee_a.pk

    def test_acknowledge_forbidden_for_non_subject(self, client_a, performance_review_a):
        """The logged-in admin has no linked party (not the subject) — 403, not silently ignored."""
        performance_review_a.status = "shared"
        performance_review_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:performancereview_acknowledge", args=[performance_review_a.pk]))
        assert resp.status_code == 403
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "shared"

    def test_acknowledge_blocked_when_not_shared(self, client_a, admin_user, employee_a, performance_review_a):
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        assert performance_review_a.status == "draft"
        client_a.post(reverse("hrm:performancereview_acknowledge", args=[performance_review_a.pk]))
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "draft"  # unchanged

    def test_acknowledge_get_not_allowed(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_acknowledge", args=[performance_review_a.pk]))
        assert resp.status_code == 405


class TestPerformanceReviewCalibrate:
    def test_calibrate_get_200_as_admin(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_calibrate", args=[performance_review_a.pk]))
        assert resp.status_code == 200

    def test_calibrate_post_writes_calibrated_rating(self, client_a, performance_review_a):
        resp = client_a.post(reverse("hrm:performancereview_calibrate", args=[performance_review_a.pk]), {
            "calibrated_rating": "3.50", "potential_rating": "2.00", "calibration_notes": "Adjusted down.",
        })
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.calibrated_rating == Decimal("3.50")
        assert performance_review_a.potential_rating == Decimal("2.00")
        assert performance_review_a.calibration_notes == "Adjusted down."

    def test_calibrate_form_only_exposes_calibration_fields(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_calibrate", args=[performance_review_a.pk]))
        fields = set(resp.context["form"].fields.keys())
        assert fields == {"calibrated_rating", "potential_rating", "calibration_notes"}


# ================================================================ calibration_board
class TestCalibrationBoard:
    def test_200(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:calibration_board"))
        assert resp.status_code == 200

    def test_defaults_to_most_recent_cycle(self, client_a, review_cycle_a):
        resp = client_a.get(reverse("hrm:calibration_board"))
        assert resp.context["cycle"].pk == review_cycle_a.pk

    def test_cycle_selectable_via_query_param(self, client_a, tenant_a, review_cycle_a):
        from apps.hrm.models import ReviewCycle
        other = ReviewCycle.objects.create(tenant=tenant_a, name="Other Cycle")
        resp = client_a.get(reverse("hrm:calibration_board"), {"cycle": other.pk})
        assert resp.context["cycle"].pk == other.pk

    def test_only_includes_manager_reviews(self, client_a, tenant_a, review_cycle_a, employee_a, employee_a2):
        from apps.hrm.models import PerformanceReview
        self_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a,
            review_type="self")
        manager_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="manager")
        resp = client_a.get(reverse("hrm:calibration_board"))
        pks = [r.pk for r in resp.context["reviews"]]
        assert manager_review.pk in pks
        assert self_review.pk not in pks

    def test_sorts_by_effective_rating_descending(self, client_a, tenant_a, review_cycle_a, employee_a, employee_a2):
        """Two manager reviews, ratings 2.00 and 4.00 -> the higher-rated one comes first."""
        from apps.core.models import Employment, Party
        from apps.hrm.models import EmployeeProfile, PerformanceReview, ReviewRating
        low_party = Party.objects.create(tenant=tenant_a, kind="person", name="Low Scorer")
        low_employment = Employment.objects.create(
            tenant=tenant_a, party=low_party, job_title="Staff", status="active")
        low_subject = EmployeeProfile.objects.create(
            tenant=tenant_a, party=low_party, employment=low_employment, employee_type="full_time")
        low_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=low_subject, reviewer=employee_a2,
            review_type="manager")
        ReviewRating.objects.create(
            tenant=tenant_a, review=low_review, criterion_label="C1",
            rating_value=Decimal("2.00"), weight=Decimal("100"))

        high_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="manager")
        ReviewRating.objects.create(
            tenant=tenant_a, review=high_review, criterion_label="C1",
            rating_value=Decimal("4.00"), weight=Decimal("100"))

        resp = client_a.get(reverse("hrm:calibration_board"))
        pks_in_order = [r.pk for r in resp.context["reviews"]]
        assert pks_in_order.index(high_review.pk) < pks_in_order.index(low_review.pk)

    def test_unrated_reviews_sort_last(self, client_a, tenant_a, review_cycle_a, employee_a, employee_a2):
        from apps.hrm.models import PerformanceReview, ReviewRating
        rated = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="manager")
        ReviewRating.objects.create(
            tenant=tenant_a, review=rated, criterion_label="C1",
            rating_value=Decimal("1.00"), weight=Decimal("100"))
        unrated = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a2, reviewer=employee_a,
            review_type="manager")
        resp = client_a.get(reverse("hrm:calibration_board"))
        pks_in_order = [r.pk for r in resp.context["reviews"]]
        assert pks_in_order.index(rated.pk) < pks_in_order.index(unrated.pk)


# ================================================================ ReviewRating nested create/edit/delete
class TestReviewRatingCreateView:
    def test_get_200(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]))
        assert resp.status_code == 200

    def test_default_weight_equal_split_with_no_siblings(self, client_a, performance_review_a):
        """No existing ratings -> default weight = 100/(0+1) = 100.00."""
        resp = client_a.get(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]))
        assert resp.context["form"].initial["weight"] == Decimal("100.00")

    def test_default_weight_equal_split_with_one_sibling(self, client_a, performance_review_a, review_rating_a):
        """One existing rating -> default weight = 100/(1+1) = 50.00 for the new one."""
        resp = client_a.get(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]))
        assert resp.context["form"].initial["weight"] == Decimal("50.00")

    def test_default_weight_equal_split_with_two_siblings(self, client_a, tenant_a, performance_review_a, review_rating_a):
        from apps.hrm.models import ReviewRating
        ReviewRating.objects.create(
            tenant=tenant_a, review=performance_review_a, criterion_label="C2",
            rating_value=Decimal("3.00"))
        resp = client_a.get(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]))
        assert resp.context["form"].initial["weight"] == Decimal("33.33")

    def test_post_creates_with_tenant_and_review_from_url(self, client_a, tenant_a, performance_review_a):
        from apps.hrm.models import ReviewRating
        resp = client_a.post(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]), {
            "criterion_label": "Teamwork", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "50", "comment": "",
        })
        assert resp.status_code == 302
        rating = ReviewRating.objects.filter(tenant=tenant_a, criterion_label="Teamwork").first()
        assert rating is not None
        assert rating.review_id == performance_review_a.pk
        assert rating.tenant_id == tenant_a.pk
        assert rating.number.startswith("RVR-")

    def test_post_redirects_to_review_detail(self, client_a, performance_review_a):
        resp = client_a.post(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]), {
            "criterion_label": "Teamwork", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "50", "comment": "",
        })
        assert reverse("hrm:performancereview_detail", args=[performance_review_a.pk]) in resp["Location"]

    def test_post_invalid_rating_above_scale_max_rejected(self, client_a, tenant_a, performance_review_a):
        from apps.hrm.models import ReviewRating
        resp = client_a.post(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]), {
            "criterion_label": "Too High", "criterion_category": "competency",
            "rating_value": "99.00", "weight": "50", "comment": "",
        })
        assert resp.status_code == 200
        assert not ReviewRating.objects.filter(tenant=tenant_a, criterion_label="Too High").exists()

    def test_blocked_once_review_not_draft(self, client_a, tenant_a, performance_review_a):
        """reviewrating_create is gated by _can_edit_review — a non-draft review rejects the POST
        (redirect, no mutation) even for the reviewer/admin."""
        from apps.hrm.models import ReviewRating
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]), {
            "criterion_label": "Blocked", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "50", "comment": "",
        })
        assert resp.status_code == 302
        assert not ReviewRating.objects.filter(review=performance_review_a, criterion_label="Blocked").exists()


class TestReviewRatingDetailEditDelete:
    def test_detail_200_for_admin(self, client_a, review_rating_a):
        resp = client_a.get(reverse("hrm:reviewrating_detail", args=[review_rating_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200(self, client_a, review_rating_a):
        resp = client_a.get(reverse("hrm:reviewrating_edit", args=[review_rating_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_criterion_label(self, client_a, review_rating_a):
        resp = client_a.post(reverse("hrm:reviewrating_edit", args=[review_rating_a.pk]), {
            "criterion_label": "Communication Renamed", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "100", "comment": "",
        })
        assert resp.status_code == 302
        review_rating_a.refresh_from_db()
        assert review_rating_a.criterion_label == "Communication Renamed"

    def test_edit_blocked_once_review_not_draft(self, client_a, performance_review_a, review_rating_a):
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:reviewrating_edit", args=[review_rating_a.pk]), {
            "criterion_label": "Should Not Apply", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "100", "comment": "",
        })
        review_rating_a.refresh_from_db()
        assert review_rating_a.criterion_label != "Should Not Apply"

    def test_delete_post_removes(self, client_a, review_rating_a):
        from apps.hrm.models import ReviewRating
        pk = review_rating_a.pk
        resp = client_a.post(reverse("hrm:reviewrating_delete", args=[pk]))
        assert resp.status_code == 302
        assert not ReviewRating.objects.filter(pk=pk).exists()

    def test_delete_redirects_to_review_detail(self, client_a, performance_review_a, review_rating_a):
        resp = client_a.post(reverse("hrm:reviewrating_delete", args=[review_rating_a.pk]))
        assert reverse("hrm:performancereview_detail", args=[performance_review_a.pk]) in resp["Location"]

    def test_delete_blocked_once_review_not_draft(self, client_a, performance_review_a, review_rating_a):
        from apps.hrm.models import ReviewRating
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:reviewrating_delete", args=[review_rating_a.pk]))
        assert ReviewRating.objects.filter(pk=review_rating_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, review_rating_a):
        resp = client_a.get(reverse("hrm:reviewrating_delete", args=[review_rating_a.pk]))
        assert resp.status_code == 405


# ================================================================ Bounded queries (N+1 guard)
class TestReviewsQueryCount:
    def test_performancereview_list_bounded_queries_flat(
        self, client_a, tenant_a, review_cycle_a, django_assert_max_num_queries
    ):
        """The review list must not grow per-row — create several reviews each with multiple
        ratings and assert the query count stays flat (overall_rating/effective_rating/
        reviewer_anonymized must use prefetched ratings, not re-query)."""
        from apps.core.models import Employment, Party
        from apps.hrm.models import EmployeeProfile, PerformanceReview, ReviewRating
        for i in range(5):
            party = Party.objects.create(tenant=tenant_a, kind="person", name=f"Subject {i}")
            employment = Employment.objects.create(
                tenant=tenant_a, party=party, job_title="Staff", status="active")
            subject = EmployeeProfile.objects.create(
                tenant=tenant_a, party=party, employment=employment, employee_type="full_time")
            reviewer_party = Party.objects.create(tenant=tenant_a, kind="person", name=f"Reviewer {i}")
            reviewer_employment = Employment.objects.create(
                tenant=tenant_a, party=reviewer_party, job_title="Manager", status="active")
            reviewer = EmployeeProfile.objects.create(
                tenant=tenant_a, party=reviewer_party, employment=reviewer_employment, employee_type="full_time")
            review = PerformanceReview.objects.create(
                tenant=tenant_a, cycle=review_cycle_a, subject=subject, reviewer=reviewer,
                review_type="manager", status="draft")
            for j in range(2):
                ReviewRating.objects.create(
                    tenant=tenant_a, review=review, criterion_label=f"C{i}-{j}",
                    rating_value=Decimal("3.00"), weight=Decimal("50"))
        with django_assert_max_num_queries(20):
            client_a.get(reverse("hrm:performancereview_list"))

    def test_reviewcycle_list_bounded_queries_flat(
        self, client_a, tenant_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import ReviewCycle
        for i in range(5):
            ReviewCycle.objects.create(tenant=tenant_a, name=f"Cycle {i}")
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:reviewcycle_list"))

    def test_reviewtemplate_list_bounded_queries_flat(
        self, client_a, tenant_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import ReviewTemplate
        for i in range(5):
            ReviewTemplate.objects.create(tenant=tenant_a, name=f"Template {i}")
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:reviewtemplate_list"))
