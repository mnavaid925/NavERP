"""Tests for HRM 3.18 Goal Setting views: GoalPeriod CRUD + activate/close workflow; Objective
CRUD + tree + ?mine=1 filter; KeyResult nested create (equal-split weight default)/edit/delete;
GoalCheckIn nested create (advances current_value, sets created_by)/list/detail/delete. Bounded-query
guard on list views."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ GoalPeriod CRUD
class TestGoalPeriodListView:
    def test_list_200(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_period_a.pk in pks

    def test_list_filter_by_status(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_list"), {"status": "active"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_period_a.pk in pks
        resp2 = client_a.get(reverse("hrm:goalperiod_list"), {"status": "closed"})
        pks2 = [obj.pk for obj in resp2.context["object_list"]]
        assert goal_period_a.pk not in pks2

    def test_list_filter_by_period_type(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_list"), {"period_type": "quarterly"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_period_a.pk in pks

    def test_list_search_by_name(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_list"), {"q": "Q3 2026"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_period_a.pk in pks

    def test_list_has_choices_context(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_list"))
        assert "status_choices" in resp.context
        assert "period_type_choices" in resp.context


class TestGoalPeriodCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:goalperiod_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a):
        from apps.hrm.models import GoalPeriod
        resp = client_a.post(reverse("hrm:goalperiod_create"), {
            "name": "Q4 2026", "period_type": "quarterly",
            "start_date": "2026-10-01", "end_date": "2026-12-31", "description": "",
        })
        assert resp.status_code == 302
        gp = GoalPeriod.objects.filter(tenant=tenant_a, name="Q4 2026").first()
        assert gp is not None
        assert gp.tenant_id == tenant_a.pk
        assert gp.status == "draft"

    def test_post_invalid_end_before_start_rejected(self, client_a, tenant_a):
        """The model's clean() end<=start guard is enforced through full_clean() on ModelForm save."""
        from apps.hrm.models import GoalPeriod
        resp = client_a.post(reverse("hrm:goalperiod_create"), {
            "name": "Bad Period", "period_type": "quarterly",
            "start_date": "2026-10-31", "end_date": "2026-10-01", "description": "",
        })
        assert not GoalPeriod.objects.filter(tenant=tenant_a, name="Bad Period").exists()


