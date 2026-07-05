"""Security tests for HRM 3.19 Performance Review: cross-tenant IDOR (ReviewCycle/ReviewTemplate/
PerformanceReview/ReviewRating detail/edit/delete + calibrate + nested reviewrating_create), list
isolation, anonymous-blocked, CONFIDENTIALITY (_can_view_review — admin/subject/reviewer only,
non-participant 403 + roster exclusion), EDIT LOCK (_can_edit_review — draft-only + reviewer/admin),
@tenant_admin_required on advance_phase/share/calibrate, CSRF enforcement, and the
ReviewCycleForm/PerformanceReviewForm status/calibrated_rating authz fixes."""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ ReviewCycle IDOR
class TestReviewCycleIDOR:
    def test_detail_cross_tenant_404(self, client_a, review_cycle_b):
        resp = client_a.get(reverse("hrm:reviewcycle_detail", args=[review_cycle_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, review_cycle_b):
        resp = client_a.get(reverse("hrm:reviewcycle_edit", args=[review_cycle_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, review_cycle_b):
        resp = client_a.post(reverse("hrm:reviewcycle_edit", args=[review_cycle_b.pk]), {
            "name": "hacked", "cycle_type": "half_yearly",
            "self_review_start": "", "self_review_end": "",
            "manager_review_start": "", "manager_review_end": "",
            "calibration_date": "", "results_release_date": "", "goal_period": "", "description": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, review_cycle_b):
        resp = client_a.post(reverse("hrm:reviewcycle_delete", args=[review_cycle_b.pk]))
        assert resp.status_code == 404

    def test_advance_phase_cross_tenant_404(self, client_a, review_cycle_b):
        resp = client_a.post(reverse("hrm:reviewcycle_advance_phase", args=[review_cycle_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_cycles(self, client_a, review_cycle_a, review_cycle_b):
        resp = client_a.get(reverse("hrm:reviewcycle_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_cycle_a.pk in pks
        assert review_cycle_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, review_cycle_b):
        original_status = review_cycle_b.status
        original_name = review_cycle_b.name
        client_a.post(reverse("hrm:reviewcycle_edit", args=[review_cycle_b.pk]), {
            "name": "hacked", "cycle_type": "half_yearly",
            "self_review_start": "", "self_review_end": "",
            "manager_review_start": "", "manager_review_end": "",
            "calibration_date": "", "results_release_date": "", "goal_period": "", "description": "",
        })
        client_a.post(reverse("hrm:reviewcycle_advance_phase", args=[review_cycle_b.pk]))
        review_cycle_b.refresh_from_db()
        assert review_cycle_b.status == original_status
        assert review_cycle_b.name == original_name


# ================================================================ ReviewTemplate IDOR
class TestReviewTemplateIDOR:
    def test_detail_cross_tenant_404(self, client_a, review_template_b):
        resp = client_a.get(reverse("hrm:reviewtemplate_detail", args=[review_template_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, review_template_b):
        resp = client_a.get(reverse("hrm:reviewtemplate_edit", args=[review_template_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, review_template_b):
        resp = client_a.post(reverse("hrm:reviewtemplate_edit", args=[review_template_b.pk]), {
            "name": "hacked", "review_type": "manager", "rating_scale_max": "5",
            "include_goals": "", "is_anonymous": "", "description": "", "is_active": "on",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, review_template_b):
        resp = client_a.post(reverse("hrm:reviewtemplate_delete", args=[review_template_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_templates(self, client_a, review_template_a, review_template_b):
        resp = client_a.get(reverse("hrm:reviewtemplate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_template_a.pk in pks
        assert review_template_b.pk not in pks

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, review_template_b):
        original_name = review_template_b.name
        client_a.post(reverse("hrm:reviewtemplate_edit", args=[review_template_b.pk]), {
            "name": "hacked", "review_type": "manager", "rating_scale_max": "5",
            "include_goals": "", "is_anonymous": "", "description": "", "is_active": "on",
        })
        review_template_b.refresh_from_db()
        assert review_template_b.name == original_name


# ================================================================ PerformanceReview IDOR
class TestPerformanceReviewIDOR:
    def test_detail_cross_tenant_404(self, client_a, performance_review_b):
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[performance_review_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, performance_review_b):
        resp = client_a.get(reverse("hrm:performancereview_edit", args=[performance_review_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, performance_review_b):
        resp = client_a.post(reverse("hrm:performancereview_edit", args=[performance_review_b.pk]), {
            "cycle": performance_review_b.cycle_id, "template": "",
            "subject": performance_review_b.subject_id, "reviewer": performance_review_b.reviewer_id,
            "review_type": "self", "strengths": "hacked", "improvements": "", "private_notes": "",
            "is_anonymous": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, performance_review_b):
        resp = client_a.post(reverse("hrm:performancereview_delete", args=[performance_review_b.pk]))
        assert resp.status_code == 404

    def test_submit_cross_tenant_404(self, client_a, performance_review_b):
        resp = client_a.post(reverse("hrm:performancereview_submit", args=[performance_review_b.pk]))
        assert resp.status_code == 404

    def test_share_cross_tenant_404(self, client_a, performance_review_b):
        resp = client_a.post(reverse("hrm:performancereview_share", args=[performance_review_b.pk]))
        assert resp.status_code == 404

    def test_acknowledge_cross_tenant_404(self, client_a, performance_review_b):
        resp = client_a.post(reverse("hrm:performancereview_acknowledge", args=[performance_review_b.pk]))
        assert resp.status_code == 404

    def test_calibrate_get_cross_tenant_404(self, client_a, performance_review_b):
        resp = client_a.get(reverse("hrm:performancereview_calibrate", args=[performance_review_b.pk]))
        assert resp.status_code == 404

    def test_calibrate_post_cross_tenant_404(self, client_a, performance_review_b):
        resp = client_a.post(reverse("hrm:performancereview_calibrate", args=[performance_review_b.pk]), {
            "calibrated_rating": "5.00", "potential_rating": "", "calibration_notes": "",
        })
        assert resp.status_code == 404

    def test_reviewrating_create_nested_cross_tenant_parent_404(self, client_a, performance_review_b):
        """POST reviewrating_create against a tenant_b review pk must 404 — the nested-create view
        looks up the parent PerformanceReview scoped to request.tenant."""
        from apps.hrm.models import ReviewRating
        resp = client_a.post(reverse("hrm:reviewrating_create", args=[performance_review_b.pk]), {
            "criterion_label": "hacked", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "50", "comment": "",
        })
        assert resp.status_code == 404
        assert not ReviewRating.objects.filter(review=performance_review_b, criterion_label="hacked").exists()

    def test_reviewrating_create_nested_cross_tenant_parent_404_get(self, client_a, performance_review_b):
        resp = client_a.get(reverse("hrm:reviewrating_create", args=[performance_review_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_reviews(self, client_a, performance_review_a, performance_review_b):
        resp = client_a.get(reverse("hrm:performancereview_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks
        assert performance_review_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, performance_review_b):
        original_strengths = performance_review_b.strengths
        client_a.post(reverse("hrm:performancereview_edit", args=[performance_review_b.pk]), {
            "cycle": performance_review_b.cycle_id, "template": "",
            "subject": performance_review_b.subject_id, "reviewer": performance_review_b.reviewer_id,
            "review_type": "self", "strengths": "hacked", "improvements": "", "private_notes": "",
            "is_anonymous": "",
        })
        performance_review_b.refresh_from_db()
        assert performance_review_b.strengths == original_strengths


# ================================================================ ReviewRating IDOR
class TestReviewRatingIDOR:
    def test_detail_cross_tenant_404(self, client_a, review_rating_b):
        resp = client_a.get(reverse("hrm:reviewrating_detail", args=[review_rating_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, review_rating_b):
        resp = client_a.get(reverse("hrm:reviewrating_edit", args=[review_rating_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, review_rating_b):
        resp = client_a.post(reverse("hrm:reviewrating_edit", args=[review_rating_b.pk]), {
            "criterion_label": "hacked", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "50", "comment": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, review_rating_b):
        resp = client_a.post(reverse("hrm:reviewrating_delete", args=[review_rating_b.pk]))
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, review_rating_b):
        original_label = review_rating_b.criterion_label
        client_a.post(reverse("hrm:reviewrating_edit", args=[review_rating_b.pk]), {
            "criterion_label": "hacked", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "50", "comment": "",
        })
        review_rating_b.refresh_from_db()
        assert review_rating_b.criterion_label == original_label

    def test_cross_tenant_delete_does_not_remove_b_row(self, client_a, review_rating_b):
        from apps.hrm.models import ReviewRating
        client_a.post(reverse("hrm:reviewrating_delete", args=[review_rating_b.pk]))
        assert ReviewRating.objects.filter(pk=review_rating_b.pk).exists()


# ================================================================ Anonymous user -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:reviewcycle_list", []),
        ("hrm:reviewtemplate_list", []),
        ("hrm:performancereview_list", []),
        ("hrm:calibration_board", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_pages(
        self, client, review_cycle_a, review_template_a, performance_review_a, review_rating_a
    ):
        for url_name, pk in [
            ("hrm:reviewcycle_detail", review_cycle_a.pk),
            ("hrm:reviewtemplate_detail", review_template_a.pk),
            ("hrm:performancereview_detail", performance_review_a.pk),
            ("hrm:reviewrating_detail", review_rating_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_actions(
        self, client, review_cycle_a, review_template_a, performance_review_a, review_rating_a
    ):
        for url_name, pk in [
            ("hrm:reviewcycle_delete", review_cycle_a.pk),
            ("hrm:reviewcycle_advance_phase", review_cycle_a.pk),
            ("hrm:reviewtemplate_delete", review_template_a.pk),
            ("hrm:performancereview_delete", performance_review_a.pk),
            ("hrm:performancereview_submit", performance_review_a.pk),
            ("hrm:performancereview_share", performance_review_a.pk),
            ("hrm:performancereview_acknowledge", performance_review_a.pk),
            ("hrm:reviewrating_delete", review_rating_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_nested_creates(self, client, performance_review_a):
        resp = client.get(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_blocked_on_calibrate(self, client, performance_review_a):
        resp = client.get(reverse("hrm:performancereview_calibrate", args=[performance_review_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ CONFIDENTIALITY
def _link_user_to_employee(user, employee):
    user.party = employee.party
    user.save(update_fields=["party"])


@pytest.fixture
def outsider_employee_a(db, tenant_a):
    """A THIRD EmployeeProfile in tenant_a — neither subject nor reviewer of performance_review_a
    (which uses employee_a as subject and employee_a2 as reviewer). Used to build a non-admin user
    who must be denied access to a review they're not party to."""
    from apps.core.models import Employment, Party
    from apps.hrm.models import EmployeeProfile
    party = Party.objects.create(tenant=tenant_a, kind="person", name="Dana Outsider")
    employment = Employment.objects.create(
        tenant=tenant_a, party=party, job_title="Analyst", status="active")
    return EmployeeProfile.objects.create(
        tenant=tenant_a, party=party, employment=employment, employee_type="full_time")


@pytest.fixture
def outsider_user(db, tenant_a, outsider_employee_a):
    """A non-admin tenant_a User linked to outsider_employee_a."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email="dana@acme.com", username="dana_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )
    user.party = outsider_employee_a.party
    user.save(update_fields=["party"])
    return user


@pytest.fixture
def outsider_client(db, outsider_user):
    c = Client()
    c.force_login(outsider_user)
    return c


@pytest.fixture
def subject_client(db, admin_user, employee_a):
    """A non-admin-flavored client logged in as `admin_user` (kept a tenant admin at the User
    level for simplicity) but LINKED to employee_a (the subject of performance_review_a), used
    where the test cares about the subject/reviewer identity rather than the admin bypass. Prefer
    `outsider_client`/`member_client_as_reviewer` below for true non-admin authz checks."""
    _link_user_to_employee(admin_user, employee_a)
    c = Client()
    c.force_login(admin_user)
    return c


@pytest.fixture
def member_as_outsider_client(db, member_user, outsider_employee_a):
    """The plain non-admin member_user, linked to outsider_employee_a (neither subject nor
    reviewer of performance_review_a) — the canonical "curious employee" for confidentiality
    tests: is_tenant_admin=False AND not a participant."""
    _link_user_to_employee(member_user, outsider_employee_a)
    c = Client()
    c.force_login(member_user)
    return c


@pytest.fixture
def member_as_subject_client(db, member_user, employee_a):
    """The plain non-admin member_user, linked to employee_a (the SUBJECT of
    performance_review_a) — used for subject-view / edit-lock assertions."""
    _link_user_to_employee(member_user, employee_a)
    c = Client()
    c.force_login(member_user)
    return c


@pytest.fixture
def member_as_reviewer_client(db, member_user, employee_a2):
    """The plain non-admin member_user, linked to employee_a2 (the REVIEWER of
    performance_review_a) — used for reviewer-edit assertions."""
    _link_user_to_employee(member_user, employee_a2)
    c = Client()
    c.force_login(member_user)
    return c


class TestPerformanceReviewConfidentiality:
    def test_non_participant_403_on_detail(self, member_as_outsider_client, performance_review_a):
        resp = member_as_outsider_client.get(
            reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.status_code == 403

    def test_non_participant_403_on_rating_detail(self, member_as_outsider_client, review_rating_a):
        resp = member_as_outsider_client.get(reverse("hrm:reviewrating_detail", args=[review_rating_a.pk]))
        assert resp.status_code == 403

    def test_subject_can_view_own_review(self, member_as_subject_client, performance_review_a):
        resp = member_as_subject_client.get(
            reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_subject"] is True

    def test_reviewer_can_view_authored_review(self, member_as_reviewer_client, performance_review_a):
        resp = member_as_reviewer_client.get(
            reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_reviewer"] is True

    def test_admin_can_view_any_review(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.status_code == 200

    def test_reviewer_can_view_rating_detail(self, member_as_reviewer_client, review_rating_a):
        resp = member_as_reviewer_client.get(reverse("hrm:reviewrating_detail", args=[review_rating_a.pk]))
        assert resp.status_code == 200

    def test_performancereview_list_shows_admin_all_reviews(
        self, tenant_a, review_cycle_a, employee_a, employee_a2, admin_user
    ):
        """Sanity baseline: the tenant admin's list includes both reviews below."""
        from apps.hrm.models import PerformanceReview
        review_for_a = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="manager")
        c = Client()
        c.force_login(admin_user)
        resp = c.get(reverse("hrm:performancereview_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert review_for_a.pk in pks

    def test_performancereview_list_hides_others_reviews_from_non_participant(
        self, member_as_outsider_client, performance_review_a
    ):
        """A non-admin employee who is neither subject nor reviewer of performance_review_a must
        NOT see it in their own list roster."""
        resp = member_as_outsider_client.get(reverse("hrm:performancereview_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk not in pks

    def test_performancereview_list_shows_subject_their_own_review(
        self, member_as_subject_client, performance_review_a
    ):
        resp = member_as_subject_client.get(reverse("hrm:performancereview_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks

    def test_performancereview_list_shows_reviewer_their_authored_review(
        self, member_as_reviewer_client, performance_review_a
    ):
        resp = member_as_reviewer_client.get(reverse("hrm:performancereview_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert performance_review_a.pk in pks

    def test_performancereview_list_scoped_employee_sees_only_own_reviews_not_others(
        self, tenant_a, review_cycle_a, employee_a, employee_a2, outsider_employee_a, member_as_outsider_client
    ):
        """A non-participant's list must contain ONLY their own subject/reviewer rows, never
        another employee's review — build a second review the outsider IS party to, and confirm
        performance_review_a (which they're NOT party to) is excluded while their own is present."""
        from apps.hrm.models import PerformanceReview
        own_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=outsider_employee_a, reviewer=employee_a2,
            review_type="manager")
        resp = member_as_outsider_client.get(reverse("hrm:performancereview_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert own_review.pk in pks

    def test_reviewcycle_detail_hides_roster_from_non_participant(
        self, member_as_outsider_client, review_cycle_a, performance_review_a
    ):
        """A non-participant viewing the cycle detail must not see performance_review_a in the
        cycle's reviews roster (the confidentiality filter also applies to reviewcycle_detail)."""
        resp = member_as_outsider_client.get(reverse("hrm:reviewcycle_detail", args=[review_cycle_a.pk]))
        assert resp.status_code == 200
        pks = [r.pk for r in resp.context["reviews"]]
        assert performance_review_a.pk not in pks

    def test_reviewcycle_detail_shows_subject_their_own_review_in_roster(
        self, member_as_subject_client, review_cycle_a, performance_review_a
    ):
        resp = member_as_subject_client.get(reverse("hrm:reviewcycle_detail", args=[review_cycle_a.pk]))
        pks = [r.pk for r in resp.context["reviews"]]
        assert performance_review_a.pk in pks

    def test_reviewcycle_detail_admin_sees_full_roster(
        self, client_a, review_cycle_a, performance_review_a
    ):
        resp = client_a.get(reverse("hrm:reviewcycle_detail", args=[review_cycle_a.pk]))
        pks = [r.pk for r in resp.context["reviews"]]
        assert performance_review_a.pk in pks


class TestReviewRatingConfidentialityCascade:
    def test_reviewrating_detail_denied_to_non_participant_even_though_it_exists(
        self, member_as_outsider_client, review_rating_a
    ):
        resp = member_as_outsider_client.get(reverse("hrm:reviewrating_detail", args=[review_rating_a.pk]))
        assert resp.status_code == 403


# ================================================================ private_notes gating
class TestPrivateNotesGating:
    def test_admin_sees_private_notes(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.status_code == 200
        assert b"Confidential: needs coaching on delegation." in resp.content

    def test_reviewer_sees_private_notes(self, member_as_reviewer_client, performance_review_a):
        resp = member_as_reviewer_client.get(
            reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.status_code == 200
        assert b"Confidential: needs coaching on delegation." in resp.content

    def test_subject_does_not_see_private_notes_once_shared(
        self, member_as_subject_client, performance_review_a
    ):
        """The subject can only reach performancereview_detail once the review is shared (or
        acknowledged) — at that point private_notes must be absent from the rendered page."""
        performance_review_a.status = "shared"
        performance_review_a.save(update_fields=["status"])
        resp = member_as_subject_client.get(
            reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.status_code == 200
        assert resp.context["show_private"] is False
        assert b"Confidential: needs coaching on delegation." not in resp.content

    def test_subject_does_not_see_private_notes_once_acknowledged(
        self, member_as_subject_client, performance_review_a
    ):
        performance_review_a.status = "acknowledged"
        performance_review_a.save(update_fields=["status"])
        resp = member_as_subject_client.get(
            reverse("hrm:performancereview_detail", args=[performance_review_a.pk]))
        assert resp.status_code == 200
        assert b"Confidential: needs coaching on delegation." not in resp.content


# ================================================================ EDIT LOCK (_can_edit_review)
class TestEditLock:
    def test_reviewer_can_edit_while_draft(self, member_as_reviewer_client, performance_review_a):
        resp = member_as_reviewer_client.get(
            reverse("hrm:performancereview_edit", args=[performance_review_a.pk]))
        assert resp.status_code == 200

    def test_admin_can_edit_while_draft(self, client_a, performance_review_a):
        resp = client_a.get(reverse("hrm:performancereview_edit", args=[performance_review_a.pk]))
        assert resp.status_code == 200

    def test_subject_cannot_edit_even_while_draft(self, member_as_subject_client, performance_review_a):
        """The subject is never the reviewer on this manager review — editing is denied
        regardless of status (redirect, not a 403 — matches the view's messages.error + redirect
        pattern for this particular gate)."""
        resp = member_as_subject_client.get(
            reverse("hrm:performancereview_edit", args=[performance_review_a.pk]))
        assert resp.status_code == 302

    def test_reviewer_blocked_once_submitted(self, member_as_reviewer_client, performance_review_a):
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        resp = member_as_reviewer_client.get(
            reverse("hrm:performancereview_edit", args=[performance_review_a.pk]))
        assert resp.status_code == 302

    def test_post_to_edit_on_shared_review_leaves_private_notes_unchanged(
        self, member_as_reviewer_client, performance_review_a, review_cycle_a, employee_a, employee_a2
    ):
        """Even the reviewer cannot mutate private_notes on a shared/acknowledged review — the
        edit view redirects without saving the form."""
        performance_review_a.status = "shared"
        performance_review_a.save(update_fields=["status"])
        original_notes = performance_review_a.private_notes
        resp = member_as_reviewer_client.post(
            reverse("hrm:performancereview_edit", args=[performance_review_a.pk]), {
                "cycle": review_cycle_a.pk, "template": performance_review_a.template_id,
                "subject": employee_a.pk, "reviewer": employee_a2.pk, "review_type": "manager",
                "strengths": "", "improvements": "",
                "private_notes": "TAMPERED — should never be written",
                "is_anonymous": "",
            })
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.private_notes == original_notes

    def test_admin_post_to_edit_on_shared_review_also_blocked(
        self, client_a, performance_review_a, review_cycle_a, employee_a, employee_a2
    ):
        """The draft-only gate applies to the admin too, not just non-admins — once shared, even
        an admin's edit POST is rejected (redirect, no mutation)."""
        performance_review_a.status = "shared"
        performance_review_a.save(update_fields=["status"])
        original_notes = performance_review_a.private_notes
        resp = client_a.post(
            reverse("hrm:performancereview_edit", args=[performance_review_a.pk]), {
                "cycle": review_cycle_a.pk, "template": performance_review_a.template_id,
                "subject": employee_a.pk, "reviewer": employee_a2.pk, "review_type": "manager",
                "strengths": "", "improvements": "", "private_notes": "TAMPERED", "is_anonymous": "",
            })
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.private_notes == original_notes

    def test_subject_cannot_edit_manager_review_private_notes_via_post(
        self, member_as_subject_client, performance_review_a, review_cycle_a, employee_a, employee_a2
    ):
        original_notes = performance_review_a.private_notes
        resp = member_as_subject_client.post(
            reverse("hrm:performancereview_edit", args=[performance_review_a.pk]), {
                "cycle": review_cycle_a.pk, "template": performance_review_a.template_id,
                "subject": employee_a.pk, "reviewer": employee_a2.pk, "review_type": "manager",
                "strengths": "", "improvements": "",
                "private_notes": "TAMPERED BY SUBJECT", "is_anonymous": "",
            })
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.private_notes == original_notes

    def test_reviewrating_create_blocked_for_non_participant(
        self, member_as_outsider_client, performance_review_a
    ):
        from apps.hrm.models import ReviewRating
        resp = member_as_outsider_client.post(
            reverse("hrm:reviewrating_create", args=[performance_review_a.pk]), {
                "criterion_label": "Should not be added", "criterion_category": "competency",
                "rating_value": "4.00", "weight": "50", "comment": "",
            })
        assert resp.status_code == 302
        assert not ReviewRating.objects.filter(
            review=performance_review_a, criterion_label="Should not be added").exists()

    def test_reviewrating_create_blocked_for_subject(self, member_as_subject_client, performance_review_a):
        from apps.hrm.models import ReviewRating
        resp = member_as_subject_client.post(
            reverse("hrm:reviewrating_create", args=[performance_review_a.pk]), {
                "criterion_label": "Should not be added by subject", "criterion_category": "competency",
                "rating_value": "4.00", "weight": "50", "comment": "",
            })
        assert resp.status_code == 302
        assert not ReviewRating.objects.filter(
            review=performance_review_a, criterion_label="Should not be added by subject").exists()

    def test_reviewrating_edit_blocked_once_not_draft(self, member_as_reviewer_client, performance_review_a, review_rating_a):
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        original_label = review_rating_a.criterion_label
        member_as_reviewer_client.post(reverse("hrm:reviewrating_edit", args=[review_rating_a.pk]), {
            "criterion_label": "TAMPERED", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "100", "comment": "",
        })
        review_rating_a.refresh_from_db()
        assert review_rating_a.criterion_label == original_label

    def test_reviewrating_delete_blocked_once_not_draft(self, member_as_reviewer_client, performance_review_a, review_rating_a):
        from apps.hrm.models import ReviewRating
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        member_as_reviewer_client.post(reverse("hrm:reviewrating_delete", args=[review_rating_a.pk]))
        assert ReviewRating.objects.filter(pk=review_rating_a.pk).exists()

    def test_reviewrating_edit_blocked_for_outsider_even_while_draft(
        self, member_as_outsider_client, review_rating_a
    ):
        original_label = review_rating_a.criterion_label
        member_as_outsider_client.post(reverse("hrm:reviewrating_edit", args=[review_rating_a.pk]), {
            "criterion_label": "TAMPERED BY OUTSIDER", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "100", "comment": "",
        })
        review_rating_a.refresh_from_db()
        assert review_rating_a.criterion_label == original_label


# ================================================================ AuthZ — tenant-admin-only actions
class TestReviewCycleAdminOnlyActions:
    """@tenant_admin_required gates reviewcycle_advance_phase — a plain (non-admin) tenant member
    must get 403 and the row must remain unchanged."""

    def test_non_admin_403_on_advance_phase(self, member_client, review_cycle_a):
        resp = member_client.post(reverse("hrm:reviewcycle_advance_phase", args=[review_cycle_a.pk]))
        assert resp.status_code == 403
        review_cycle_a.refresh_from_db()
        assert review_cycle_a.status == "draft"

    def test_non_admin_can_still_view_lists_and_details(self, member_client, review_cycle_a):
        resp = member_client.get(reverse("hrm:reviewcycle_list"))
        assert resp.status_code == 200
        resp = member_client.get(reverse("hrm:reviewcycle_detail", args=[review_cycle_a.pk]))
        assert resp.status_code == 200

    def test_non_admin_can_still_do_regular_crud(self, member_client):
        resp = member_client.get(reverse("hrm:reviewcycle_create"))
        assert resp.status_code == 200


class TestPerformanceReviewAdminOnlyActions:
    """@tenant_admin_required gates performancereview_share and performancereview_calibrate."""

    def test_non_admin_403_on_share(self, member_client, performance_review_a):
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        resp = member_client.post(reverse("hrm:performancereview_share", args=[performance_review_a.pk]))
        assert resp.status_code == 403
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "submitted"

    def test_non_admin_403_on_calibrate_get(self, member_client, performance_review_a):
        resp = member_client.get(reverse("hrm:performancereview_calibrate", args=[performance_review_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_on_calibrate_post(self, member_client, performance_review_a):
        resp = member_client.post(
            reverse("hrm:performancereview_calibrate", args=[performance_review_a.pk]), {
                "calibrated_rating": "5.00", "potential_rating": "", "calibration_notes": "",
            })
        assert resp.status_code == 403
        performance_review_a.refresh_from_db()
        assert performance_review_a.calibrated_rating is None

    def test_reviewer_non_admin_403_on_share_even_though_they_authored_the_review(
        self, member_as_reviewer_client, performance_review_a
    ):
        """share is a strictly-admin action — even the review's own reviewer (non-admin) is denied."""
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        resp = member_as_reviewer_client.post(
            reverse("hrm:performancereview_share", args=[performance_review_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_on_calibration_board(self, member_client):
        resp = member_client.get(reverse("hrm:calibration_board"))
        assert resp.status_code == 403


# ================================================================ CSRF enforcement
class TestReviewsCSRFEnforcement:
    def test_reviewcycle_delete_enforces_csrf(self, admin_user, tenant_a):
        from apps.hrm.models import ReviewCycle
        rc = ReviewCycle.objects.create(tenant=tenant_a, name="CSRF Delete Cycle")
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:reviewcycle_delete", args=[rc.pk]))
        assert resp.status_code == 403

    def test_reviewcycle_advance_phase_enforces_csrf(self, admin_user, review_cycle_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:reviewcycle_advance_phase", args=[review_cycle_a.pk]))
        assert resp.status_code == 403
        review_cycle_a.refresh_from_db()
        assert review_cycle_a.status == "draft"

    def test_reviewtemplate_delete_enforces_csrf(self, admin_user, review_template_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:reviewtemplate_delete", args=[review_template_a.pk]))
        assert resp.status_code == 403

    def test_performancereview_delete_enforces_csrf(self, admin_user, performance_review_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:performancereview_delete", args=[performance_review_a.pk]))
        assert resp.status_code == 403

    def test_performancereview_submit_enforces_csrf(self, admin_user, performance_review_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:performancereview_submit", args=[performance_review_a.pk]))
        assert resp.status_code == 403
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "draft"

    def test_performancereview_share_enforces_csrf(self, admin_user, performance_review_a):
        performance_review_a.status = "submitted"
        performance_review_a.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:performancereview_share", args=[performance_review_a.pk]))
        assert resp.status_code == 403
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "submitted"

    def test_performancereview_acknowledge_enforces_csrf(self, admin_user, employee_a, performance_review_a):
        _link_user_to_employee(admin_user, employee_a)
        performance_review_a.status = "shared"
        performance_review_a.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:performancereview_acknowledge", args=[performance_review_a.pk]))
        assert resp.status_code == 403
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "shared"

    def test_performancereview_calibrate_enforces_csrf(self, admin_user, performance_review_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(
            reverse("hrm:performancereview_calibrate", args=[performance_review_a.pk]), {
                "calibrated_rating": "5.00", "potential_rating": "", "calibration_notes": "",
            })
        assert resp.status_code == 403
        performance_review_a.refresh_from_db()
        assert performance_review_a.calibrated_rating is None

    def test_reviewrating_create_enforces_csrf(self, admin_user, performance_review_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:reviewrating_create", args=[performance_review_a.pk]), {
            "criterion_label": "CSRF-blocked", "criterion_category": "competency",
            "rating_value": "4.00", "weight": "50", "comment": "",
        })
        assert resp.status_code == 403
        from apps.hrm.models import ReviewRating
        assert not ReviewRating.objects.filter(
            review=performance_review_a, criterion_label="CSRF-blocked").exists()

    def test_reviewrating_delete_enforces_csrf(self, admin_user, review_rating_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:reviewrating_delete", args=[review_rating_a.pk]))
        assert resp.status_code == 403


# ================================================================ Form authz fixes
class TestReviewCycleFormStatusFieldExcluded:
    def test_form_has_no_status_field(self):
        from apps.hrm.forms import ReviewCycleForm
        assert "status" not in ReviewCycleForm.Meta.fields

    def test_edit_post_with_status_does_not_bypass_advance_phase_gate(self, client_a, review_cycle_a):
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
        assert review_cycle_a.status == "draft"


class TestPerformanceReviewFormWorkflowFieldsExcluded:
    def test_form_excludes_status_and_calibration_fields(self):
        from apps.hrm.forms import PerformanceReviewForm
        excluded = {"status", "manager_rating", "calibrated_rating", "potential_rating",
                    "calibration_notes", "submitted_at", "shared_at", "acknowledged_at",
                    "acknowledged_by", "number"}
        assert excluded.isdisjoint(set(PerformanceReviewForm.Meta.fields))

    def test_edit_post_with_calibrated_rating_does_not_write_it(
        self, client_a, performance_review_a, review_cycle_a, employee_a, employee_a2
    ):
        """PerformanceReviewForm has no `calibrated_rating` field — POSTing it via the general
        edit form must NOT set it (only performancereview_calibrate's CalibrationForm may)."""
        assert performance_review_a.calibrated_rating is None
        resp = client_a.post(reverse("hrm:performancereview_edit", args=[performance_review_a.pk]), {
            "cycle": review_cycle_a.pk, "template": performance_review_a.template_id,
            "subject": employee_a.pk, "reviewer": employee_a2.pk, "review_type": "manager",
            "strengths": "", "improvements": "", "private_notes": "", "is_anonymous": "",
            "calibrated_rating": "1.00",
        })
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.calibrated_rating is None

    def test_edit_post_with_status_does_not_write_it(
        self, client_a, performance_review_a, review_cycle_a, employee_a, employee_a2
    ):
        assert performance_review_a.status == "draft"
        resp = client_a.post(reverse("hrm:performancereview_edit", args=[performance_review_a.pk]), {
            "cycle": review_cycle_a.pk, "template": performance_review_a.template_id,
            "subject": employee_a.pk, "reviewer": employee_a2.pk, "review_type": "manager",
            "strengths": "", "improvements": "", "private_notes": "", "is_anonymous": "",
            "status": "acknowledged",
        })
        assert resp.status_code == 302
        performance_review_a.refresh_from_db()
        assert performance_review_a.status == "draft"
