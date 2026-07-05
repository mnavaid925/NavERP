"""Security tests for HRM 3.18 Goal Setting: cross-tenant IDOR (GoalPeriod/Objective/KeyResult/
GoalCheckIn detail/edit/delete + nested creates), list isolation, anonymous-blocked,
@tenant_admin_required on goalperiod_activate/close, CSRF enforcement on mutating POSTs, and the
GoalPeriodForm status-field authz fix."""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ GoalPeriod IDOR
class TestGoalPeriodIDOR:
    def test_detail_cross_tenant_404(self, client_a, goal_period_b):
        resp = client_a.get(reverse("hrm:goalperiod_detail", args=[goal_period_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, goal_period_b):
        resp = client_a.get(reverse("hrm:goalperiod_edit", args=[goal_period_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, goal_period_b):
        resp = client_a.post(reverse("hrm:goalperiod_edit", args=[goal_period_b.pk]), {
            "name": "hacked", "period_type": "quarterly",
            "start_date": "2026-07-01", "end_date": "2026-09-30", "description": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, goal_period_b):
        resp = client_a.post(reverse("hrm:goalperiod_delete", args=[goal_period_b.pk]))
        assert resp.status_code == 404

    def test_activate_cross_tenant_404(self, client_a, goal_period_b):
        resp = client_a.post(reverse("hrm:goalperiod_activate", args=[goal_period_b.pk]))
        assert resp.status_code == 404

    def test_close_cross_tenant_404(self, client_a, goal_period_b):
        resp = client_a.post(reverse("hrm:goalperiod_close", args=[goal_period_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_periods(self, client_a, goal_period_a, goal_period_b):
        resp = client_a.get(reverse("hrm:goalperiod_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_period_a.pk in pks
        assert goal_period_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, goal_period_b):
        original_status = goal_period_b.status
        original_name = goal_period_b.name
        client_a.post(reverse("hrm:goalperiod_edit", args=[goal_period_b.pk]), {
            "name": "hacked", "period_type": "quarterly",
            "start_date": "2026-07-01", "end_date": "2026-09-30", "description": "",
        })
        client_a.post(reverse("hrm:goalperiod_close", args=[goal_period_b.pk]))
        goal_period_b.refresh_from_db()
        assert goal_period_b.status == original_status
        assert goal_period_b.name == original_name


# ================================================================ Objective IDOR
class TestObjectiveIDOR:
    def test_detail_cross_tenant_404(self, client_a, objective_b):
        resp = client_a.get(reverse("hrm:objective_detail", args=[objective_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, objective_b):
        resp = client_a.get(reverse("hrm:objective_edit", args=[objective_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, objective_b):
        resp = client_a.post(reverse("hrm:objective_edit", args=[objective_b.pk]), {
            "title": "hacked", "description": "", "owner": objective_b.owner_id,
            "goal_period": objective_b.goal_period_id, "scope": "individual",
            "target_type": "committed", "weight": "100", "status": "active",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, objective_b):
        resp = client_a.post(reverse("hrm:objective_delete", args=[objective_b.pk]))
        assert resp.status_code == 404

    def test_keyresult_create_nested_cross_tenant_parent_404(self, client_a, objective_b):
        """POST keyresult_create against a tenant_b objective pk must 404 — the nested-create view
        looks up the parent Objective scoped to request.tenant."""
        from apps.hrm.models import KeyResult
        resp = client_a.post(reverse("hrm:keyresult_create", args=[objective_b.pk]), {
            "title": "hacked KR", "metric_type": "numeric", "start_value": "0",
            "target_value": "100", "current_value": "0", "weight": "50", "status": "not_started",
        })
        assert resp.status_code == 404
        assert not KeyResult.objects.filter(objective=objective_b, title="hacked KR").exists()

    def test_keyresult_create_nested_cross_tenant_parent_404_get(self, client_a, objective_b):
        resp = client_a.get(reverse("hrm:keyresult_create", args=[objective_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_objectives(self, client_a, objective_a, objective_b):
        resp = client_a.get(reverse("hrm:objective_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert objective_a.pk in pks
        assert objective_b.pk not in pks

    def test_tree_excludes_b_objectives(self, client_a, objective_a, objective_b):
        resp = client_a.get(reverse("hrm:objective_tree"))
        pks = [o.pk for o in resp.context["objectives"]]
        assert objective_a.pk in pks
        assert objective_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, objective_b):
        original_title = objective_b.title
        client_a.post(reverse("hrm:objective_edit", args=[objective_b.pk]), {
            "title": "hacked", "description": "", "owner": objective_b.owner_id,
            "goal_period": objective_b.goal_period_id, "scope": "individual",
            "target_type": "committed", "weight": "100", "status": "active",
        })
        objective_b.refresh_from_db()
        assert objective_b.title == original_title


# ================================================================ KeyResult IDOR
class TestKeyResultIDOR:
    def test_detail_cross_tenant_404(self, client_a, key_result_b):
        resp = client_a.get(reverse("hrm:keyresult_detail", args=[key_result_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, key_result_b):
        resp = client_a.get(reverse("hrm:keyresult_edit", args=[key_result_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, key_result_b):
        resp = client_a.post(reverse("hrm:keyresult_edit", args=[key_result_b.pk]), {
            "title": "hacked", "metric_type": "numeric", "start_value": "0",
            "target_value": "100", "current_value": "0", "weight": "50", "status": "in_progress",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, key_result_b):
        resp = client_a.post(reverse("hrm:keyresult_delete", args=[key_result_b.pk]))
        assert resp.status_code == 404

    def test_goalcheckin_create_nested_cross_tenant_parent_404(self, client_a, key_result_b):
        """POST goalcheckin_create against a tenant_b key_result pk must 404 — the nested-create view
        looks up the parent KeyResult scoped to request.tenant."""
        from apps.hrm.models import GoalCheckIn
        resp = client_a.post(reverse("hrm:goalcheckin_create", args=[key_result_b.pk]), {
            "checkin_date": "2026-07-25", "value_at_checkin": "999", "confidence": "on_track",
            "comment": "",
        })
        assert resp.status_code == 404
        assert not GoalCheckIn.objects.filter(key_result=key_result_b).exists()

    def test_goalcheckin_create_nested_cross_tenant_parent_404_get(self, client_a, key_result_b):
        resp = client_a.get(reverse("hrm:goalcheckin_create", args=[key_result_b.pk]))
        assert resp.status_code == 404

    def test_cross_tenant_checkin_does_not_advance_b_current_value(self, client_a, key_result_b):
        original_value = key_result_b.current_value
        client_a.post(reverse("hrm:goalcheckin_create", args=[key_result_b.pk]), {
            "checkin_date": "2026-07-25", "value_at_checkin": "999", "confidence": "on_track",
            "comment": "",
        })
        key_result_b.refresh_from_db()
        assert key_result_b.current_value == original_value

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, key_result_b):
        original_title = key_result_b.title
        client_a.post(reverse("hrm:keyresult_edit", args=[key_result_b.pk]), {
            "title": "hacked", "metric_type": "numeric", "start_value": "0",
            "target_value": "100", "current_value": "0", "weight": "50", "status": "in_progress",
        })
        key_result_b.refresh_from_db()
        assert key_result_b.title == original_title


# ================================================================ GoalCheckIn IDOR
class TestGoalCheckInIDOR:
    def test_detail_cross_tenant_404(self, client_a, goal_checkin_b):
        resp = client_a.get(reverse("hrm:goalcheckin_detail", args=[goal_checkin_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, goal_checkin_b):
        resp = client_a.post(reverse("hrm:goalcheckin_delete", args=[goal_checkin_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_checkins(self, client_a, goal_checkin_a, goal_checkin_b):
        resp = client_a.get(reverse("hrm:goalcheckin_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert goal_checkin_a.pk in pks
        assert goal_checkin_b.pk not in pks

    def test_cross_tenant_delete_does_not_remove_b_row(self, client_a, goal_checkin_b):
        from apps.hrm.models import GoalCheckIn
        client_a.post(reverse("hrm:goalcheckin_delete", args=[goal_checkin_b.pk]))
        assert GoalCheckIn.objects.filter(pk=goal_checkin_b.pk).exists()


# ================================================================ Anonymous user -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:goalperiod_list", []),
        ("hrm:objective_list", []),
        ("hrm:objective_tree", []),
        ("hrm:goalcheckin_list", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_pages(
        self, client, goal_period_a, objective_a, key_result_a, goal_checkin_a
    ):
        for url_name, pk in [
            ("hrm:goalperiod_detail", goal_period_a.pk),
            ("hrm:objective_detail", objective_a.pk),
            ("hrm:keyresult_detail", key_result_a.pk),
            ("hrm:goalcheckin_detail", goal_checkin_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_actions(self, client, goal_period_a, objective_a, key_result_a):
        for url_name, pk in [
            ("hrm:goalperiod_delete", goal_period_a.pk),
            ("hrm:goalperiod_activate", goal_period_a.pk),
            ("hrm:goalperiod_close", goal_period_a.pk),
            ("hrm:objective_delete", objective_a.pk),
            ("hrm:keyresult_delete", key_result_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_nested_creates(self, client, objective_a, key_result_a):
        resp1 = client.get(reverse("hrm:keyresult_create", args=[objective_a.pk]))
        assert resp1.status_code == 302
        assert "login" in resp1["Location"]
        resp2 = client.get(reverse("hrm:goalcheckin_create", args=[key_result_a.pk]))
        assert resp2.status_code == 302
        assert "login" in resp2["Location"]


# ================================================================ AuthZ — tenant-admin-only actions
class TestGoalPeriodAdminOnlyActions:
    """@tenant_admin_required gates goalperiod_activate/close — a plain (non-admin) tenant member
    must get 403 and the row must remain unchanged."""

    def test_non_admin_403_on_activate(self, member_client, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="Draft For AuthZ", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31), status="draft",
        )
        resp = member_client.post(reverse("hrm:goalperiod_activate", args=[gp.pk]))
        assert resp.status_code == 403
        gp.refresh_from_db()
        assert gp.status == "draft"

    def test_non_admin_403_on_close(self, member_client, goal_period_a):
        resp = member_client.post(reverse("hrm:goalperiod_close", args=[goal_period_a.pk]))
        assert resp.status_code == 403
        goal_period_a.refresh_from_db()
        assert goal_period_a.status == "active"

    def test_non_admin_can_still_view_lists_and_details(self, member_client, goal_period_a):
        """Plain @login_required reads (list/detail) stay open to non-admin tenant members."""
        resp = member_client.get(reverse("hrm:goalperiod_list"))
        assert resp.status_code == 200
        resp = member_client.get(reverse("hrm:goalperiod_detail", args=[goal_period_a.pk]))
        assert resp.status_code == 200

    def test_non_admin_can_still_do_regular_crud(
        self, member_client, tenant_a, employee_a, goal_period_a
    ):
        """goalperiod_create/objective_create/keyresult_create/goalcheckin_create are plain
        @login_required — not admin-gated (only the activate/close workflow actions are)."""
        resp = member_client.get(reverse("hrm:objective_create"))
        assert resp.status_code == 200


# ================================================================ CSRF enforcement
class TestGoalsCSRFEnforcement:
    def test_goalperiod_delete_enforces_csrf(self, admin_user, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="CSRF Delete", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:goalperiod_delete", args=[gp.pk]))
        assert resp.status_code == 403

    def test_goalperiod_activate_enforces_csrf(self, admin_user, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="CSRF Activate", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31), status="draft",
        )
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:goalperiod_activate", args=[gp.pk]))
        assert resp.status_code == 403
        gp.refresh_from_db()
        assert gp.status == "draft"

    def test_goalperiod_close_enforces_csrf(self, admin_user, goal_period_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:goalperiod_close", args=[goal_period_a.pk]))
        assert resp.status_code == 403
        goal_period_a.refresh_from_db()
        assert goal_period_a.status == "active"

    def test_objective_delete_enforces_csrf(self, admin_user, objective_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:objective_delete", args=[objective_a.pk]))
        assert resp.status_code == 403

    def test_keyresult_create_enforces_csrf(self, admin_user, objective_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:keyresult_create", args=[objective_a.pk]), {
            "title": "CSRF-blocked KR", "metric_type": "numeric", "start_value": "0",
            "target_value": "100", "current_value": "0", "weight": "50", "status": "not_started",
        })
        assert resp.status_code == 403
        from apps.hrm.models import KeyResult
        assert not KeyResult.objects.filter(objective=objective_a, title="CSRF-blocked KR").exists()

    def test_keyresult_delete_enforces_csrf(self, admin_user, key_result_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:keyresult_delete", args=[key_result_a.pk]))
        assert resp.status_code == 403

    def test_goalcheckin_create_enforces_csrf(self, admin_user, key_result_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:goalcheckin_create", args=[key_result_a.pk]), {
            "checkin_date": "2026-07-25", "value_at_checkin": "999", "confidence": "on_track",
            "comment": "",
        })
        assert resp.status_code == 403
        key_result_a.refresh_from_db()
        assert key_result_a.current_value != Decimal("999")

    def test_goalcheckin_delete_enforces_csrf(self, admin_user, goal_checkin_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:goalcheckin_delete", args=[goal_checkin_a.pk]))
        assert resp.status_code == 403


# ================================================================ GoalPeriodForm authz fix
class TestGoalPeriodFormStatusFieldExcluded:
    """The authz fix: GoalPeriodForm's Meta.fields does not include `status`, so a regular tenant
    admin (or any user) cannot bypass the @tenant_admin_required activate/close gate by POSTing
    status directly through the edit form."""

    def test_form_has_no_status_field(self):
        from apps.hrm.forms import GoalPeriodForm
        assert "status" not in GoalPeriodForm.Meta.fields

    def test_edit_post_with_status_active_does_not_activate_draft_period(self, client_a, tenant_a):
        from apps.hrm.models import GoalPeriod
        gp = GoalPeriod.objects.create(
            tenant=tenant_a, name="Draft Bypass Attempt", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31), status="draft",
        )
        resp = client_a.post(reverse("hrm:goalperiod_edit", args=[gp.pk]), {
            "name": gp.name, "period_type": "quarterly",
            "start_date": "2026-01-01", "end_date": "2026-03-31", "description": "",
            "status": "active",
        })
        assert resp.status_code == 302
        gp.refresh_from_db()
        assert gp.status == "draft"  # the authz fix — status did NOT flip via the edit form

    def test_edit_post_with_status_closed_does_not_close_active_period(self, client_a, goal_period_a):
        resp = client_a.post(reverse("hrm:goalperiod_edit", args=[goal_period_a.pk]), {
            "name": goal_period_a.name, "period_type": "quarterly",
            "start_date": "2026-07-01", "end_date": "2026-09-30", "description": "",
            "status": "closed",
        })
        assert resp.status_code == 302
        goal_period_a.refresh_from_db()
        assert goal_period_a.status == "active"  # unchanged despite the POSTed status=closed
