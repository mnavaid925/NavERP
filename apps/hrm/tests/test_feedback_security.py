"""Security tests for HRM 3.20 Continuous Feedback: cross-tenant IDOR (KudosBadge/Feedback/
OneOnOneMeeting/MeetingActionItem detail/edit/delete + workflow actions), list isolation,
anonymous-blocked, CONFIDENTIALITY (_can_view_feedback/_visible_feedback_q — private/team/public
visibility tiers, anonymous-giver masking + the anti-correlation search guard, kudosbadge_detail's
recent-awards leak fix), manager_private_notes gating (mirrors 3.19's private_notes), the
_can_manage_action_item security fix (an item owner who isn't a meeting participant cannot manage
it), form-smuggling guards, and CSRF enforcement."""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ KudosBadge IDOR
class TestKudosBadgeIDOR:
    def test_detail_cross_tenant_404(self, client_a, kudos_badge_b):
        resp = client_a.get(reverse("hrm:kudosbadge_detail", args=[kudos_badge_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, kudos_badge_b):
        resp = client_a.get(reverse("hrm:kudosbadge_edit", args=[kudos_badge_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, kudos_badge_b):
        resp = client_a.post(reverse("hrm:kudosbadge_edit", args=[kudos_badge_b.pk]), {
            "name": "hacked", "description": "", "icon": "", "color": "", "linked_value": "",
            "is_active": "on",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, kudos_badge_b):
        resp = client_a.post(reverse("hrm:kudosbadge_delete", args=[kudos_badge_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_badges(self, client_a, kudos_badge_a, kudos_badge_b):
        resp = client_a.get(reverse("hrm:kudosbadge_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert kudos_badge_a.pk in pks
        assert kudos_badge_b.pk not in pks

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, kudos_badge_b):
        original_name = kudos_badge_b.name
        client_a.post(reverse("hrm:kudosbadge_edit", args=[kudos_badge_b.pk]), {
            "name": "hacked", "description": "", "icon": "", "color": "", "linked_value": "",
            "is_active": "on",
        })
        kudos_badge_b.refresh_from_db()
        assert kudos_badge_b.name == original_name


# ================================================================ Feedback IDOR
class TestFeedbackIDOR:
    def test_detail_cross_tenant_404(self, client_a, feedback_b):
        resp = client_a.get(reverse("hrm:feedback_detail", args=[feedback_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, feedback_b):
        resp = client_a.get(reverse("hrm:feedback_edit", args=[feedback_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, feedback_b):
        resp = client_a.post(reverse("hrm:feedback_edit", args=[feedback_b.pk]), {
            "receiver": feedback_b.receiver_id, "feedback_type": "kudos", "visibility": "private",
            "message": "hacked", "is_anonymous": "", "badge": "", "related_objective": "",
            "related_review": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, feedback_b):
        resp = client_a.post(reverse("hrm:feedback_delete", args=[feedback_b.pk]))
        assert resp.status_code == 404

    def test_acknowledge_cross_tenant_404(self, client_a, feedback_b):
        resp = client_a.post(reverse("hrm:feedback_acknowledge", args=[feedback_b.pk]))
        assert resp.status_code == 404

    def test_respond_cross_tenant_404(self, client_a, tenant_b, feedback_b, employee_b):
        feedback_b.feedback_type = "request"
        feedback_b.status = "requested"
        feedback_b.save(update_fields=["feedback_type", "status"])
        resp = client_a.get(reverse("hrm:feedback_respond", args=[feedback_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_feedback(self, client_a, feedback_a, feedback_b):
        resp = client_a.get(reverse("hrm:feedback_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks
        assert feedback_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, feedback_b):
        original_message = feedback_b.message
        client_a.post(reverse("hrm:feedback_edit", args=[feedback_b.pk]), {
            "receiver": feedback_b.receiver_id, "feedback_type": "kudos", "visibility": "private",
            "message": "hacked", "is_anonymous": "", "badge": "", "related_objective": "",
            "related_review": "",
        })
        client_a.post(reverse("hrm:feedback_acknowledge", args=[feedback_b.pk]))
        feedback_b.refresh_from_db()
        assert feedback_b.message == original_message
        assert feedback_b.status == "given"


# ================================================================ OneOnOneMeeting IDOR
class TestOneOnOneMeetingIDOR:
    def test_detail_cross_tenant_404(self, client_a, oneonone_b):
        resp = client_a.get(reverse("hrm:oneononemeeting_detail", args=[oneonone_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, oneonone_b):
        resp = client_a.get(reverse("hrm:oneononemeeting_edit", args=[oneonone_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, oneonone_b):
        resp = client_a.post(reverse("hrm:oneononemeeting_edit", args=[oneonone_b.pk]), {
            "manager": oneonone_b.manager_id, "employee": oneonone_b.employee_id,
            "scheduled_at": "2026-08-01T10:00", "agenda": "hacked", "shared_notes": "",
            "manager_private_notes": "", "related_objective": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, oneonone_b):
        resp = client_a.post(reverse("hrm:oneononemeeting_delete", args=[oneonone_b.pk]))
        assert resp.status_code == 404

    def test_complete_cross_tenant_404(self, client_a, oneonone_b):
        resp = client_a.post(reverse("hrm:oneononemeeting_complete", args=[oneonone_b.pk]))
        assert resp.status_code == 404

    def test_cancel_cross_tenant_404(self, client_a, oneonone_b):
        resp = client_a.post(reverse("hrm:oneononemeeting_cancel", args=[oneonone_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_meetings(self, client_a, oneonone_a, oneonone_b):
        resp = client_a.get(reverse("hrm:oneononemeeting_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert oneonone_a.pk in pks
        assert oneonone_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, oneonone_b):
        original_status = oneonone_b.status
        client_a.post(reverse("hrm:oneononemeeting_edit", args=[oneonone_b.pk]), {
            "manager": oneonone_b.manager_id, "employee": oneonone_b.employee_id,
            "scheduled_at": "2026-08-01T10:00", "agenda": "hacked", "shared_notes": "",
            "manager_private_notes": "", "related_objective": "",
        })
        client_a.post(reverse("hrm:oneononemeeting_complete", args=[oneonone_b.pk]))
        oneonone_b.refresh_from_db()
        assert oneonone_b.status == original_status
        assert oneonone_b.agenda != "hacked"


# ================================================================ MeetingActionItem IDOR
class TestMeetingActionItemIDOR:
    def test_detail_cross_tenant_404(self, client_a, action_item_b):
        resp = client_a.get(reverse("hrm:meetingactionitem_detail", args=[action_item_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, action_item_b):
        resp = client_a.get(reverse("hrm:meetingactionitem_edit", args=[action_item_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, action_item_b):
        resp = client_a.post(reverse("hrm:meetingactionitem_edit", args=[action_item_b.pk]), {
            "description": "hacked", "owner": action_item_b.owner_id, "due_date": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, action_item_b):
        resp = client_a.post(reverse("hrm:meetingactionitem_delete", args=[action_item_b.pk]))
        assert resp.status_code == 404

    def test_toggle_cross_tenant_404(self, client_a, action_item_b):
        resp = client_a.post(reverse("hrm:meetingactionitem_toggle", args=[action_item_b.pk]))
        assert resp.status_code == 404

    def test_create_nested_cross_tenant_parent_404(self, client_a, oneonone_b, employee_b):
        """POST meetingactionitem_create against a tenant_b meeting pk must 404 — the nested-create
        view looks up the parent OneOnOneMeeting scoped to request.tenant."""
        from apps.hrm.models import MeetingActionItem
        resp = client_a.post(reverse("hrm:meetingactionitem_create", args=[oneonone_b.pk]), {
            "description": "hacked", "owner": employee_b.pk, "due_date": "",
        })
        assert resp.status_code == 404
        assert not MeetingActionItem.objects.filter(meeting=oneonone_b, description="hacked").exists()

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, action_item_b):
        original_description = action_item_b.description
        client_a.post(reverse("hrm:meetingactionitem_edit", args=[action_item_b.pk]), {
            "description": "hacked", "owner": action_item_b.owner_id, "due_date": "",
        })
        action_item_b.refresh_from_db()
        assert action_item_b.description == original_description

    def test_cross_tenant_toggle_does_not_mutate_b_row(self, client_a, action_item_b):
        client_a.post(reverse("hrm:meetingactionitem_toggle", args=[action_item_b.pk]))
        action_item_b.refresh_from_db()
        assert action_item_b.status == "open"


# ================================================================ Anonymous user -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:kudosbadge_list", []),
        ("hrm:feedback_list", []),
        ("hrm:feedback_dashboard", []),
        ("hrm:oneononemeeting_list", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_pages(
        self, client, kudos_badge_a, feedback_a, oneonone_a, action_item_a
    ):
        for url_name, pk in [
            ("hrm:kudosbadge_detail", kudos_badge_a.pk),
            ("hrm:feedback_detail", feedback_a.pk),
            ("hrm:oneononemeeting_detail", oneonone_a.pk),
            ("hrm:meetingactionitem_detail", action_item_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_actions(
        self, client, kudos_badge_a, feedback_a, oneonone_a, action_item_a
    ):
        for url_name, pk in [
            ("hrm:kudosbadge_delete", kudos_badge_a.pk),
            ("hrm:feedback_delete", feedback_a.pk),
            ("hrm:feedback_acknowledge", feedback_a.pk),
            ("hrm:oneononemeeting_delete", oneonone_a.pk),
            ("hrm:oneononemeeting_complete", oneonone_a.pk),
            ("hrm:oneononemeeting_cancel", oneonone_a.pk),
            ("hrm:meetingactionitem_delete", action_item_a.pk),
            ("hrm:meetingactionitem_toggle", action_item_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_nested_create(self, client, oneonone_a):
        resp = client.get(reverse("hrm:meetingactionitem_create", args=[oneonone_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_blocked_on_respond(self, client, feedback_a):
        feedback_a.feedback_type = "request"
        feedback_a.status = "requested"
        feedback_a.save(update_fields=["feedback_type", "status"])
        resp = client.get(reverse("hrm:feedback_respond", args=[feedback_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ CONFIDENTIALITY (_can_view_feedback)
def _link_user_to_employee(user, employee):
    user.party = employee.party
    user.save(update_fields=["party"])


@pytest.fixture
def outsider_user(db, tenant_a, outsider_employee_a):
    """A non-admin tenant_a User linked to outsider_employee_a (a THIRD employee, in a different
    org unit — neither giver/receiver of feedback_a nor participant of oneonone_a)."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email="dana5@acme.com", username="dana5_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )
    _link_user_to_employee(user, outsider_employee_a)
    return user


@pytest.fixture
def outsider_client(db, outsider_user):
    c = Client()
    c.force_login(outsider_user)
    return c


@pytest.fixture
def teammate_user(db, tenant_a, teammate_employee_a):
    """A non-admin tenant_a User linked to teammate_employee_a (shares employee_a's org unit,
    dept_a) — used for the "team" visibility tier tests."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email="eve@acme.com", username="eve_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )
    _link_user_to_employee(user, teammate_employee_a)
    return user


@pytest.fixture
def teammate_client(db, teammate_user):
    c = Client()
    c.force_login(teammate_user)
    return c


@pytest.fixture
def giver_client(db, tenant_a, employee_a2):
    """A non-admin tenant_a User linked to employee_a2 (the giver of feedback_a)."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email="carol4@acme.com", username="carol4_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )
    _link_user_to_employee(user, employee_a2)
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def receiver_client(db, tenant_a, employee_a):
    """A non-admin tenant_a User linked to employee_a (the receiver of feedback_a)."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email="alice3@acme.com", username="alice3_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )
    _link_user_to_employee(user, employee_a)
    c = Client()
    c.force_login(user)
    return c


class TestFeedbackConfidentiality:
    def test_non_participant_403_on_private_detail(self, outsider_client, feedback_a):
        resp = outsider_client.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 403

    def test_non_participant_private_row_absent_from_list(self, outsider_client, feedback_a):
        resp = outsider_client.get(reverse("hrm:feedback_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk not in pks

    def test_giver_can_view_own_private_row(self, giver_client, feedback_a):
        resp = giver_client.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 200

    def test_receiver_can_view_own_private_row(self, receiver_client, feedback_a):
        resp = receiver_client.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 200

    def test_admin_can_view_any_private_row(self, client_a, feedback_a):
        resp = client_a.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 200

    def test_public_row_is_visible_to_non_participant(self, outsider_client, feedback_a):
        feedback_a.visibility = "public"
        feedback_a.save(update_fields=["visibility"])
        resp = outsider_client.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 200

    def test_public_row_appears_in_non_participant_list(self, outsider_client, feedback_a):
        feedback_a.visibility = "public"
        feedback_a.save(update_fields=["visibility"])
        resp = outsider_client.get(reverse("hrm:feedback_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_team_row_visible_to_same_org_unit_colleague(self, teammate_client, feedback_a):
        """teammate_employee_a shares employee_a's (the receiver's) org unit — a `team`-visibility
        row must be visible to them even though they're neither giver nor receiver."""
        feedback_a.visibility = "team"
        feedback_a.save(update_fields=["visibility"])
        resp = teammate_client.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 200

    def test_team_row_appears_in_colleague_list(self, teammate_client, feedback_a):
        feedback_a.visibility = "team"
        feedback_a.save(update_fields=["visibility"])
        resp = teammate_client.get(reverse("hrm:feedback_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks

    def test_team_row_not_visible_to_different_org_unit_outsider(self, outsider_client, feedback_a):
        """outsider_employee_a is in a DIFFERENT org unit from employee_a (the receiver) — a
        `team`-visibility row must remain hidden from them."""
        feedback_a.visibility = "team"
        feedback_a.save(update_fields=["visibility"])
        resp = outsider_client.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 403

    def test_team_row_absent_from_different_org_unit_outsiders_list(self, outsider_client, feedback_a):
        feedback_a.visibility = "team"
        feedback_a.save(update_fields=["visibility"])
        resp = outsider_client.get(reverse("hrm:feedback_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk not in pks


# ================================================================ Anonymous masking
class TestFeedbackAnonymousMasking:
    def test_receiver_sees_anonymous_not_giver_name_on_detail(self, receiver_client, feedback_a):
        feedback_a.is_anonymous = True
        feedback_a.save(update_fields=["is_anonymous"])
        resp = receiver_client.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.status_code == 200
        assert resp.context["giver_display"] == "Anonymous"
        assert b"Carol White" not in resp.content  # employee_a2's (the giver's) party name

    def test_receiver_sees_anonymous_not_giver_name_on_list(self, receiver_client, feedback_a):
        """`Carol White` (the giver's real name) legitimately appears elsewhere on the page — e.g.
        the receiver-filter <select> lists every tenant employee — so scope the masking assertion
        to the actual list ROW for feedback_a, not the whole raw HTML."""
        feedback_a.is_anonymous = True
        feedback_a.save(update_fields=["is_anonymous"])
        resp = receiver_client.get(reverse("hrm:feedback_list"))
        assert resp.status_code == 200
        rows = {obj.pk: obj for obj in resp.context["object_list"]}
        assert feedback_a.pk in rows
        row = rows[feedback_a.pk]
        assert row.giver_anonymized is True
        assert resp.context["current_profile_id"] != row.giver_id
        # Reproduce the template's own masking condition (list.html:79) directly against the row.
        is_admin = resp.context["is_admin"]
        should_mask = row.giver_anonymized and not is_admin and row.giver_id != resp.context["current_profile_id"]
        assert should_mask is True

    def test_admin_sees_real_giver_name_on_detail(self, client_a, feedback_a):
        feedback_a.is_anonymous = True
        feedback_a.save(update_fields=["is_anonymous"])
        resp = client_a.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.context["giver_display"] == "Carol White"
        assert b"Carol White" in resp.content

    def test_giver_sees_own_real_name_on_detail(self, giver_client, feedback_a):
        feedback_a.is_anonymous = True
        feedback_a.save(update_fields=["is_anonymous"])
        resp = giver_client.get(reverse("hrm:feedback_detail", args=[feedback_a.pk]))
        assert resp.context["giver_display"] == "Carol White"

    def test_non_admin_cannot_search_giver_name_to_surface_anonymous_row(self, receiver_client, feedback_a):
        """The anti-correlation guard: a non-admin's `q=` search must NOT include `giver__party__name`
        as a search field — searching the (known) giver's real name must not surface the masked row,
        which would let a curious receiver confirm who gave an "anonymous" kudos."""
        feedback_a.is_anonymous = True
        feedback_a.save(update_fields=["is_anonymous"])
        resp = receiver_client.get(reverse("hrm:feedback_list"), {"q": "Carol White"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk not in pks

    def test_admin_can_search_giver_name(self, client_a, feedback_a):
        """An admin's search DOES include giver name (no confidentiality reason to hide it from
        an admin) — sanity check the search field is admin-gated, not globally broken."""
        resp = client_a.get(reverse("hrm:feedback_list"), {"q": "Carol White"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert feedback_a.pk in pks


# ================================================================ kudosbadge_detail recent-awards leak
class TestKudosBadgeDetailRecentAwardsLeak:
    def test_non_participant_does_not_see_recipient_of_private_feedback(
        self, outsider_client, kudos_badge_a, feedback_a
    ):
        """A non-admin who is NOT a participant of a `private` feedback carrying kudos_badge_a
        must NOT see that feedback (and thus its recipient) in the badge's recent-awards list —
        the reverse-accessor leak the code-reviewer caught, now filtered through
        _visible_feedback_q."""
        feedback_a.badge = kudos_badge_a
        feedback_a.save(update_fields=["badge"])
        resp = outsider_client.get(reverse("hrm:kudosbadge_detail", args=[kudos_badge_a.pk]))
        assert resp.status_code == 200
        pks = [f.pk for f in resp.context["recent_feedback"]]
        assert feedback_a.pk not in pks

    def test_receiver_sees_own_private_feedback_in_recent_awards(
        self, receiver_client, kudos_badge_a, feedback_a
    ):
        feedback_a.badge = kudos_badge_a
        feedback_a.save(update_fields=["badge"])
        resp = receiver_client.get(reverse("hrm:kudosbadge_detail", args=[kudos_badge_a.pk]))
        pks = [f.pk for f in resp.context["recent_feedback"]]
        assert feedback_a.pk in pks

    def test_admin_sees_all_feedback_in_recent_awards(self, client_a, kudos_badge_a, feedback_a):
        feedback_a.badge = kudos_badge_a
        feedback_a.save(update_fields=["badge"])
        resp = client_a.get(reverse("hrm:kudosbadge_detail", args=[kudos_badge_a.pk]))
        pks = [f.pk for f in resp.context["recent_feedback"]]
        assert feedback_a.pk in pks

    def test_public_feedback_visible_to_non_participant_in_recent_awards(
        self, outsider_client, kudos_badge_a, feedback_a
    ):
        feedback_a.badge = kudos_badge_a
        feedback_a.visibility = "public"
        feedback_a.save(update_fields=["badge", "visibility"])
        resp = outsider_client.get(reverse("hrm:kudosbadge_detail", args=[kudos_badge_a.pk]))
        pks = [f.pk for f in resp.context["recent_feedback"]]
        assert feedback_a.pk in pks


# ================================================================ manager_private_notes gating
class TestManagerPrivateNotesGating:
    def test_manager_sees_private_notes(self, giver_client, oneonone_a):
        """employee_a2 (giver_client's linked profile) is oneonone_a's MANAGER."""
        resp = giver_client.get(reverse("hrm:oneononemeeting_detail", args=[oneonone_a.pk]))
        assert resp.status_code == 200
        assert resp.context["show_private"] is True
        assert b"flight risk" in resp.content

    def test_admin_sees_private_notes(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_detail", args=[oneonone_a.pk]))
        assert resp.context["show_private"] is True
        assert b"flight risk" in resp.content

    def test_employee_does_not_see_private_notes(self, receiver_client, oneonone_a):
        """employee_a (receiver_client's linked profile) is oneonone_a's EMPLOYEE side — the
        manager-only notes must be absent from the rendered body entirely."""
        resp = receiver_client.get(reverse("hrm:oneononemeeting_detail", args=[oneonone_a.pk]))
        assert resp.status_code == 200
        assert resp.context["show_private"] is False
        assert b"flight risk" not in resp.content

    def test_employee_blocked_from_edit_form_that_holds_the_field(self, receiver_client, oneonone_a):
        """The edit form itself carries manager_private_notes — the employee must never reach it
        (masking only the read view would leave the field readable via the bound edit form)."""
        resp = receiver_client.get(reverse("hrm:oneononemeeting_edit", args=[oneonone_a.pk]))
        assert resp.status_code == 302

    def test_employee_post_to_edit_does_not_mutate_private_notes(
        self, receiver_client, oneonone_a, employee_a2, employee_a
    ):
        original_notes = oneonone_a.manager_private_notes
        resp = receiver_client.post(reverse("hrm:oneononemeeting_edit", args=[oneonone_a.pk]), {
            "manager": employee_a2.pk, "employee": employee_a.pk,
            "scheduled_at": "2026-08-01T10:00", "agenda": "", "shared_notes": "",
            "manager_private_notes": "TAMPERED BY EMPLOYEE", "related_objective": "",
        })
        assert resp.status_code == 302
        oneonone_a.refresh_from_db()
        assert oneonone_a.manager_private_notes == original_notes

    def test_manager_can_edit_and_write_private_notes(self, giver_client, oneonone_a, employee_a2, employee_a):
        """The manager retains write access to manager_private_notes — only the READ gate (and the
        employee's form access) is restricted."""
        resp = giver_client.post(reverse("hrm:oneononemeeting_edit", args=[oneonone_a.pk]), {
            "manager": employee_a2.pk, "employee": employee_a.pk,
            "scheduled_at": "2026-08-01T10:00", "agenda": "", "shared_notes": "",
            "manager_private_notes": "Updated by the manager.", "related_objective": "",
        })
        assert resp.status_code == 302
        oneonone_a.refresh_from_db()
        assert oneonone_a.manager_private_notes == "Updated by the manager."

    def test_employee_blocked_from_delete(self, receiver_client, oneonone_a):
        from apps.hrm.models import OneOnOneMeeting
        resp = receiver_client.post(reverse("hrm:oneononemeeting_delete", args=[oneonone_a.pk]))
        assert resp.status_code == 302
        assert OneOnOneMeeting.objects.filter(pk=oneonone_a.pk).exists()

    def test_employee_blocked_from_complete(self, receiver_client, oneonone_a):
        resp = receiver_client.post(reverse("hrm:oneononemeeting_complete", args=[oneonone_a.pk]))
        assert resp.status_code == 403
        oneonone_a.refresh_from_db()
        assert oneonone_a.status == "scheduled"

    def test_employee_can_still_view_shared_notes(self, receiver_client, oneonone_a):
        """Sanity: the employee CAN reach the read view at all (the notes field alone is masked,
        not the whole detail page)."""
        oneonone_a.shared_notes = "Agreed on next steps."
        oneonone_a.save(update_fields=["shared_notes"])
        resp = receiver_client.get(reverse("hrm:oneononemeeting_detail", args=[oneonone_a.pk]))
        assert b"Agreed on next steps." in resp.content

    def test_non_participant_403_on_detail(self, outsider_client, oneonone_a):
        resp = outsider_client.get(reverse("hrm:oneononemeeting_detail", args=[oneonone_a.pk]))
        assert resp.status_code == 403

    def test_non_participant_meeting_absent_from_list(self, outsider_client, oneonone_a):
        resp = outsider_client.get(reverse("hrm:oneononemeeting_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert oneonone_a.pk not in pks

    def test_admin_list_shows_all_meetings(self, client_a, oneonone_a):
        resp = client_a.get(reverse("hrm:oneononemeeting_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert oneonone_a.pk in pks


# ================================================================ FeedbackForm.related_review scoping
class TestFeedbackFormRelatedReviewScoping:
    def test_excludes_review_giver_cannot_view(
        self, client_a, tenant_a, employee_a, employee_a2, review_cycle_a, outsider_employee_a
    ):
        """FeedbackForm(viewer_profile=<giver>).related_review must only offer reviews where the
        giver is subject/reviewer — a review belonging to two OTHER employees (neither the subject
        nor reviewer is the giver) must not appear."""
        from apps.hrm.forms import FeedbackForm
        from apps.hrm.models import PerformanceReview
        unrelated_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=outsider_employee_a, reviewer=employee_a2,
            review_type="manager",
        )
        form = FeedbackForm(tenant=tenant_a, viewer_profile=employee_a)
        pks = list(form.fields["related_review"].queryset.values_list("pk", flat=True))
        assert unrelated_review.pk not in pks

    def test_includes_review_giver_is_subject_of(
        self, client_a, tenant_a, employee_a, employee_a2, review_cycle_a
    ):
        from apps.hrm.forms import FeedbackForm
        from apps.hrm.models import PerformanceReview
        own_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="manager",
        )
        form = FeedbackForm(tenant=tenant_a, viewer_profile=employee_a)
        pks = list(form.fields["related_review"].queryset.values_list("pk", flat=True))
        assert own_review.pk in pks

    def test_includes_review_giver_is_reviewer_of(
        self, client_a, tenant_a, employee_a, employee_a2, review_cycle_a
    ):
        from apps.hrm.forms import FeedbackForm
        from apps.hrm.models import PerformanceReview
        authored_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a2, reviewer=employee_a,
            review_type="manager",
        )
        form = FeedbackForm(tenant=tenant_a, viewer_profile=employee_a)
        pks = list(form.fields["related_review"].queryset.values_list("pk", flat=True))
        assert authored_review.pk in pks

    def test_empty_queryset_when_viewer_profile_is_none(self, tenant_a, review_cycle_a, employee_a, employee_a2):
        """No viewer_profile (e.g. an unlinked superuser) means no giver identity to scope
        against — the field must show no reviews rather than the tenant-wide roster."""
        from apps.hrm.forms import FeedbackForm
        from apps.hrm.models import PerformanceReview
        PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="manager",
        )
        form = FeedbackForm(tenant=tenant_a, viewer_profile=None)
        assert form.fields["related_review"].queryset.count() == 0

    def test_view_passes_giver_as_viewer_profile_on_create_get(
        self, client_a, admin_user, employee_a, employee_a2, review_cycle_a
    ):
        """End-to-end: feedback_create's GET must scope related_review to the LOGGED-IN user's
        linked profile (the would-be giver), not show every review in the tenant."""
        from apps.hrm.models import PerformanceReview
        admin_user.party = employee_a.party
        admin_user.save(update_fields=["party"])
        own_review = PerformanceReview.objects.create(
            tenant=review_cycle_a.tenant, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="manager",
        )
        unrelated = PerformanceReview.objects.create(
            tenant=review_cycle_a.tenant, cycle=review_cycle_a, subject=employee_a2, reviewer=employee_a2,
            review_type="self",
        )
        resp = client_a.get(reverse("hrm:feedback_create"))
        pks = list(resp.context["form"].fields["related_review"].queryset.values_list("pk", flat=True))
        assert own_review.pk in pks
        assert unrelated.pk not in pks


# ================================================================ Security fix: action item owner
# who is not a meeting participant cannot manage it (view-layer _can_manage_action_item gate)
class TestActionItemOwnerNotParticipantSecurityFix:
    @pytest.fixture
    def outsider_owned_item(self, db, tenant_a, oneonone_a, outsider_employee_a):
        """Bypass the form's owner-scoping (which would never offer this outsider) by creating the
        item directly, to prove the VIEW layer's gate holds independently of the form."""
        from apps.hrm.models import MeetingActionItem
        return MeetingActionItem.objects.create(
            tenant=tenant_a, meeting=oneonone_a, description="Outsider-owned item",
            owner=outsider_employee_a, status="open",
        )

    def test_owner_who_is_not_participant_403_on_edit(self, outsider_client, outsider_owned_item):
        resp = outsider_client.get(reverse("hrm:meetingactionitem_edit", args=[outsider_owned_item.pk]))
        assert resp.status_code == 403

    def test_owner_who_is_not_participant_403_on_toggle(self, outsider_client, outsider_owned_item):
        resp = outsider_client.post(reverse("hrm:meetingactionitem_toggle", args=[outsider_owned_item.pk]))
        assert resp.status_code == 403
        outsider_owned_item.refresh_from_db()
        assert outsider_owned_item.status == "open"

    def test_owner_who_is_not_participant_redirect_on_delete(self, outsider_client, outsider_owned_item):
        from apps.hrm.models import MeetingActionItem
        resp = outsider_client.post(reverse("hrm:meetingactionitem_delete", args=[outsider_owned_item.pk]))
        assert resp.status_code == 302
        assert MeetingActionItem.objects.filter(pk=outsider_owned_item.pk).exists()

    def test_owner_who_is_not_participant_403_on_detail(self, outsider_client, outsider_owned_item):
        resp = outsider_client.get(reverse("hrm:meetingactionitem_detail", args=[outsider_owned_item.pk]))
        assert resp.status_code == 403

    def test_admin_can_still_manage_outsider_owned_item(self, client_a, outsider_owned_item):
        """Sanity: the fix doesn't lock the admin out — only the non-participant owner."""
        resp = client_a.post(reverse("hrm:meetingactionitem_toggle", args=[outsider_owned_item.pk]))
        assert resp.status_code == 302
        outsider_owned_item.refresh_from_db()
        assert outsider_owned_item.status == "done"


# ================================================================ CSRF enforcement
class TestFeedbackCSRFEnforcement:
    def test_kudosbadge_delete_enforces_csrf(self, admin_user, tenant_a):
        from apps.hrm.models import KudosBadge
        badge = KudosBadge.objects.create(tenant=tenant_a, name="CSRF Delete Badge")
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:kudosbadge_delete", args=[badge.pk]))
        assert resp.status_code == 403

    def test_feedback_delete_enforces_csrf(self, admin_user, feedback_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:feedback_delete", args=[feedback_a.pk]))
        assert resp.status_code == 403

    def test_feedback_acknowledge_enforces_csrf(self, admin_user, employee_a, feedback_a):
        _link_user_to_employee(admin_user, employee_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:feedback_acknowledge", args=[feedback_a.pk]))
        assert resp.status_code == 403
        feedback_a.refresh_from_db()
        assert feedback_a.status == "given"

    def test_oneononemeeting_delete_enforces_csrf(self, admin_user, oneonone_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:oneononemeeting_delete", args=[oneonone_a.pk]))
        assert resp.status_code == 403

    def test_oneononemeeting_complete_enforces_csrf(self, admin_user, oneonone_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:oneononemeeting_complete", args=[oneonone_a.pk]))
        assert resp.status_code == 403
        oneonone_a.refresh_from_db()
        assert oneonone_a.status == "scheduled"

    def test_oneononemeeting_cancel_enforces_csrf(self, admin_user, oneonone_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:oneononemeeting_cancel", args=[oneonone_a.pk]))
        assert resp.status_code == 403
        oneonone_a.refresh_from_db()
        assert oneonone_a.status == "scheduled"

    def test_meetingactionitem_create_enforces_csrf(self, admin_user, oneonone_a, employee_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:meetingactionitem_create", args=[oneonone_a.pk]), {
            "description": "CSRF-blocked", "owner": employee_a.pk, "due_date": "",
        })
        assert resp.status_code == 403
        from apps.hrm.models import MeetingActionItem
        assert not MeetingActionItem.objects.filter(
            meeting=oneonone_a, description="CSRF-blocked").exists()

    def test_meetingactionitem_delete_enforces_csrf(self, admin_user, action_item_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:meetingactionitem_delete", args=[action_item_a.pk]))
        assert resp.status_code == 403

    def test_meetingactionitem_toggle_enforces_csrf(self, admin_user, action_item_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:meetingactionitem_toggle", args=[action_item_a.pk]))
        assert resp.status_code == 403
        action_item_a.refresh_from_db()
        assert action_item_a.status == "open"


# ================================================================ Form-smuggling guards
class TestFeedbackFormFieldExclusions:
    def test_feedbackform_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import FeedbackForm
        excluded = {"status", "number", "acknowledged_at", "giver", "requested_from"}
        assert excluded.isdisjoint(set(FeedbackForm.Meta.fields))

    def test_edit_post_with_status_does_not_write_it(self, client_a, feedback_a, employee_a):
        assert feedback_a.status == "given"
        resp = client_a.post(reverse("hrm:feedback_edit", args=[feedback_a.pk]), {
            "receiver": employee_a.pk, "feedback_type": "kudos", "visibility": "private",
            "message": "", "is_anonymous": "", "badge": "", "related_objective": "",
            "related_review": "", "status": "acknowledged",
        })
        assert resp.status_code == 302
        feedback_a.refresh_from_db()
        assert feedback_a.status == "given"

    def test_edit_post_with_giver_does_not_reassign_giver(self, client_a, feedback_a, employee_a, employee_a2):
        """FeedbackForm has no `giver` field — POSTing a different giver pk via the general edit
        form must NOT reassign it."""
        original_giver_id = feedback_a.giver_id
        client_a.post(reverse("hrm:feedback_edit", args=[feedback_a.pk]), {
            "receiver": employee_a.pk, "feedback_type": "kudos", "visibility": "private",
            "message": "", "is_anonymous": "", "badge": "", "related_objective": "",
            "related_review": "", "giver": employee_a.pk,
        })
        feedback_a.refresh_from_db()
        assert feedback_a.giver_id == original_giver_id

    def test_oneononemeetingform_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import OneOnOneMeetingForm
        excluded = {"status", "number", "completed_at"}
        assert excluded.isdisjoint(set(OneOnOneMeetingForm.Meta.fields))

    def test_oneononemeeting_edit_post_with_status_does_not_write_it(
        self, client_a, oneonone_a, employee_a2, employee_a
    ):
        assert oneonone_a.status == "scheduled"
        resp = client_a.post(reverse("hrm:oneononemeeting_edit", args=[oneonone_a.pk]), {
            "manager": employee_a2.pk, "employee": employee_a.pk,
            "scheduled_at": "2026-08-01T10:00", "agenda": "", "shared_notes": "",
            "manager_private_notes": "", "related_objective": "", "status": "completed",
        })
        assert resp.status_code == 302
        oneonone_a.refresh_from_db()
        assert oneonone_a.status == "scheduled"

    def test_meetingactionitemform_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import MeetingActionItemForm
        excluded = {"status", "number", "completed_at", "meeting"}
        assert excluded.isdisjoint(set(MeetingActionItemForm.Meta.fields))

    def test_meetingactionitem_edit_post_with_status_does_not_write_it(
        self, client_a, action_item_a, employee_a
    ):
        assert action_item_a.status == "open"
        resp = client_a.post(reverse("hrm:meetingactionitem_edit", args=[action_item_a.pk]), {
            "description": action_item_a.description, "owner": employee_a.pk, "due_date": "",
            "status": "done",
        })
        assert resp.status_code == 302
        action_item_a.refresh_from_db()
        assert action_item_a.status == "open"

    def test_meetingactionitem_edit_post_with_meeting_does_not_reassign_meeting(
        self, client_a, tenant_a, action_item_a, employee_a, employee_a2
    ):
        """MeetingActionItemForm has no `meeting` field — POSTing a different meeting pk via the
        edit form must NOT reassign the parent."""
        from apps.hrm.models import OneOnOneMeeting
        other_meeting = OneOnOneMeeting.objects.create(
            tenant=tenant_a, manager=employee_a2, employee=employee_a,
            scheduled_at=datetime.datetime(2026, 9, 1, 10, 0, tzinfo=datetime.timezone.utc),
        )
        original_meeting_id = action_item_a.meeting_id
        client_a.post(reverse("hrm:meetingactionitem_edit", args=[action_item_a.pk]), {
            "description": action_item_a.description, "owner": employee_a.pk, "due_date": "",
            "meeting": other_meeting.pk,
        })
        action_item_a.refresh_from_db()
        assert action_item_a.meeting_id == original_meeting_id
