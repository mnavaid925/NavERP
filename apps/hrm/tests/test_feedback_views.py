"""Tests for HRM 3.20 Continuous Feedback views: KudosBadge CRUD; Feedback CRUD + acknowledge +
request-pull respond workflow + dashboard; OneOnOneMeeting CRUD + complete/cancel; MeetingActionItem
nested create/edit/delete/toggle. Bounded-query guard on list views (mirrors test_reviews_views.py)."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ KudosBadge CRUD
class TestKudosBadgeListView:
    def test_list_200(self, client_a, kudos_badge_a):
        resp = client_a.get(reverse("hrm:kudosbadge_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, kudos_badge_a):
        resp = client_a.get(reverse("hrm:kudosbadge_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert kudos_badge_a.pk in pks

    def test_list_filter_by_is_active(self, client_a, tenant_a, kudos_badge_a):
        from apps.hrm.models import KudosBadge
        inactive = KudosBadge.objects.create(tenant=tenant_a, name="Retired Badge", is_active=False)
        resp = client_a.get(reverse("hrm:kudosbadge_list"), {"is_active": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert kudos_badge_a.pk in pks
        assert inactive.pk not in pks

    def test_list_search_by_name(self, client_a, kudos_badge_a):
        resp = client_a.get(reverse("hrm:kudosbadge_list"), {"q": "Team Player"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert kudos_badge_a.pk in pks


class TestKudosBadgeCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:kudosbadge_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a):
        from apps.hrm.models import KudosBadge
        resp = client_a.post(reverse("hrm:kudosbadge_create"), {
            "name": "Above & Beyond", "description": "", "icon": "star", "color": "",
            "linked_value": "Excellence", "is_active": "on",
        })
        assert resp.status_code == 302
        badge = KudosBadge.objects.filter(tenant=tenant_a, name="Above & Beyond").first()
        assert badge is not None
        assert badge.tenant_id == tenant_a.pk


class TestKudosBadgeDetailEditDelete:
    def test_detail_200(self, client_a, kudos_badge_a):
        resp = client_a.get(reverse("hrm:kudosbadge_detail", args=[kudos_badge_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_recent_feedback(self, client_a, kudos_badge_a, feedback_a):
        feedback_a.badge = kudos_badge_a
        feedback_a.visibility = "public"
        feedback_a.save(update_fields=["badge", "visibility"])
        resp = client_a.get(reverse("hrm:kudosbadge_detail", args=[kudos_badge_a.pk]))
        assert "recent_feedback" in resp.context
        pks = [f.pk for f in resp.context["recent_feedback"]]
        assert feedback_a.pk in pks

    def test_edit_get_200(self, client_a, kudos_badge_a):
        resp = client_a.get(reverse("hrm:kudosbadge_edit", args=[kudos_badge_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_name(self, client_a, kudos_badge_a):
        resp = client_a.post(reverse("hrm:kudosbadge_edit", args=[kudos_badge_a.pk]), {
            "name": "Team Player Renamed", "description": "", "icon": "", "color": "",
            "linked_value": "", "is_active": "on",
        })
        assert resp.status_code == 302
        kudos_badge_a.refresh_from_db()
        assert kudos_badge_a.name == "Team Player Renamed"

    def test_delete_post_removes(self, client_a, tenant_a):
        from apps.hrm.models import KudosBadge
        badge = KudosBadge.objects.create(tenant=tenant_a, name="Deletable Badge")
        resp = client_a.post(reverse("hrm:kudosbadge_delete", args=[badge.pk]))
        assert resp.status_code == 302
        assert not KudosBadge.objects.filter(pk=badge.pk).exists()

    def test_delete_get_not_allowed(self, client_a, kudos_badge_a):
        resp = client_a.get(reverse("hrm:kudosbadge_delete", args=[kudos_badge_a.pk]))
        assert resp.status_code == 405


# ================================================================ Feedback CRUD
class TestFeedbackListView:
    def test_list_200(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_list"))
        assert resp.status_code == 200

    def test_list_shows_own_as_admin(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_list_filter_by_feedback_type(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_list"), {"feedback_type": "kudos"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_list_filter_by_visibility(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_list"), {"visibility": "private"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_list_filter_by_status(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_list"), {"status": "given"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_list_filter_by_receiver(self, client_a, feedback_a, employee_a):
        resp = client_a.get(reverse("hrm:feedback_list"), {"receiver": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_list_filter_by_badge(self, client_a, feedback_a, kudos_badge_a):
        feedback_a.badge = kudos_badge_a
        feedback_a.save(update_fields=["badge"])
        resp = client_a.get(reverse("hrm:feedback_list"), {"badge": kudos_badge_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_list_search_by_number(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_list"), {"q": feedback_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_list_has_choices_context(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_list"))
        assert "feedback_type_choices" in resp.context
        assert "visibility_choices" in resp.context
        assert "status_choices" in resp.context
        assert "employees" in resp.context
        assert "badges" in resp.context
        assert "is_admin" in resp.context

    def test_given_filter_returns_true_for_admin_when_linked(self, client_a, admin_user, employee_a2, feedback_a):
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        resp = client_a.get(reverse("hrm:feedback_list"), {"given": "1"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_received_filter_returns_true_for_admin_when_linked(self, client_a, admin_user, employee_a, feedback_a):
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        resp = client_a.get(reverse("hrm:feedback_list"), {"received": "1"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_requested_filter_isolates_requested_status(self, client_a, tenant_a, feedback_a, employee_a2):
        from apps.hrm.models import Feedback
        ask = Feedback.objects.create(
            tenant=tenant_a, receiver=employee_a2, feedback_type="request", status="requested")
        resp = client_a.get(reverse("hrm:feedback_list"), {"requested": "1"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert ask.pk in pks
        assert feedback_a.pk not in pks

    def test_is_anonymous_filter(self, client_a, feedback_a):
        feedback_a.is_anonymous = True
        feedback_a.save(update_fields=["is_anonymous"])
        resp = client_a.get(reverse("hrm:feedback_list"), {"is_anonymous": "1"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks


class TestFeedbackCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:feedback_create"))
        assert resp.status_code == 200

    def test_post_creates_kudos_with_tenant_and_status_given(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import Feedback
        resp = client_a.post(reverse("hrm:feedback_create"), {
            "receiver": employee_a.pk, "feedback_type": "kudos", "visibility": "private",
            "message": "Nice work!", "is_anonymous": "", "badge": "", "related_objective": "",
            "related_review": "",
        })
        assert resp.status_code == 302
        fb = Feedback.objects.filter(tenant=tenant_a, receiver=employee_a, message="Nice work!").first()
        assert fb is not None
        assert fb.tenant_id == tenant_a.pk
        assert fb.number.startswith("FBK-")
        assert fb.status == "given"

    def test_post_creates_request_type_born_status_requested(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import Feedback
        resp = client_a.post(reverse("hrm:feedback_create"), {
            "receiver": employee_a.pk, "feedback_type": "request", "visibility": "private",
            "message": "Can you give me feedback on my presentation?", "is_anonymous": "",
            "badge": "", "related_objective": "", "related_review": "",
        })
        assert resp.status_code == 302
        fb = Feedback.objects.filter(tenant=tenant_a, receiver=employee_a, feedback_type="request").first()
        assert fb is not None
        assert fb.status == "requested"

    def test_post_invalid_giver_equal_receiver_rejected(self, client_a, tenant_a, admin_user, employee_a):
        """The server-side giver assignment (from the logged-in user's linked profile) must not
        allow self-feedback — the model's clean() guard runs on the resolved giver."""
        from apps.hrm.models import Feedback
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        resp = client_a.post(reverse("hrm:feedback_create"), {
            "receiver": employee_a.pk, "feedback_type": "kudos", "visibility": "private",
            "message": "Self kudos", "is_anonymous": "", "badge": "", "related_objective": "",
            "related_review": "",
        })
        assert resp.status_code == 200
        assert not Feedback.objects.filter(tenant=tenant_a, message="Self kudos").exists()

    def test_receiver_dropdown_scoped_to_tenant(self, client_a, employee_a, employee_b):
        resp = client_a.get(reverse("hrm:feedback_create"))
        pks = list(resp.context["form"].fields["receiver"].queryset.values_list("pk", flat=True))
        assert employee_a.pk in pks
        assert employee_b.pk not in pks

    def test_badge_dropdown_excludes_inactive(self, client_a, tenant_a, kudos_badge_a):
        from apps.hrm.models import KudosBadge
        inactive = KudosBadge.objects.create(tenant=tenant_a, name="Retired", is_active=False)
        resp = client_a.get(reverse("hrm:feedback_create"))
        pks = list(resp.context["form"].fields["badge"].queryset.values_list("pk", flat=True))
        assert kudos_badge_a.pk in pks
        assert inactive.pk not in pks

    def test_form_has_no_status_number_giver_fields(self, client_a):
        resp = client_a.get(reverse("hrm:feedback_create"))
        fields = resp.context["form"].fields
        assert "status" not in fields
        assert "number" not in fields
        assert "giver" not in fields
        assert "acknowledged_at" not in fields
        assert "requested_from" not in fields


class TestFeedbackDetailView:
    def test_detail_200_for_admin(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert "obj" in resp.context
        assert "giver_display" in resp.context
        assert "can_edit" in resp.context
        assert "is_receiver" in resp.context
        assert "is_giver" in resp.context
        assert "can_acknowledge" in resp.context
        assert "can_respond" in resp.context

    def test_can_acknowledge_true_only_when_receiver_and_given(self, client_a, admin_user, employee_a, feedback_a):
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        resp = client_a.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.context["can_acknowledge"] is True

    def test_can_respond_true_only_when_receiver_and_requested(self, client_a, tenant_a, admin_user, employee_a2):
        from apps.hrm.models import Feedback
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        ask = Feedback.objects.create(
            tenant=tenant_a, receiver=employee_a2, feedback_type="request", status="requested")
        resp = client_a.get(reverse("hrm:feedback_detail", args=[ask.pk]))
        assert resp.context["can_respond"] is True
        assert resp.context["can_acknowledge"] is False


class TestFeedbackEditDelete:
    def test_edit_get_200_for_admin(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_edit", args=[feedback_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_message(self, client_a, feedback_a, employee_a):
        resp = client_a.post(reverse("hrm:feedback_edit", args=[feedback_a.pk]), {
            "receiver": employee_a.pk, "feedback_type": "kudos", "visibility": "private",
            "message": "Updated message", "is_anonymous": "", "badge": "", "related_objective": "",
            "related_review": "",
        })
        assert resp.status_code == 302
        feedback_a.refresh_from_db()
        assert feedback_a.message == "Updated message"

    def test_edit_blocked_once_acknowledged(self, client_a, feedback_a):
        """_can_edit_feedback locks content once acknowledged — the admin is still allowed per the
        helper's `_is_admin` short-circuit, so use a non-admin giver instead to prove the lock."""
        from django.test import Client
        from apps.accounts.models import User
        feedback_a.status = "acknowledged"
        feedback_a.save(update_fields=["status"])
        giver_user = User.objects.create_user(
            email="carol@acme.com", username="carol_acme", password="TestPass123!",
            tenant=feedback_a.tenant, is_tenant_admin=False)
        giver_user.party = feedback_a.giver.party
        giver_user.save(update_fields=["party"])
        c = Client()
        c.force_login(giver_user)
        resp = c.get(reverse("hrm:feedback_edit", args=[feedback_a.pk]))
        assert resp.status_code == 302

    def test_delete_post_removes_as_admin(self, client_a, feedback_a):
        from apps.hrm.models import Feedback
        pk = feedback_a.pk
        resp = client_a.post(reverse("hrm:feedback_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Feedback.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_delete", args=[feedback_a.pk]))
        assert resp.status_code == 405


# ================================================================ Feedback acknowledge
class TestFeedbackAcknowledge:
    def test_acknowledge_given_to_acknowledged_by_receiver(self, client_a, admin_user, employee_a, feedback_a):
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        resp = client_a.post(reverse("hrm:feedback_acknowledge", args=[feedback_a.pk]))
        assert resp.status_code == 302
        feedback_a.refresh_from_db()
        assert feedback_a.status == "acknowledged"
        assert feedback_a.acknowledged_at is not None

    def test_acknowledge_allowed_for_admin_without_linked_profile(self, client_a, feedback_a):
        resp = client_a.post(reverse("hrm:feedback_acknowledge", args=[feedback_a.pk]))
        assert resp.status_code == 302
        feedback_a.refresh_from_db()
        assert feedback_a.status == "acknowledged"

    def test_acknowledge_forbidden_for_non_receiver_non_admin(self, member_user, employee_a2, feedback_a):
        """member_user (non-admin) linked to the GIVER, not the receiver — must still be denied."""
        from django.test import Client
        member_user.party = employee_a2.party
        member_user.save(update_fields=["party"])
        c = Client()
        c.force_login(member_user)
        resp = c.post(reverse("hrm:feedback_acknowledge", args=[feedback_a.pk]))
        assert resp.status_code == 403
        feedback_a.refresh_from_db()
        assert feedback_a.status == "given"

    def test_acknowledge_blocked_when_not_given(self, client_a, feedback_a):
        feedback_a.status = "requested"
        feedback_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:feedback_acknowledge", args=[feedback_a.pk]))
        feedback_a.refresh_from_db()
        assert feedback_a.status == "requested"  # unchanged

    def test_acknowledge_get_not_allowed(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_acknowledge", args=[feedback_a.pk]))
        assert resp.status_code == 405


# ================================================================ Feedback request-pull workflow
class TestFeedbackRequestPullWorkflow:
    def test_respond_redirects_to_create_with_respond_to_param(self, client_a, admin_user, employee_a2, tenant_a):
        from apps.hrm.models import Feedback
        ask = Feedback.objects.create(
            tenant=tenant_a, receiver=employee_a2, feedback_type="request", status="requested")
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        resp = client_a.get(reverse("hrm:feedback_respond", args=[ask.pk]))
        assert resp.status_code == 302
        assert f"respond_to={ask.pk}" in resp["Location"]
        assert reverse("hrm:feedback_create") in resp["Location"]

    def test_posting_response_links_requested_from_and_sets_given(
        self, client_a, tenant_a, admin_user, employee_a2, employee_a
    ):
        """The asked person (employee_a2) responds to a request FROM employee_a — POSTing the
        response via ?respond_to= must link requested_from back AND set the response row's own
        status to 'given'."""
        from apps.hrm.models import Feedback
        ask = Feedback.objects.create(
            tenant=tenant_a, giver=employee_a, receiver=employee_a2,
            feedback_type="request", status="requested",
        )
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        resp = client_a.post(f"{reverse('hrm:feedback_create')}?respond_to={ask.pk}", {
            "receiver": employee_a.pk, "feedback_type": "appreciation", "visibility": "private",
            "message": "Here is my feedback on your presentation.", "is_anonymous": "",
            "badge": "", "related_objective": "", "related_review": "",
        })
        assert resp.status_code == 302
        response = Feedback.objects.filter(
            tenant=tenant_a, receiver=employee_a, message="Here is my feedback on your presentation.").first()
        assert response is not None
        assert response.requested_from_id == ask.pk
        assert response.status == "given"

    def test_posting_response_flips_original_ask_to_responded(
        self, client_a, tenant_a, admin_user, employee_a2, employee_a
    ):
        from apps.hrm.models import Feedback
        ask = Feedback.objects.create(
            tenant=tenant_a, giver=employee_a, receiver=employee_a2,
            feedback_type="request", status="requested",
        )
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        client_a.post(f"{reverse('hrm:feedback_create')}?respond_to={ask.pk}", {
            "receiver": employee_a.pk, "feedback_type": "appreciation", "visibility": "private",
            "message": "Response body", "is_anonymous": "", "badge": "", "related_objective": "",
            "related_review": "",
        })
        ask.refresh_from_db()
        assert ask.status == "responded"

    def test_second_respond_attempt_on_responded_ask_is_404(
        self, client_a, tenant_a, admin_user, employee_a2, employee_a
    ):
        """respond looks up status='requested' only — once flipped to 'responded' a second attempt
        to reach feedback_respond against the same pk must 404."""
        from apps.hrm.models import Feedback
        ask = Feedback.objects.create(
            tenant=tenant_a, giver=employee_a, receiver=employee_a2,
            feedback_type="request", status="requested",
        )
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        client_a.post(f"{reverse('hrm:feedback_create')}?respond_to={ask.pk}", {
            "receiver": employee_a.pk, "feedback_type": "appreciation", "visibility": "private",
            "message": "First response", "is_anonymous": "", "badge": "", "related_objective": "",
            "related_review": "",
        })
        ask.refresh_from_db()
        assert ask.status == "responded"
        resp = client_a.get(reverse("hrm:feedback_respond", args=[ask.pk]))
        assert resp.status_code == 404

    def test_non_asked_user_cannot_respond(self, tenant_a, employee_a2, employee_a, outsider_employee_a):
        """A non-admin who is NOT the request's receiver gets 403 attempting feedback_respond."""
        from django.test import Client
        from apps.accounts.models import User
        from apps.hrm.models import Feedback
        ask = Feedback.objects.create(
            tenant=tenant_a, giver=employee_a, receiver=employee_a2,
            feedback_type="request", status="requested",
        )
        outsider_user = User.objects.create_user(
            email="dana2@acme.com", username="dana2_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        outsider_user.party = outsider_employee_a.party
        outsider_user.save(update_fields=["party"])
        c = Client()
        c.force_login(outsider_user)
        resp = c.get(reverse("hrm:feedback_respond", args=[ask.pk]))
        assert resp.status_code == 403

    def test_non_asked_user_respond_link_ignored_on_create(
        self, tenant_a, employee_a2, employee_a, outsider_employee_a
    ):
        """Even if a non-asked user reaches feedback_create with ?respond_to= directly (bypassing
        feedback_respond), the create view drops the linkage — respond_to is set to None for
        anyone but the ask's receiver/an admin, so the response is NOT wired to the ask."""
        from django.test import Client
        from apps.accounts.models import User
        from apps.hrm.models import Feedback
        ask = Feedback.objects.create(
            tenant=tenant_a, giver=employee_a, receiver=employee_a2,
            feedback_type="request", status="requested",
        )
        outsider_user = User.objects.create_user(
            email="dana3@acme.com", username="dana3_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        outsider_user.party = outsider_employee_a.party
        outsider_user.save(update_fields=["party"])
        c = Client()
        c.force_login(outsider_user)
        resp = c.get(f"{reverse('hrm:feedback_create')}?respond_to={ask.pk}")
        assert resp.status_code == 200
        assert resp.context["respond_to"] is None
        ask.refresh_from_db()
        assert ask.status == "requested"  # unchanged, not consumed


# ================================================================ feedback_dashboard
class TestFeedbackDashboard:
    def test_200_for_admin(self, client_a):
        resp = client_a.get(reverse("hrm:feedback_dashboard"))
        assert resp.status_code == 200

    def test_admin_defaults_target_to_first_employee(self, client_a, employee_a):
        """A tenant admin with no linked party defaults `target` to the first employee (so the
        dashboard is never blank for the admin)."""
        resp = client_a.get(reverse("hrm:feedback_dashboard"))
        assert resp.context["target"] is not None

    def test_admin_can_select_employee_via_query_param(self, client_a, employee_a, employee_a2):
        resp = client_a.get(reverse("hrm:feedback_dashboard"), {"employee": employee_a2.pk})
        assert resp.context["target"].pk == employee_a2.pk

    def test_non_admin_sees_own_dashboard(self, member_client, member_user, employee_a, feedback_a):
        member_user.party = employee_a.party
        member_user.save(update_fields=["party"])
        resp = member_client.get(reverse("hrm:feedback_dashboard"))
        assert resp.status_code == 200
        assert resp.context["target"].pk == employee_a.pk
        pks = [f.pk for f in resp.context["received"]]
        assert feedback_a.pk in pks

    def test_non_admin_without_linked_profile_sees_none_target(self, member_client):
        resp = member_client.get(reverse("hrm:feedback_dashboard"))
        assert resp.status_code == 200
        assert resp.context["target"] is None

    def test_received_count_and_given_count_computed(
        self, client_a, tenant_a, employee_a, employee_a2, feedback_a
    ):
        resp = client_a.get(reverse("hrm:feedback_dashboard"), {"employee": employee_a.pk})
        assert resp.context["received_count"] == 1
        assert resp.context["given_count"] == 0

    def test_requested_count_only_counts_status_requested(
        self, client_a, tenant_a, employee_a2, employee_a
    ):
        """A request FROM employee_a2 (giver) TO employee_a (receiver) counts toward
        employee_a2's `requested_count` on their own dashboard."""
        from apps.hrm.models import Feedback
        Feedback.objects.create(
            tenant=tenant_a, giver=employee_a2, receiver=employee_a,
            feedback_type="request", status="requested")
        resp = client_a.get(reverse("hrm:feedback_dashboard"), {"employee": employee_a2.pk})
        assert resp.context["requested_count"] == 1


# ================================================================ OneOnOneMeeting CRUD
class TestOneOnOneMeetingListView:
    def test_list_200(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert oneonone_a.pk in pks

    def test_list_filter_by_status(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_list"), {"status": "scheduled"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert oneonone_a.pk in pks

    def test_list_filter_by_manager(self, client_a, oneonone_a, employee_a2):
        resp = client_a.get(reverse("hrm:oneononemeeting_list"), {"manager": employee_a2.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert oneonone_a.pk in pks

    def test_list_filter_by_employee(self, client_a, oneonone_a, employee_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_list"), {"employee": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert oneonone_a.pk in pks

    def test_list_search_by_number(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_list"), {"q": oneonone_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert oneonone_a.pk in pks

    def test_list_has_choices_context(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_list"))
        assert "status_choices" in resp.context
        assert "employees" in resp.context
        assert "is_admin" in resp.context


class TestOneOnOneMeetingCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a, employee_a2, employee_a):
        from apps.hrm.models import OneOnOneMeeting
        resp = client_a.post(reverse("hrm:oneononemeeting_create"), {
            "manager": employee_a2.pk, "employee": employee_a.pk,
            "scheduled_at": "2026-08-01T10:00", "agenda": "", "shared_notes": "",
            "manager_private_notes": "", "related_objective": "",
        })
        assert resp.status_code == 302
        m = OneOnOneMeeting.objects.filter(tenant=tenant_a, manager=employee_a2, employee=employee_a).first()
        assert m is not None
        assert m.tenant_id == tenant_a.pk
        assert m.number.startswith("O2O-")
        assert m.status == "scheduled"

    def test_post_invalid_manager_equal_employee_rejected(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import OneOnOneMeeting
        resp = client_a.post(reverse("hrm:oneononemeeting_create"), {
            "manager": employee_a.pk, "employee": employee_a.pk,
            "scheduled_at": "2026-08-01T10:00", "agenda": "", "shared_notes": "",
            "manager_private_notes": "", "related_objective": "",
        })
        assert not OneOnOneMeeting.objects.filter(tenant=tenant_a, manager=employee_a, employee=employee_a).exists()

    def test_manager_and_employee_dropdowns_scoped_to_tenant(self, client_a, employee_a, employee_b):
        resp = client_a.get(reverse("hrm:oneononemeeting_create"))
        mgr_pks = list(resp.context["form"].fields["manager"].queryset.values_list("pk", flat=True))
        emp_pks = list(resp.context["form"].fields["employee"].queryset.values_list("pk", flat=True))
        assert employee_a.pk in mgr_pks
        assert employee_b.pk not in mgr_pks
        assert employee_a.pk in emp_pks
        assert employee_b.pk not in emp_pks

    def test_form_has_no_status_or_number_field(self, client_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_create"))
        fields = resp.context["form"].fields
        assert "status" not in fields
        assert "number" not in fields
        assert "completed_at" not in fields


class TestOneOnOneMeetingDetailEditDelete:
    def test_detail_200_for_admin(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_detail", args=[oneonone_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, oneonone_a, action_item_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_detail", args=[oneonone_a.pk]))
        assert "obj" in resp.context
        assert "show_private" in resp.context
        assert "can_manage" in resp.context
        assert "action_items" in resp.context
        assert "action_form" in resp.context
        pks = [i.pk for i in resp.context["action_items"]]
        assert action_item_a.pk in pks

    def test_edit_get_200_for_admin(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_edit", args=[oneonone_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_agenda(self, client_a, oneonone_a, employee_a2, employee_a):
        resp = client_a.post(reverse("hrm:oneononemeeting_edit", args=[oneonone_a.pk]), {
            "manager": employee_a2.pk, "employee": employee_a.pk,
            "scheduled_at": "2026-08-01T10:00", "agenda": "Updated agenda", "shared_notes": "",
            "manager_private_notes": "", "related_objective": "",
        })
        assert resp.status_code == 302
        oneonone_a.refresh_from_db()
        assert oneonone_a.agenda == "Updated agenda"

    def test_delete_post_removes_as_admin(self, client_a, oneonone_a):
        from apps.hrm.models import OneOnOneMeeting
        pk = oneonone_a.pk
        resp = client_a.post(reverse("hrm:oneononemeeting_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OneOnOneMeeting.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_delete", args=[oneonone_a.pk]))
        assert resp.status_code == 405

    def test_delete_cascades_action_items(self, client_a, oneonone_a, action_item_a):
        from apps.hrm.models import MeetingActionItem
        client_a.post(reverse("hrm:oneononemeeting_delete", args=[oneonone_a.pk]))
        assert not MeetingActionItem.objects.filter(pk=action_item_a.pk).exists()


class TestOneOnOneMeetingCompleteCancel:
    def test_complete_scheduled_to_completed_as_admin(self, client_a, oneonone_a):
        resp = client_a.post(reverse("hrm:oneononemeeting_complete", args=[oneonone_a.pk]))
        assert resp.status_code == 302
        oneonone_a.refresh_from_db()
        assert oneonone_a.status == "completed"
        assert oneonone_a.completed_at is not None

    def test_complete_by_manager(self, tenant_a, oneonone_a, employee_a2):
        from django.test import Client
        from apps.accounts.models import User
        manager_user = User.objects.create_user(
            email="carol2@acme.com", username="carol2_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        manager_user.party = employee_a2.party
        manager_user.save(update_fields=["party"])
        c = Client()
        c.force_login(manager_user)
        resp = c.post(reverse("hrm:oneononemeeting_complete", args=[oneonone_a.pk]))
        assert resp.status_code == 302
        oneonone_a.refresh_from_db()
        assert oneonone_a.status == "completed"

    def test_complete_blocked_when_not_scheduled(self, client_a, oneonone_a):
        oneonone_a.status = "cancelled"
        oneonone_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:oneononemeeting_complete", args=[oneonone_a.pk]))
        oneonone_a.refresh_from_db()
        assert oneonone_a.status == "cancelled"  # unchanged

    def test_complete_get_not_allowed(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_complete", args=[oneonone_a.pk]))
        assert resp.status_code == 405

    def test_cancel_scheduled_to_cancelled_as_admin(self, client_a, oneonone_a):
        resp = client_a.post(reverse("hrm:oneononemeeting_cancel", args=[oneonone_a.pk]))
        assert resp.status_code == 302
        oneonone_a.refresh_from_db()
        assert oneonone_a.status == "cancelled"

    def test_cancel_blocked_when_not_scheduled(self, client_a, oneonone_a):
        oneonone_a.status = "completed"
        oneonone_a.completed_at = None
        oneonone_a.save(update_fields=["status", "completed_at"])
        client_a.post(reverse("hrm:oneononemeeting_cancel", args=[oneonone_a.pk]))
        oneonone_a.refresh_from_db()
        assert oneonone_a.status == "completed"  # unchanged

    def test_cancel_get_not_allowed(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_cancel", args=[oneonone_a.pk]))
        assert resp.status_code == 405


# ================================================================ MeetingActionItem nested CRUD
class TestMeetingActionItemCreateView:
    def test_get_200(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:meetingactionitem_create", args=[oneonone_a.pk]))
        assert resp.status_code == 200

    def test_post_creates_with_tenant_and_meeting_from_url(self, client_a, tenant_a, oneonone_a, employee_a):
        from apps.hrm.models import MeetingActionItem
        resp = client_a.post(reverse("hrm:meetingactionitem_create", args=[oneonone_a.pk]), {
            "description": "Follow up on training budget", "owner": employee_a.pk, "due_date": "",
        })
        assert resp.status_code == 302
        item = MeetingActionItem.objects.filter(tenant=tenant_a, description="Follow up on training budget").first()
        assert item is not None
        assert item.meeting_id == oneonone_a.pk
        assert item.tenant_id == tenant_a.pk
        assert item.number.startswith("MAI-")
        assert item.status == "open"

    def test_post_redirects_to_meeting_detail(self, client_a, oneonone_a, employee_a):
        resp = client_a.post(reverse("hrm:meetingactionitem_create", args=[oneonone_a.pk]), {
            "description": "Item", "owner": employee_a.pk, "due_date": "",
        })
        assert reverse("hrm:oneononemeeting_detail", args=[oneonone_a.pk]) in resp["Location"]

    def test_owner_dropdown_scoped_to_meeting_participants_only(
        self, client_a, oneonone_a, employee_a2, employee_a, outsider_employee_a
    ):
        """The form scopes `owner` to the meeting's two participants — an outsider must not appear
        as an assignable owner."""
        resp = client_a.get(reverse("hrm:meetingactionitem_create", args=[oneonone_a.pk]))
        pks = list(resp.context["form"].fields["owner"].queryset.values_list("pk", flat=True))
        assert employee_a.pk in pks
        assert employee_a2.pk in pks
        assert outsider_employee_a.pk not in pks

    def test_form_has_no_status_or_meeting_field(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:meetingactionitem_create", args=[oneonone_a.pk]))
        fields = resp.context["form"].fields
        assert "status" not in fields
        assert "meeting" not in fields
        assert "number" not in fields


class TestMeetingActionItemDetailEditDelete:
    def test_detail_200_for_admin(self, client_a, action_item_a):
        resp = client_a.get(reverse("hrm:meetingactionitem_detail", args=[action_item_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, action_item_a):
        resp = client_a.get(reverse("hrm:meetingactionitem_detail", args=[action_item_a.pk]))
        assert "obj" in resp.context
        assert "meeting" in resp.context
        assert "can_manage" in resp.context

    def test_edit_get_200_for_admin(self, client_a, action_item_a):
        resp = client_a.get(reverse("hrm:meetingactionitem_edit", args=[action_item_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_description(self, client_a, action_item_a, employee_a):
        resp = client_a.post(reverse("hrm:meetingactionitem_edit", args=[action_item_a.pk]), {
            "description": "Renamed action item", "owner": employee_a.pk, "due_date": "",
        })
        assert resp.status_code == 302
        action_item_a.refresh_from_db()
        assert action_item_a.description == "Renamed action item"

    def test_delete_post_removes_as_admin(self, client_a, action_item_a):
        from apps.hrm.models import MeetingActionItem
        pk = action_item_a.pk
        resp = client_a.post(reverse("hrm:meetingactionitem_delete", args=[pk]))
        assert resp.status_code == 302
        assert not MeetingActionItem.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, action_item_a):
        resp = client_a.get(reverse("hrm:meetingactionitem_delete", args=[action_item_a.pk]))
        assert resp.status_code == 405


class TestMeetingActionItemToggle:
    def test_toggle_open_to_done_sets_completed_at(self, client_a, action_item_a):
        assert action_item_a.status == "open"
        resp = client_a.post(reverse("hrm:meetingactionitem_toggle", args=[action_item_a.pk]))
        assert resp.status_code == 302
        action_item_a.refresh_from_db()
        assert action_item_a.status == "done"
        assert action_item_a.completed_at is not None

    def test_toggle_done_to_open_clears_completed_at(self, client_a, action_item_a):
        action_item_a.status = "done"
        action_item_a.completed_at = datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc)
        action_item_a.save(update_fields=["status", "completed_at"])
        resp = client_a.post(reverse("hrm:meetingactionitem_toggle", args=[action_item_a.pk]))
        assert resp.status_code == 302
        action_item_a.refresh_from_db()
        assert action_item_a.status == "open"
        assert action_item_a.completed_at is None

    def test_toggle_by_owner(self, tenant_a, oneonone_a, action_item_a, employee_a):
        from django.test import Client
        from apps.accounts.models import User
        owner_user = User.objects.create_user(
            email="alice2@acme.com", username="alice2_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        owner_user.party = employee_a.party
        owner_user.save(update_fields=["party"])
        c = Client()
        c.force_login(owner_user)
        resp = c.post(reverse("hrm:meetingactionitem_toggle", args=[action_item_a.pk]))
        assert resp.status_code == 302
        action_item_a.refresh_from_db()
        assert action_item_a.status == "done"

    def test_toggle_by_manager(self, tenant_a, oneonone_a, action_item_a, employee_a2):
        from django.test import Client
        from apps.accounts.models import User
        manager_user = User.objects.create_user(
            email="carol3@acme.com", username="carol3_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        manager_user.party = employee_a2.party
        manager_user.save(update_fields=["party"])
        c = Client()
        c.force_login(manager_user)
        resp = c.post(reverse("hrm:meetingactionitem_toggle", args=[action_item_a.pk]))
        assert resp.status_code == 302
        action_item_a.refresh_from_db()
        assert action_item_a.status == "done"

    def test_toggle_get_not_allowed(self, client_a, action_item_a):
        resp = client_a.get(reverse("hrm:meetingactionitem_toggle", args=[action_item_a.pk]))
        assert resp.status_code == 405


# ================================================================ Security fix regression: action
# item owner who is NOT a meeting participant cannot manage it (bypass the form's owner-scoping by
# creating the item directly with an outsider owner)
class TestActionItemOwnerMustBeMeetingParticipant:
    @pytest.fixture
    def outsider_owned_item(self, db, tenant_a, oneonone_a, outsider_employee_a):
        """A MeetingActionItem whose owner is NOT a participant of oneonone_a — constructed
        directly (the form's owner queryset would never offer this outsider), to exercise the
        view-layer `_can_manage_action_item` gate."""
        from apps.hrm.models import MeetingActionItem
        return MeetingActionItem.objects.create(
            tenant=tenant_a, meeting=oneonone_a, description="Owned by an outsider",
            owner=outsider_employee_a, status="open",
        )

    @pytest.fixture
    def outsider_owner_client(self, db, tenant_a, outsider_employee_a):
        from django.test import Client
        from apps.accounts.models import User
        user = User.objects.create_user(
            email="dana4@acme.com", username="dana4_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        user.party = outsider_employee_a.party
        user.save(update_fields=["party"])
        c = Client()
        c.force_login(user)
        return c

    def test_outsider_owner_cannot_view_the_meeting(self, outsider_owner_client, oneonone_a):
        """Sanity baseline: the outsider owner is not a participant, so they cannot even view the
        1:1 the item belongs to."""
        resp = outsider_owner_client.get(reverse("hrm:oneononemeeting_detail", args=[oneonone_a.pk]))
        assert resp.status_code == 403

    def test_outsider_owner_403_on_action_item_detail(self, outsider_owner_client, outsider_owned_item):
        resp = outsider_owner_client.get(reverse("hrm:meetingactionitem_detail", args=[outsider_owned_item.pk]))
        assert resp.status_code == 403

    def test_outsider_owner_403_on_action_item_edit(self, outsider_owner_client, outsider_owned_item):
        resp = outsider_owner_client.get(reverse("hrm:meetingactionitem_edit", args=[outsider_owned_item.pk]))
        assert resp.status_code == 403

    def test_outsider_owner_blocked_on_action_item_delete(self, outsider_owner_client, outsider_owned_item):
        from apps.hrm.models import MeetingActionItem
        resp = outsider_owner_client.post(reverse("hrm:meetingactionitem_delete", args=[outsider_owned_item.pk]))
        assert resp.status_code == 302  # messages.error + redirect (not a hard 403), no mutation
        assert MeetingActionItem.objects.filter(pk=outsider_owned_item.pk).exists()

    def test_outsider_owner_403_on_action_item_toggle(self, outsider_owner_client, outsider_owned_item):
        resp = outsider_owner_client.post(reverse("hrm:meetingactionitem_toggle", args=[outsider_owned_item.pk]))
        assert resp.status_code == 403
        outsider_owned_item.refresh_from_db()
        assert outsider_owned_item.status == "open"  # unchanged


# ================================================================ Bounded queries (N+1 guard)
class TestFeedbackQueryCount:
    def test_feedback_list_bounded_queries_flat(
        self, client_a, tenant_a, employee_a2, employee_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import Feedback
        for i in range(8):
            Feedback.objects.create(
                tenant=tenant_a, giver=employee_a2, receiver=employee_a, feedback_type="kudos",
                message=f"Msg {i}",
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:feedback_list"))

    def test_oneononemeeting_list_bounded_queries_flat(
        self, client_a, tenant_a, employee_a2, employee_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import OneOnOneMeeting
        for i in range(8):
            OneOnOneMeeting.objects.create(
                tenant=tenant_a, manager=employee_a2, employee=employee_a,
                scheduled_at=datetime.datetime(2026, 7, i + 1, 10, 0, tzinfo=datetime.timezone.utc),
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:oneononemeeting_list"))

    def test_feedback_dashboard_bounded_queries_flat(
        self, client_a, tenant_a, employee_a, employee_a2, django_assert_max_num_queries
    ):
        from apps.hrm.models import Feedback
        for i in range(8):
            Feedback.objects.create(
                tenant=tenant_a, giver=employee_a2, receiver=employee_a, feedback_type="kudos",
                message=f"Msg {i}",
            )
        with django_assert_max_num_queries(20):
            client_a.get(reverse("hrm:feedback_dashboard"), {"employee": employee_a.pk})