class TestGoalPeriodDetailEditDelete:
    def test_detail_200(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_detail", args=[goal_period_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_objectives(self, client_a, goal_period_a, objective_a):
        resp = client_a.get(reverse("hrm:goalperiod_detail", args=[goal_period_a.pk]))
        assert "objectives" in resp.context
        pks = [o.pk for o in resp.context["objectives"]]
        assert objective_a.pk in pks

    def test_edit_get_200(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_edit", args=[goal_period_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_name(self, client_a, goal_period_a):
        resp = client_a.post(reverse("hrm:goalperiod_edit", args=[goal_period_a.pk]), {
            "name": "Q3 2026 Renamed", "period_type": "quarterly",
            "start_date": "2026-07-01", "end_date": "2026-09-30", "description": "",
        })
        assert resp.status_code == 302
        goal_period_a.refresh_from_db()
        assert goal_period_a.name == "Q3 2026 Renamed"

    def test_edit_post_status_field_ignored_authz_fix(self, client_a, goal_period_a):
        """GoalPeriodForm does NOT accept `status` — POSTing status=closed via the edit form must NOT
        change status (the authz fix; only @tenant_admin_required activate/close may flip it)."""
        assert goal_period_a.status == "active"
        resp = client_a.post(reverse("hrm:goalperiod_edit", args=[goal_period_a.pk]), {
            "name": goal_period_a.name, "period_type": "quarterly",
            "start_date": "2026-07-01", "end_date": "2026-09-30", "description": "",
            "status": "closed",
        })
        assert resp.status_code == 302
        goal_period_a.refresh_from_db()
        assert goal_period_a.status == "active"  # unchanged

    def test_status_not_a_form_field(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_edit", args=[goal_period_a.pk]))
        assert "status" not in resp.context["form"].fields

    def test_delete_post_removes_when_no_objectives(self, client_a, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="Deletable", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        resp = client_a.post(reverse("hrm:goalperiod_delete", args=[gp.pk]))
        assert resp.status_code == 302
        assert not GoalPeriod.objects.filter(pk=gp.pk).exists()

    def test_delete_blocked_when_has_objectives(self, client_a, goal_period_a, objective_a):
        from apps.hrm.models import GoalPeriod
        resp = client_a.post(reverse("hrm:goalperiod_delete", args=[goal_period_a.pk]))
        assert GoalPeriod.objects.filter(pk=goal_period_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_delete", args=[goal_period_a.pk]))
        assert resp.status_code == 405


class TestGoalPeriodActivateClose:
    def test_activate_draft_to_active(self, client_a, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="Draft Period", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31), status="draft",
        )
        resp = client_a.post(reverse("hrm:goalperiod_activate", args=[gp.pk]))
        assert resp.status_code == 302
        gp.refresh_from_db()
        assert gp.status == "active"

    def test_activate_closed_to_active(self, client_a, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="Closed Period", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31), status="closed",
        )
        resp = client_a.post(reverse("hrm:goalperiod_activate", args=[gp.pk]))
        gp.refresh_from_db()
        assert gp.status == "active"

    def test_activate_blocked_when_already_active(self, client_a, goal_period_a):
        client_a.post(reverse("hrm:goalperiod_activate", args=[goal_period_a.pk]))
        goal_period_a.refresh_from_db()
        assert goal_period_a.status == "active"  # unchanged, no crash

    def test_close_active_to_closed(self, client_a, goal_period_a):
        resp = client_a.post(reverse("hrm:goalperiod_close", args=[goal_period_a.pk]))
        assert resp.status_code == 302
        goal_period_a.refresh_from_db()
        assert goal_period_a.status == "closed"

    def test_close_blocked_when_not_active(self, client_a, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="Draft Period 2", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31), status="draft",
        )
        client_a.post(reverse("hrm:goalperiod_close", args=[gp.pk]))
        gp.refresh_from_db()
        assert gp.status == "draft"  # unchanged

    def test_activate_get_not_allowed(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_activate", args=[goal_period_a.pk]))
        assert resp.status_code == 405

    def test_close_get_not_allowed(self, client_a, goal_period_a):
        resp = client_a.get(reverse("hrm:goalperiod_close", args=[goal_period_a.pk]))
        assert resp.status_code == 405


# ================================================================ Objective CRUD
class TestObjectiveListView:
    def test_list_200(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert objective_a.pk in pks

    def test_list_filter_by_status(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_list"), {"status": "active"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert objective_a.pk in pks

    def test_list_filter_by_scope(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_list"), {"scope": "individual"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert objective_a.pk in pks

    def test_list_filter_by_goal_period(self, client_a, objective_a, goal_period_a):
        resp = client_a.get(reverse("hrm:objective_list"), {"goal_period": goal_period_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert objective_a.pk in pks

    def test_list_filter_by_owner(self, client_a, objective_a, employee_a):
        resp = client_a.get(reverse("hrm:objective_list"), {"owner": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert objective_a.pk in pks

    def test_list_search_by_title(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_list"), {"q": objective_a.title})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert objective_a.pk in pks

    def test_list_has_choices_context(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_list"))
        assert "status_choices" in resp.context
        assert "scope_choices" in resp.context
        assert "target_type_choices" in resp.context
        assert "goal_periods" in resp.context
        assert "employees" in resp.context
        assert "departments" in resp.context

    def test_mine_filter_returns_owned_objectives(self, client_a, objective_a, employee_a, admin_user, tenant_a):
        """?mine=1 with an EmployeeProfile linked via request.user.party returns the user's own +
        direct-reports' objectives."""
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        resp = client_a.get(reverse("hrm:objective_list"), {"mine": "1"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert objective_a.pk in pks
        assert resp.context["mine"] is True

    def test_mine_filter_returns_none_when_no_employee_profile(self, client_a, objective_a, admin_user):
        """A logged-in user with NO linked EmployeeProfile (admin_user.party is None by default)
        gets qs.none() for ?mine=1 — never crashes, never leaks every objective."""
        assert admin_user.party_id is None
        resp = client_a.get(reverse("hrm:objective_list"), {"mine": "1"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pks == []


class TestObjectiveTreeView:
    def test_tree_200(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_tree"))
        assert resp.status_code == 200

    def test_tree_shows_top_level_objectives(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_tree"))
        pks = [o.pk for o in resp.context["objectives"]]
        assert objective_a.pk in pks

    def test_tree_excludes_child_objectives_from_top_level(
        self, client_a, tenant_a, objective_a, employee_a, goal_period_a
    ):
        from apps.hrm.models import Objective
        child = Objective.objects.create(
            tenant=tenant_a, title="Child Objective", owner=employee_a, goal_period=goal_period_a,
            parent_objective=objective_a,
        )
        resp = client_a.get(reverse("hrm:objective_tree"))
        pks = [o.pk for o in resp.context["objectives"]]
        assert objective_a.pk in pks
        assert child.pk not in pks

    def test_tree_filter_by_goal_period(self, client_a, objective_a, goal_period_a):
        resp = client_a.get(reverse("hrm:objective_tree"), {"goal_period": goal_period_a.pk})
        pks = [o.pk for o in resp.context["objectives"]]
        assert objective_a.pk in pks

    def test_tree_has_goal_periods_context(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_tree"))
        assert "goal_periods" in resp.context
        assert "tree_max_depth" in resp.context


class TestObjectiveCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:objective_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a, employee_a, goal_period_a):
        from apps.hrm.models import Objective
        resp = client_a.post(reverse("hrm:objective_create"), {
            "title": "New Objective", "description": "", "owner": employee_a.pk,
            "goal_period": goal_period_a.pk, "scope": "individual", "target_type": "committed",
            "weight": "100", "status": "draft",
        })
        assert resp.status_code == 302
        obj = Objective.objects.filter(tenant=tenant_a, title="New Objective").first()
        assert obj is not None
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("OBJ-")

    def test_owner_dropdown_scoped_to_tenant(self, client_a, employee_a, employee_b):
        resp = client_a.get(reverse("hrm:objective_create"))
        pks = list(resp.context["form"].fields["owner"].queryset.values_list("pk", flat=True))
        assert employee_a.pk in pks
        assert employee_b.pk not in pks

    def test_goal_period_dropdown_scoped_to_tenant(self, client_a, goal_period_a, goal_period_b):
        resp = client_a.get(reverse("hrm:objective_create"))
        pks = list(resp.context["form"].fields["goal_period"].queryset.values_list("pk", flat=True))
        assert goal_period_a.pk in pks
        assert goal_period_b.pk not in pks


class TestObjectiveDetailEditDelete:
    def test_detail_200(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_detail", args=[objective_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, objective_a, key_result_a):
        resp = client_a.get(reverse("hrm:objective_detail", args=[objective_a.pk]))
        assert "obj" in resp.context
        assert "key_results" in resp.context
        assert "child_objectives" in resp.context
        assert "recent_checkins" in resp.context
        assert "kr_form" in resp.context
        pks = [kr.pk for kr in resp.context["key_results"]]
        assert key_result_a.pk in pks

    def test_edit_get_200(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_edit", args=[objective_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_title(self, client_a, objective_a, employee_a, goal_period_a):
        resp = client_a.post(reverse("hrm:objective_edit", args=[objective_a.pk]), {
            "title": "Renamed Objective", "description": "", "owner": employee_a.pk,
            "goal_period": goal_period_a.pk, "scope": "individual", "target_type": "committed",
            "weight": "100", "status": "active",
        })
        assert resp.status_code == 302
        objective_a.refresh_from_db()
        assert objective_a.title == "Renamed Objective"

    def test_parent_objective_dropdown_excludes_self(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_edit", args=[objective_a.pk]))
        pks = list(resp.context["form"].fields["parent_objective"].queryset.values_list("pk", flat=True))
        assert objective_a.pk not in pks

    def test_delete_post_removes(self, client_a, objective_a):
        from apps.hrm.models import Objective
        pk = objective_a.pk
        resp = client_a.post(reverse("hrm:objective_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Objective.objects.filter(pk=pk).exists()

    def test_delete_cascades_key_results(self, client_a, objective_a, key_result_a):
        from apps.hrm.models import KeyResult
        client_a.post(reverse("hrm:objective_delete", args=[objective_a.pk]))
        assert not KeyResult.objects.filter(pk=key_result_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:objective_delete", args=[objective_a.pk]))
        assert resp.status_code == 405


# ================================================================ KeyResult nested create/edit/delete
class TestKeyResultCreateView:
    def test_get_200(self, client_a, objective_a):
        resp = client_a.get(reverse("hrm:keyresult_create", args=[objective_a.pk]))
        assert resp.status_code == 200

    def test_default_weight_equal_split_with_no_siblings(self, client_a, objective_a):
        """No existing KRs -> default weight = 100/(0+1) = 100.00."""
        resp = client_a.get(reverse("hrm:keyresult_create", args=[objective_a.pk]))
        assert resp.context["form"].initial["weight"] == Decimal("100.00")

    def test_default_weight_equal_split_with_one_sibling(self, client_a, objective_a, key_result_a):
        """One existing KR -> default weight = 100/(1+1) = 50.00 for the new one."""
        resp = client_a.get(reverse("hrm:keyresult_create", args=[objective_a.pk]))
        assert resp.context["form"].initial["weight"] == Decimal("50.00")

    def test_default_weight_equal_split_with_two_siblings(
        self, client_a, tenant_a, objective_a, key_result_a
    ):
        """Two existing KRs -> default weight = 100/(2+1) = 33.33 for the new one."""
        from apps.hrm.models import KeyResult
        KeyResult.objects.create(
            tenant=tenant_a, objective=objective_a, title="KR2", metric_type="numeric",
            target_value=Decimal("100"),
        )
        resp = client_a.get(reverse("hrm:keyresult_create", args=[objective_a.pk]))
        assert resp.context["form"].initial["weight"] == Decimal("33.33")

    def test_post_creates_with_tenant_and_objective_from_url(self, client_a, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        resp = client_a.post(reverse("hrm:keyresult_create", args=[objective_a.pk]), {
            "title": "New KR", "metric_type": "numeric", "start_value": "0",
            "target_value": "100", "current_value": "0", "weight": "50", "status": "not_started",
        })
        assert resp.status_code == 302
        kr = KeyResult.objects.filter(tenant=tenant_a, title="New KR").first()
        assert kr is not None
        assert kr.objective_id == objective_a.pk
        assert kr.tenant_id == tenant_a.pk
        assert kr.number.startswith("KR-")

    def test_post_redirects_to_objective_detail(self, client_a, objective_a):
        resp = client_a.post(reverse("hrm:keyresult_create", args=[objective_a.pk]), {
            "title": "New KR", "metric_type": "numeric", "start_value": "0",
            "target_value": "100", "current_value": "0", "weight": "50", "status": "not_started",
        })
        assert reverse("hrm:objective_detail", args=[objective_a.pk]) in resp["Location"]

    def test_post_invalid_metric_type_missing_target_value_rejected(self, client_a, tenant_a, objective_a):
        from apps.hrm.models import KeyResult
        resp = client_a.post(reverse("hrm:keyresult_create", args=[objective_a.pk]), {
            "title": "Bad KR", "metric_type": "numeric", "start_value": "0",
            "target_value": "", "current_value": "0", "weight": "50", "status": "not_started",
        })
        assert resp.status_code == 200
        assert not KeyResult.objects.filter(tenant=tenant_a, title="Bad KR").exists()


class TestKeyResultDetailEditDelete:
    def test_detail_200(self, client_a, key_result_a):
        resp = client_a.get(reverse("hrm:keyresult_detail", args=[key_result_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, key_result_a, goal_checkin_a):
        resp = client_a.get(reverse("hrm:keyresult_detail", args=[key_result_a.pk]))
        assert "obj" in resp.context
        assert "objective" in resp.context
        assert "checkins" in resp.context
        assert "checkin_form" in resp.context
        pks = [c.pk for c in resp.context["checkins"]]
        assert goal_checkin_a.pk in pks

    def test_edit_get_200(self, client_a, key_result_a):
        resp = client_a.get(reverse("hrm:keyresult_edit", args=[key_result_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_title(self, client_a, key_result_a):
        resp = client_a.post(reverse("hrm:keyresult_edit", args=[key_result_a.pk]), {
            "title": "Renamed KR", "metric_type": "numeric", "start_value": "0",
            "target_value": "100", "current_value": "60", "weight": "70", "status": "in_progress",
        })
        assert resp.status_code == 302
        key_result_a.refresh_from_db()
        assert key_result_a.title == "Renamed KR"

    def test_edit_redirects_to_objective_detail(self, client_a, key_result_a, objective_a):
        resp = client_a.post(reverse("hrm:keyresult_edit", args=[key_result_a.pk]), {
            "title": "Renamed KR", "metric_type": "numeric", "start_value": "0",
            "target_value": "100", "current_value": "60", "weight": "70", "status": "in_progress",
        })
        assert reverse("hrm:objective_detail", args=[objective_a.pk]) in resp["Location"]

    def test_delete_post_removes(self, client_a, key_result_a):
        from apps.hrm.models import KeyResult
        pk = key_result_a.pk
        resp = client_a.post(reverse("hrm:keyresult_delete", args=[pk]))
        assert resp.status_code == 302
        assert not KeyResult.objects.filter(pk=pk).exists()

    def test_delete_redirects_to_objective_detail(self, client_a, key_result_a, objective_a):
        resp = client_a.post(reverse("hrm:keyresult_delete", args=[key_result_a.pk]))
        assert reverse("hrm:objective_detail", args=[objective_a.pk]) in resp["Location"]

    def test_delete_get_not_allowed(self, client_a, key_result_a):
        resp = client_a.get(reverse("hrm:keyresult_delete", args=[key_result_a.pk]))
        assert resp.status_code == 405


# ================================================================ GoalCheckIn nested create/list/detail/delete
class TestGoalCheckInCreateView:
    def test_get_200(self, client_a, key_result_a):
        resp = client_a.get(reverse("hrm:goalcheckin_create", args=[key_result_a.pk]))
        assert resp.status_code == 200

    def test_post_creates_with_tenant_and_key_result_from_url(self, client_a, tenant_a, key_result_a):
        from apps.hrm.models import GoalCheckIn
        resp = client_a.post(reverse("hrm:goalcheckin_create", args=[key_result_a.pk]), {
            "checkin_date": "2026-07-25", "value_at_checkin": "75", "confidence": "on_track",
            "comment": "Making good progress",
        })
        assert resp.status_code == 302
        checkin = GoalCheckIn.objects.filter(tenant=tenant_a, key_result=key_result_a).latest("created_at")
        assert checkin.key_result_id == key_result_a.pk
        assert checkin.tenant_id == tenant_a.pk
        assert checkin.number.startswith("GCI-")

    def test_post_sets_created_by_from_logged_in_user_employee_profile(
        self, client_a, admin_user, employee_a, key_result_a
    ):
        """created_by resolves via request.user.party -> employee_profile (the admin's linked
        EmployeeProfile), not just any employee."""
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        from apps.hrm.models import GoalCheckIn
        client_a.post(reverse("hrm:goalcheckin_create", args=[key_result_a.pk]), {
            "checkin_date": "2026-07-25", "value_at_checkin": "80", "confidence": "on_track",
            "comment": "",
        })
        checkin = GoalCheckIn.objects.filter(key_result=key_result_a).latest("created_at")
        assert checkin.created_by_id == employee_a.pk

    def test_post_created_by_none_when_user_has_no_employee_profile(self, client_a, admin_user, key_result_a):
        """The logged-in tenant admin has no linked party/EmployeeProfile by default -> created_by
        is None (SET_NULL), not a crash."""
        assert admin_user.party_id is None
        from apps.hrm.models import GoalCheckIn
        client_a.post(reverse("hrm:goalcheckin_create", args=[key_result_a.pk]), {
            "checkin_date": "2026-07-25", "value_at_checkin": "80", "confidence": "on_track",
            "comment": "",
        })
        checkin = GoalCheckIn.objects.filter(key_result=key_result_a).latest("created_at")
        assert checkin.created_by_id is None

    def test_post_advances_key_result_current_value(self, client_a, key_result_a):
        client_a.post(reverse("hrm:goalcheckin_create", args=[key_result_a.pk]), {
            "checkin_date": "2026-07-25", "value_at_checkin": "85", "confidence": "on_track",
            "comment": "",
        })
        key_result_a.refresh_from_db()
        assert key_result_a.current_value == Decimal("85")

    def test_post_redirects_to_keyresult_detail(self, client_a, key_result_a):
        resp = client_a.post(reverse("hrm:goalcheckin_create", args=[key_result_a.pk]), {
            "checkin_date": "2026-07-25", "value_at_checkin": "85", "confidence": "on_track",
            "comment": "",
        })
        assert reverse("hrm:keyresult_detail", args=[key_result_a.pk]) in resp["Location"]


class TestGoalCheckInListView:
    def test_list_200(self, client_a, goal_checkin_a):
        resp = client_a.get(reverse("hrm:goalcheckin_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, goal_checkin_a):
        resp = client_a.get(reverse("hrm:goalcheckin_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_checkin_a.pk in pks

    def test_list_filter_by_confidence(self, client_a, goal_checkin_a):
        resp = client_a.get(reverse("hrm:goalcheckin_list"), {"confidence": "on_track"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_checkin_a.pk in pks

    def test_list_filter_by_key_result(self, client_a, goal_checkin_a, key_result_a):
        resp = client_a.get(reverse("hrm:goalcheckin_list"), {"key_result": key_result_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_checkin_a.pk in pks

    def test_list_search_by_number(self, client_a, goal_checkin_a):
        resp = client_a.get(reverse("hrm:goalcheckin_list"), {"q": goal_checkin_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_checkin_a.pk in pks

    def test_list_has_choices_context(self, client_a, goal_checkin_a):
        resp = client_a.get(reverse("hrm:goalcheckin_list"))
        assert "confidence_choices" in resp.context
        assert "key_results" in resp.context


class TestGoalCheckInDetailDelete:
    def test_detail_200(self, client_a, goal_checkin_a):
        resp = client_a.get(reverse("hrm:goalcheckin_detail", args=[goal_checkin_a.pk]))
        assert resp.status_code == 200

    def test_delete_post_removes(self, client_a, goal_checkin_a):
        from apps.hrm.models import GoalCheckIn
        pk = goal_checkin_a.pk
        resp = client_a.post(reverse("hrm:goalcheckin_delete", args=[pk]))
        assert resp.status_code == 302
        assert not GoalCheckIn.objects.filter(pk=pk).exists()

    def test_delete_redirects_to_keyresult_detail(self, client_a, goal_checkin_a, key_result_a):
        resp = client_a.post(reverse("hrm:goalcheckin_delete", args=[goal_checkin_a.pk]))
        assert reverse("hrm:keyresult_detail", args=[key_result_a.pk]) in resp["Location"]

    def test_delete_get_not_allowed(self, client_a, goal_checkin_a):
        resp = client_a.get(reverse("hrm:goalcheckin_delete", args=[goal_checkin_a.pk]))
        assert resp.status_code == 405

    def test_delete_does_not_revert_key_result_current_value(self, client_a, goal_checkin_a, key_result_a):
        """Deleting a check-in is an append-only-history removal — it does not roll back
        current_value (no reverse-advance logic exists)."""
        current_before = key_result_a.current_value
        client_a.post(reverse("hrm:goalcheckin_delete", args=[goal_checkin_a.pk]))
        key_result_a.refresh_from_db()
        assert key_result_a.current_value == current_before


# ================================================================ Bounded queries (N+1 guard)
class TestGoalsQueryCount:
    def test_objective_list_bounded_queries_flat(
        self, client_a, tenant_a, goal_period_a, django_assert_max_num_queries
    ):
        """The objective list must not grow per-row — create several objectives each with multiple
        KeyResults and assert the query count stays flat (progress_pct/health_status/key_result_count
        must use the prefetched key_results, not re-query)."""
        from apps.hrm.models import KeyResult, Objective
        from apps.core.models import Employment, OrgUnit, Party
        for i in range(5):
            party = Party.objects.create(tenant=tenant_a, kind="person", name=f"Owner {i}")
            employment = Employment.objects.create(
                tenant=tenant_a, party=party, job_title="Staff",
                hired_on=datetime.date(2023, 1, 1), status="active")
            from apps.hrm.models import EmployeeProfile
            owner = EmployeeProfile.objects.create(
                tenant=tenant_a, party=party, employment=employment, employee_type="full_time")
            obj = Objective.objects.create(
                tenant=tenant_a, title=f"Objective {i}", owner=owner, goal_period=goal_period_a,
                status="active",
            )
            for j in range(2):
                KeyResult.objects.create(
                    tenant=tenant_a, objective=obj, title=f"KR {i}-{j}", metric_type="numeric",
                    start_value=Decimal("0"), target_value=Decimal("100"),
                    current_value=Decimal("30"), weight=Decimal("50"),
                )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:objective_list"))

    def test_goalperiod_list_bounded_queries_flat(
        self, client_a, tenant_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import GoalPeriod
        for i in range(5):
            GoalPeriod.objects.create(
                tenant=tenant_a, name=f"Period {i}", start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 3, 31),
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:goalperiod_list"))

    def test_goalcheckin_list_bounded_queries_flat(
        self, client_a, tenant_a, key_result_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import GoalCheckIn
        for i in range(5):
            GoalCheckIn.objects.create(
                tenant=tenant_a, key_result=key_result_a, checkin_date=datetime.date(2026, 7, 1 + i),
                value_at_checkin=Decimal(str(10 + i)),
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:goalcheckin_list"))
