"""Tests for HRM 3.27 Communication Hub views: the derived ``celebrations`` feed (window bounds),
``Announcement`` CRUD + audience-targeted employee feed + publish/archive lifecycle, ``Survey``
CRUD (draft-only edit/delete) + open/close/respond(-once)/results (anonymity-aware aggregation),
and ``Suggestion`` (reuses the 3.26 ``_hr_request_*``/``_ss_child_*`` helpers verbatim — same
draft->pending->approved/rejected/cancelled(+implemented) lifecycle and self-approval guard).
Mirrors test_requests_views.py conventions; client_a is the tenant admin (no linked employee)."""
import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _client_for(party, tenant, *, email, username, is_admin=False):
    """Build a logged-in Client for a User linked to the given Party."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email=email, username=username, password="TestPass123!",
        tenant=tenant, is_tenant_admin=is_admin,
    )
    user.party = party
    user.save(update_fields=["party"])
    c = Client()
    c.force_login(user)
    return c


def _admin_linked_to(party, tenant, *, email, username):
    """A tenant-admin User linked to a specific Party (for self-approval-guard tests)."""
    return _client_for(party, tenant, email=email, username=username, is_admin=True)


def _announcement_post_data(**overrides):
    data = {
        "title": "Team Update", "body": "Body text.", "category": "general",
        "audience_type": "all", "target_department": "", "target_designation": "",
        "is_pinned": "", "expires_at": "",
    }
    data.update(overrides)
    return data


def _survey_post_data(questions, **overrides):
    import json
    data = {"title": "Engagement Pulse", "description": "", "questions": json.dumps(questions),
            "is_anonymous": "", "opens_at": "", "closes_at": ""}
    data.update(overrides)
    return data


def _suggestion_post_data(**overrides):
    data = {
        "title": "Add a bike rack", "body": "A bike rack near the east entrance would help commuters.",
        "category": "workplace", "is_anonymous": "",
    }
    data.update(overrides)
    return data


# ================================================================ Celebrations (derived)
class TestCelebrationsView:
    def test_login_required(self, client):
        resp = client.get(reverse("hrm:celebrations"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_200_for_logged_in_user(self, client_a):
        resp = client_a.get(reverse("hrm:celebrations"))
        assert resp.status_code == 200

    def test_window_defaults_to_30(self, client_a):
        resp = client_a.get(reverse("hrm:celebrations"))
        assert resp.context["window"] == 30

    @pytest.mark.parametrize("raw,expected", [("7", 7), ("90", 90), ("999", 90), ("abc", 30), ("0", 1)])
    def test_window_bounds_do_not_error(self, client_a, raw, expected):
        resp = client_a.get(reverse("hrm:celebrations"), {"window": raw})
        assert resp.status_code == 200
        assert resp.context["window"] == expected

    def test_context_has_expected_keys(self, client_a):
        resp = client_a.get(reverse("hrm:celebrations"))
        for key in ("birthdays", "anniversaries", "window", "capped", "cap"):
            assert key in resp.context

    def test_birthday_within_window_included(self, tenant_a, employee_a):
        today = timezone.localdate()
        target = today + datetime.timedelta(days=5)
        employee_a.date_of_birth = datetime.date(1990, target.month, target.day)
        employee_a.save(update_fields=["date_of_birth"])
        c = _client_for(employee_a.party, tenant_a, email="cel_bday@acme.com", username="cel_bday_acme")
        resp = c.get(reverse("hrm:celebrations"))
        emp_ids = [row["emp"].pk for row in resp.context["birthdays"]]
        assert employee_a.pk in emp_ids

    def test_birthday_outside_window_excluded(self, tenant_a, employee_a):
        today = timezone.localdate()
        target = today + datetime.timedelta(days=60)
        employee_a.date_of_birth = datetime.date(1990, target.month, target.day)
        employee_a.save(update_fields=["date_of_birth"])
        c = _client_for(employee_a.party, tenant_a, email="cel_bday2@acme.com", username="cel_bday2_acme")
        resp = c.get(reverse("hrm:celebrations"), {"window": 30})
        emp_ids = [row["emp"].pk for row in resp.context["birthdays"]]
        assert employee_a.pk not in emp_ids

    def test_anniversary_within_window_included(self, tenant_a, employee_a):
        today = timezone.localdate()
        target = today + datetime.timedelta(days=5)
        employee_a.employment.hired_on = datetime.date(today.year - 2, target.month, target.day)
        employee_a.employment.save(update_fields=["hired_on"])
        c = _client_for(employee_a.party, tenant_a, email="cel_anniv@acme.com", username="cel_anniv_acme")
        resp = c.get(reverse("hrm:celebrations"))
        rows = [row for row in resp.context["anniversaries"] if row["emp"].pk == employee_a.pk]
        assert len(rows) == 1
        assert rows[0]["years"] == 2

    def test_terminated_employee_excluded_from_birthdays(self, tenant_a, employee_a):
        today = timezone.localdate()
        target = today + datetime.timedelta(days=5)
        employee_a.date_of_birth = datetime.date(1990, target.month, target.day)
        employee_a.save(update_fields=["date_of_birth"])
        employee_a.employment.status = "terminated"
        employee_a.employment.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="cel_term@acme.com", username="cel_term_acme")
        resp = c.get(reverse("hrm:celebrations"))
        emp_ids = [row["emp"].pk for row in resp.context["birthdays"]]
        assert employee_a.pk not in emp_ids

    def test_no_tenant_yields_empty_lists_no_error(self, admin_user):
        """A tenant-less superuser (request.tenant is None) gets empty feeds, not a 500."""
        from apps.accounts.models import User
        superuser = User.objects.create_superuser(
            email="super_cel@example.com", username="super_cel", password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        resp = c.get(reverse("hrm:celebrations"))
        assert resp.status_code == 200
        assert resp.context["birthdays"] == []
        assert resp.context["anniversaries"] == []


# ================================================================ Announcement — admin list/create/edit/delete
class TestAnnouncementListView:
    def test_list_200_admin(self, client_a, announcement_a):
        resp = client_a.get(reverse("hrm:announcement_list"))
        assert resp.status_code == 200

    def test_list_has_choices_context_for_admin(self, client_a, announcement_a):
        resp = client_a.get(reverse("hrm:announcement_list"))
        assert resp.context["is_admin"] is True
        assert "status_choices" in resp.context
        assert "category_choices" in resp.context
        assert "audience_type_choices" in resp.context

    def test_list_filter_by_status(self, client_a, announcement_a):
        resp = client_a.get(reverse("hrm:announcement_list"), {"status": "draft"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert announcement_a.pk in pks

    def test_list_filter_by_status_excludes_other_status(self, client_a, published_announcement_a):
        resp = client_a.get(reverse("hrm:announcement_list"), {"status": "draft"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert published_announcement_a.pk not in pks

    def test_list_filter_by_category(self, client_a, announcement_a):
        resp = client_a.get(reverse("hrm:announcement_list"), {"category": "general"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert announcement_a.pk in pks

    def test_list_filter_by_audience_type(self, client_a, dept_announcement_a):
        resp = client_a.get(reverse("hrm:announcement_list"), {"audience_type": "department"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert dept_announcement_a.pk in pks

    def test_list_search_by_title(self, client_a, announcement_a):
        resp = client_a.get(reverse("hrm:announcement_list"), {"q": "Office Closure"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert announcement_a.pk in pks

    def test_bad_page_does_not_500(self, client_a, announcement_a):
        resp = client_a.get(reverse("hrm:announcement_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, announcement_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:announcement_list"))


class TestAnnouncementEmployeeFeed:
    def test_employee_sees_published_all_audience(self, tenant_a, employee_a, published_announcement_a):
        c = _client_for(employee_a.party, tenant_a, email="emp_feed1@acme.com", username="emp_feed1_acme")
        resp = c.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert published_announcement_a.pk in pks
        assert resp.context["is_admin"] is False

    def test_employee_does_not_see_draft(self, tenant_a, employee_a, announcement_a):
        c = _client_for(employee_a.party, tenant_a, email="emp_feed2@acme.com", username="emp_feed2_acme")
        resp = c.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert announcement_a.pk not in pks

    def test_employee_does_not_see_archived(self, tenant_a, employee_a, published_announcement_a):
        published_announcement_a.status = "archived"
        published_announcement_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="emp_feed3@acme.com", username="emp_feed3_acme")
        resp = c.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert published_announcement_a.pk not in pks

    def test_employee_does_not_see_expired(self, tenant_a, employee_a, published_announcement_a):
        published_announcement_a.expires_at = timezone.localdate() - datetime.timedelta(days=1)
        published_announcement_a.save(update_fields=["expires_at"])
        c = _client_for(employee_a.party, tenant_a, email="emp_feed4@acme.com", username="emp_feed4_acme")
        resp = c.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert published_announcement_a.pk not in pks

    def test_employee_sees_own_department_announcement(self, tenant_a, employee_a, dept_announcement_a):
        c = _client_for(employee_a.party, tenant_a, email="emp_feed5@acme.com", username="emp_feed5_acme")
        resp = c.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert dept_announcement_a.pk in pks

    def test_employee_does_not_see_other_department_announcement(self, tenant_a, employee_a):
        from apps.core.models import OrgUnit
        from apps.hrm.models import Announcement
        other_dept = OrgUnit.objects.create(tenant=tenant_a, kind="department", name="Sales")
        ann = Announcement.objects.create(
            tenant=tenant_a, title="Sales Only", body="x",
            audience_type="department", target_department=other_dept,
            status="published", published_at=timezone.now())
        c = _client_for(employee_a.party, tenant_a, email="emp_feed6@acme.com", username="emp_feed6_acme")
        resp = c.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert ann.pk not in pks

    def test_employee_sees_own_designation_announcement(self, tenant_a, employee_a, desig_announcement_a):
        c = _client_for(employee_a.party, tenant_a, email="emp_feed7@acme.com", username="emp_feed7_acme")
        resp = c.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert desig_announcement_a.pk in pks

    def test_employee_with_no_department_never_null_matches_orphaned_announcement(self, tenant_a, dept_a):
        from apps.core.models import Employment, Party
        from apps.hrm.models import Announcement, EmployeeProfile
        party = Party.objects.create(tenant=tenant_a, kind="person", name="No Dept Nadia")
        employment = Employment.objects.create(
            tenant=tenant_a, party=party, job_title="Floater", status="active")  # no org_unit
        EmployeeProfile.objects.create(
            tenant=tenant_a, party=party, employment=employment, employee_type="full_time")
        ann = Announcement.objects.create(
            tenant=tenant_a, title="Dept Only", body="x",
            audience_type="department", target_department=dept_a,
            status="published", published_at=timezone.now())
        dept_a.delete()  # SET_NULL orphans the FK — audience_type stays "department"
        ann.refresh_from_db()
        assert ann.target_department_id is None
        c = _client_for(party, tenant_a, email="emp_nodept@acme.com", username="emp_nodept_acme")
        resp = c.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert ann.pk not in pks

    def test_employee_with_no_designation_never_null_matches_orphaned_announcement(
        self, tenant_a, designation_a
    ):
        from apps.core.models import Employment, Party
        from apps.hrm.models import Announcement, EmployeeProfile
        party = Party.objects.create(tenant=tenant_a, kind="person", name="No Desig Nadia")
        employment = Employment.objects.create(
            tenant=tenant_a, party=party, job_title="Floater", status="active")
        EmployeeProfile.objects.create(
            tenant=tenant_a, party=party, employment=employment, employee_type="full_time")  # no designation
        ann = Announcement.objects.create(
            tenant=tenant_a, title="Desig Only", body="x",
            audience_type="designation", target_designation=designation_a,
            status="published", published_at=timezone.now())
        designation_a.delete()  # SET_NULL orphans the FK — audience_type stays "designation"
        ann.refresh_from_db()
        assert ann.target_designation_id is None
        c = _client_for(party, tenant_a, email="emp_nodesig@acme.com", username="emp_nodesig_acme")
        resp = c.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert ann.pk not in pks


class TestAnnouncementDetailView:
    def test_admin_sees_draft_detail(self, client_a, announcement_a):
        resp = client_a.get(reverse("hrm:announcement_detail", args=[announcement_a.pk]))
        assert resp.status_code == 200

    def test_employee_403_on_draft(self, tenant_a, employee_a, announcement_a):
        c = _client_for(employee_a.party, tenant_a, email="det_draft@acme.com", username="det_draft_acme")
        resp = c.get(reverse("hrm:announcement_detail", args=[announcement_a.pk]))
        assert resp.status_code == 403

    def test_employee_200_when_published_and_matching(self, tenant_a, employee_a, published_announcement_a):
        c = _client_for(employee_a.party, tenant_a, email="det_pub@acme.com", username="det_pub_acme")
        resp = c.get(reverse("hrm:announcement_detail", args=[published_announcement_a.pk]))
        assert resp.status_code == 200

    def test_employee_403_when_audience_does_not_match(self, tenant_a, employee_a):
        from apps.core.models import OrgUnit
        from apps.hrm.models import Announcement
        other_dept = OrgUnit.objects.create(tenant=tenant_a, kind="department", name="Sales2")
        ann = Announcement.objects.create(
            tenant=tenant_a, title="Sales Only 2", body="x",
            audience_type="department", target_department=other_dept,
            status="published", published_at=timezone.now())
        c = _client_for(employee_a.party, tenant_a, email="det_mismatch@acme.com", username="det_mismatch_acme")
        resp = c.get(reverse("hrm:announcement_detail", args=[ann.pk]))
        assert resp.status_code == 403

    def test_employee_403_when_expired(self, tenant_a, employee_a, published_announcement_a):
        published_announcement_a.expires_at = timezone.localdate() - datetime.timedelta(days=1)
        published_announcement_a.save(update_fields=["expires_at"])
        c = _client_for(employee_a.party, tenant_a, email="det_exp@acme.com", username="det_exp_acme")
        resp = c.get(reverse("hrm:announcement_detail", args=[published_announcement_a.pk]))
        assert resp.status_code == 403


class TestAnnouncementCreateEditDelete:
    def test_get_200_for_admin(self, client_a):
        resp = client_a.get(reverse("hrm:announcement_create"))
        assert resp.status_code == 200

    def test_403_for_non_admin(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="ann_na@acme.com", username="ann_na_acme")
        resp = c.get(reverse("hrm:announcement_create"))
        assert resp.status_code == 403

    def test_post_creates_with_author_server_set(self, client_a, tenant_a, admin_user):
        from apps.hrm.models import Announcement
        resp = client_a.post(reverse("hrm:announcement_create"), _announcement_post_data())
        assert resp.status_code == 302
        obj = Announcement.objects.filter(tenant=tenant_a).first()
        assert obj is not None
        assert obj.author_id == admin_user.pk
        assert obj.status == "draft"

    def test_form_has_no_status_published_at_author_number_fields(self, client_a):
        resp = client_a.get(reverse("hrm:announcement_create"))
        fields = resp.context["form"].fields
        for excluded in ("tenant", "status", "published_at", "author", "number"):
            assert excluded not in fields

    def test_edit_updates_title(self, client_a, announcement_a):
        resp = client_a.post(
            reverse("hrm:announcement_edit", args=[announcement_a.pk]),
            _announcement_post_data(title="Updated Title"))
        assert resp.status_code == 302
        announcement_a.refresh_from_db()
        assert announcement_a.title == "Updated Title"

    def test_edit_403_for_non_admin(self, tenant_a, employee_a, announcement_a):
        c = _client_for(employee_a.party, tenant_a, email="ann_edit_na@acme.com", username="ann_edit_na_acme")
        resp = c.get(reverse("hrm:announcement_edit", args=[announcement_a.pk]))
        assert resp.status_code == 403

    def test_delete_removes(self, client_a, announcement_a):
        from apps.hrm.models import Announcement
        pk = announcement_a.pk
        resp = client_a.post(reverse("hrm:announcement_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Announcement.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, announcement_a):
        resp = client_a.get(reverse("hrm:announcement_delete", args=[announcement_a.pk]))
        assert resp.status_code == 405


class TestAnnouncementPublishArchive:
    def test_publish_draft_to_published_stamps_published_at(self, client_a, announcement_a):
        resp = client_a.post(reverse("hrm:announcement_publish", args=[announcement_a.pk]))
        assert resp.status_code == 302
        announcement_a.refresh_from_db()
        assert announcement_a.status == "published"
        assert announcement_a.published_at is not None

    def test_publish_blocked_when_not_draft(self, client_a, published_announcement_a):
        original = published_announcement_a.published_at
        client_a.post(reverse("hrm:announcement_publish", args=[published_announcement_a.pk]))
        published_announcement_a.refresh_from_db()
        assert published_announcement_a.status == "published"
        assert published_announcement_a.published_at == original

    def test_publish_403_for_non_admin(self, tenant_a, employee_a, announcement_a):
        c = _client_for(employee_a.party, tenant_a, email="ann_pub_na@acme.com", username="ann_pub_na_acme")
        resp = c.post(reverse("hrm:announcement_publish", args=[announcement_a.pk]))
        assert resp.status_code == 403
        announcement_a.refresh_from_db()
        assert announcement_a.status == "draft"

    def test_publish_get_not_allowed(self, client_a, announcement_a):
        resp = client_a.get(reverse("hrm:announcement_publish", args=[announcement_a.pk]))
        assert resp.status_code == 405

    def test_archive_published_to_archived(self, client_a, published_announcement_a):
        resp = client_a.post(reverse("hrm:announcement_archive", args=[published_announcement_a.pk]))
        assert resp.status_code == 302
        published_announcement_a.refresh_from_db()
        assert published_announcement_a.status == "archived"

    def test_archive_blocked_when_not_published(self, client_a, announcement_a):
        client_a.post(reverse("hrm:announcement_archive", args=[announcement_a.pk]))
        announcement_a.refresh_from_db()
        assert announcement_a.status == "draft"

    def test_archive_403_for_non_admin(self, tenant_a, employee_a, published_announcement_a):
        c = _client_for(employee_a.party, tenant_a, email="ann_arch_na@acme.com", username="ann_arch_na_acme")
        resp = c.post(reverse("hrm:announcement_archive", args=[published_announcement_a.pk]))
        assert resp.status_code == 403
        published_announcement_a.refresh_from_db()
        assert published_announcement_a.status == "published"

    def test_archive_get_not_allowed(self, client_a, published_announcement_a):
        resp = client_a.get(reverse("hrm:announcement_archive", args=[published_announcement_a.pk]))
        assert resp.status_code == 405


# ================================================================ Survey
class TestSurveyListView:
    def test_list_200(self, client_a, survey_a):
        resp = client_a.get(reverse("hrm:survey_list"))
        assert resp.status_code == 200

    def test_admin_sees_draft(self, client_a, survey_a):
        resp = client_a.get(reverse("hrm:survey_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert survey_a.pk in pks

    def test_employee_does_not_see_draft(self, tenant_a, employee_a, survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_list1@acme.com", username="sv_list1_acme")
        resp = c.get(reverse("hrm:survey_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert survey_a.pk not in pks

    def test_employee_sees_open_survey(self, tenant_a, employee_a, open_survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_list2@acme.com", username="sv_list2_acme")
        resp = c.get(reverse("hrm:survey_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert open_survey_a.pk in pks

    def test_list_filter_by_status_admin(self, client_a, open_survey_a):
        resp = client_a.get(reverse("hrm:survey_list"), {"status": "open"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert open_survey_a.pk in pks

    def test_search_by_title(self, client_a, survey_a):
        resp = client_a.get(reverse("hrm:survey_list"), {"q": "Engagement Pulse"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert survey_a.pk in pks

    def test_list_has_status_choices_for_admin(self, client_a, survey_a):
        resp = client_a.get(reverse("hrm:survey_list"))
        assert resp.context["is_admin"] is True
        assert "status_choices" in resp.context

    def test_responded_ids_marks_answered_survey(self, tenant_a, employee_a, open_survey_a, survey_response_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_resp_ids@acme.com", username="sv_resp_ids_acme")
        resp = c.get(reverse("hrm:survey_list"))
        assert open_survey_a.pk in resp.context["responded_ids"]

    def test_list_query_count_bounded(self, client_a, survey_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:survey_list"))


class TestSurveyDetailView:
    def test_admin_sees_draft(self, client_a, survey_a):
        resp = client_a.get(reverse("hrm:survey_detail", args=[survey_a.pk]))
        assert resp.status_code == 200

    def test_employee_403_on_draft(self, tenant_a, employee_a, survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_det1@acme.com", username="sv_det1_acme")
        resp = c.get(reverse("hrm:survey_detail", args=[survey_a.pk]))
        assert resp.status_code == 403

    def test_employee_200_on_open(self, tenant_a, employee_a, open_survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_det2@acme.com", username="sv_det2_acme")
        resp = c.get(reverse("hrm:survey_detail", args=[open_survey_a.pk]))
        assert resp.status_code == 200

    def test_has_responded_true_after_responding(self, tenant_a, employee_a, open_survey_a, survey_response_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_det3@acme.com", username="sv_det3_acme")
        resp = c.get(reverse("hrm:survey_detail", args=[open_survey_a.pk]))
        assert resp.context["has_responded"] is True

    def test_has_responded_false_before_responding(self, tenant_a, employee_a, open_survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_det4@acme.com", username="sv_det4_acme")
        resp = c.get(reverse("hrm:survey_detail", args=[open_survey_a.pk]))
        assert resp.context["has_responded"] is False


class TestSurveyCreateView:
    def test_get_200_for_admin(self, client_a):
        resp = client_a.get(reverse("hrm:survey_create"))
        assert resp.status_code == 200

    def test_403_for_non_admin(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_create_na@acme.com", username="sv_create_na_acme")
        resp = c.get(reverse("hrm:survey_create"))
        assert resp.status_code == 403

    def test_post_creates_with_author_server_set(self, client_a, tenant_a, admin_user, survey_questions):
        from apps.hrm.models import Survey
        resp = client_a.post(reverse("hrm:survey_create"), _survey_post_data(survey_questions))
        assert resp.status_code == 302
        obj = Survey.objects.filter(tenant=tenant_a).first()
        assert obj is not None
        assert obj.author_id == admin_user.pk
        assert obj.status == "draft"

    def test_form_has_no_status_author_number_fields(self, client_a):
        resp = client_a.get(reverse("hrm:survey_create"))
        fields = resp.context["form"].fields
        for excluded in ("tenant", "status", "author", "number"):
            assert excluded not in fields


class TestSurveyEditDelete:
    def test_edit_get_200_when_draft(self, client_a, survey_a):
        resp = client_a.get(reverse("hrm:survey_edit", args=[survey_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_when_not_draft(self, client_a, open_survey_a):
        resp = client_a.get(reverse("hrm:survey_edit", args=[open_survey_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:survey_detail", args=[open_survey_a.pk])

    def test_edit_403_for_non_admin(self, tenant_a, employee_a, survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_edit_na@acme.com", username="sv_edit_na_acme")
        resp = c.get(reverse("hrm:survey_edit", args=[survey_a.pk]))
        assert resp.status_code == 403

    def test_delete_removes_when_draft(self, client_a, survey_a):
        from apps.hrm.models import Survey
        pk = survey_a.pk
        resp = client_a.post(reverse("hrm:survey_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Survey.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_not_draft(self, client_a, open_survey_a):
        from apps.hrm.models import Survey
        resp = client_a.post(reverse("hrm:survey_delete", args=[open_survey_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:survey_detail", args=[open_survey_a.pk])
        assert Survey.objects.filter(pk=open_survey_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, survey_a):
        resp = client_a.get(reverse("hrm:survey_delete", args=[survey_a.pk]))
        assert resp.status_code == 405


class TestSurveyOpenClose:
    def test_open_draft_to_open(self, client_a, survey_a):
        resp = client_a.post(reverse("hrm:survey_open", args=[survey_a.pk]))
        assert resp.status_code == 302
        survey_a.refresh_from_db()
        assert survey_a.status == "open"

    def test_open_blocked_without_questions(self, client_a, tenant_a, admin_user):
        from apps.hrm.models import Survey
        s = Survey.objects.create(tenant=tenant_a, title="Empty", author=admin_user)
        client_a.post(reverse("hrm:survey_open", args=[s.pk]))
        s.refresh_from_db()
        assert s.status == "draft"

    def test_open_blocked_when_not_draft(self, client_a, open_survey_a):
        client_a.post(reverse("hrm:survey_open", args=[open_survey_a.pk]))
        open_survey_a.refresh_from_db()
        assert open_survey_a.status == "open"  # already open, unchanged

    def test_open_403_for_non_admin(self, tenant_a, employee_a, survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_open_na@acme.com", username="sv_open_na_acme")
        resp = c.post(reverse("hrm:survey_open", args=[survey_a.pk]))
        assert resp.status_code == 403
        survey_a.refresh_from_db()
        assert survey_a.status == "draft"

    def test_open_get_not_allowed(self, client_a, survey_a):
        resp = client_a.get(reverse("hrm:survey_open", args=[survey_a.pk]))
        assert resp.status_code == 405

    def test_close_open_to_closed(self, client_a, open_survey_a):
        resp = client_a.post(reverse("hrm:survey_close", args=[open_survey_a.pk]))
        assert resp.status_code == 302
        open_survey_a.refresh_from_db()
        assert open_survey_a.status == "closed"

    def test_close_blocked_when_not_open(self, client_a, survey_a):
        client_a.post(reverse("hrm:survey_close", args=[survey_a.pk]))
        survey_a.refresh_from_db()
        assert survey_a.status == "draft"

    def test_close_403_for_non_admin(self, tenant_a, employee_a, open_survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_close_na@acme.com", username="sv_close_na_acme")
        resp = c.post(reverse("hrm:survey_close", args=[open_survey_a.pk]))
        assert resp.status_code == 403
        open_survey_a.refresh_from_db()
        assert open_survey_a.status == "open"

    def test_close_get_not_allowed(self, client_a, open_survey_a):
        resp = client_a.get(reverse("hrm:survey_close", args=[open_survey_a.pk]))
        assert resp.status_code == 405


class TestSurveyRespond:
    def _answer_data(self):
        return {"q_0": "8", "q_1": "More snacks", "q_2": "Hybrid"}

    def test_get_200_when_open(self, tenant_a, employee_a, open_survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_resp_get@acme.com", username="sv_resp_get_acme")
        resp = c.get(reverse("hrm:survey_respond", args=[open_survey_a.pk]))
        assert resp.status_code == 200

    def test_post_creates_response(self, tenant_a, employee_a, open_survey_a):
        from apps.hrm.models import SurveyResponse
        c = _client_for(employee_a.party, tenant_a, email="sv_resp_post@acme.com", username="sv_resp_post_acme")
        resp = c.post(reverse("hrm:survey_respond", args=[open_survey_a.pk]), self._answer_data())
        assert resp.status_code == 302
        sr = SurveyResponse.objects.filter(tenant=tenant_a, survey=open_survey_a, employee=employee_a).first()
        assert sr is not None
        assert sr.answers["0"] == "8"
        assert sr.answers["2"] == "Hybrid"

    def test_second_respond_blocked_no_dup_no_500(
        self, tenant_a, employee_a, open_survey_a, survey_response_a
    ):
        from apps.hrm.models import SurveyResponse
        c = _client_for(employee_a.party, tenant_a, email="sv_resp_dup@acme.com", username="sv_resp_dup_acme")
        resp = c.post(reverse("hrm:survey_respond", args=[open_survey_a.pk]), self._answer_data())
        assert resp.status_code == 302
        assert SurveyResponse.objects.filter(
            tenant=tenant_a, survey=open_survey_a, employee=employee_a).count() == 1

    def test_respond_blocked_on_draft(self, tenant_a, employee_a, survey_a):
        from apps.hrm.models import SurveyResponse
        c = _client_for(employee_a.party, tenant_a, email="sv_resp_draft@acme.com", username="sv_resp_draft_acme")
        resp = c.post(reverse("hrm:survey_respond", args=[survey_a.pk]), self._answer_data())
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:survey_detail", args=[survey_a.pk])
        assert not SurveyResponse.objects.filter(survey=survey_a).exists()

    def test_respond_blocked_on_closed(self, tenant_a, employee_a, open_survey_a):
        from apps.hrm.models import SurveyResponse
        open_survey_a.status = "closed"
        open_survey_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="sv_resp_closed@acme.com", username="sv_resp_closed_acme")
        resp = c.post(reverse("hrm:survey_respond", args=[open_survey_a.pk]), self._answer_data())
        assert resp.status_code == 302
        assert not SurveyResponse.objects.filter(survey=open_survey_a).exists()

    def test_respond_redirect_for_user_without_linked_profile(self, client_a, open_survey_a):
        resp = client_a.get(reverse("hrm:survey_respond", args=[open_survey_a.pk]))
        assert resp.status_code == 302


class TestSurveyResults:
    def test_403_for_non_admin(self, tenant_a, employee_a, open_survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_res_na@acme.com", username="sv_res_na_acme")
        resp = c.get(reverse("hrm:survey_results", args=[open_survey_a.pk]))
        assert resp.status_code == 403

    def test_200_for_admin(self, client_a, open_survey_a, survey_response_a):
        resp = client_a.get(reverse("hrm:survey_results", args=[open_survey_a.pk]))
        assert resp.status_code == 200

    def test_rating_average_computed(self, client_a, open_survey_a, survey_response_a):
        resp = client_a.get(reverse("hrm:survey_results", args=[open_survey_a.pk]))
        rating_entry = resp.context["results"][0]
        assert rating_entry["type"] == "rating"
        assert rating_entry["average"] == 9.0
        assert rating_entry["count"] == 1

    def test_single_choice_counts(self, client_a, open_survey_a, survey_response_a):
        resp = client_a.get(reverse("hrm:survey_results", args=[open_survey_a.pk]))
        choice_entry = resp.context["results"][2]
        assert choice_entry["type"] == "single_choice"
        remote = next(c for c in choice_entry["choices"] if c["option"] == "Remote")
        assert remote["count"] == 1

    def test_text_answer_includes_respondent_when_not_anonymous(self, client_a, open_survey_a, survey_response_a):
        resp = client_a.get(reverse("hrm:survey_results", args=[open_survey_a.pk]))
        text_entry = resp.context["results"][1]
        assert text_entry["answers"][0]["who"] == "Alice Smith"

    def test_text_answer_hides_respondent_when_anonymous(self, client_a, open_survey_a, survey_response_a):
        open_survey_a.is_anonymous = True
        open_survey_a.save(update_fields=["is_anonymous"])
        resp = client_a.get(reverse("hrm:survey_results", args=[open_survey_a.pk]))
        text_entry = resp.context["results"][1]
        assert text_entry["answers"][0]["who"] is None

    def test_response_count_context(self, client_a, open_survey_a, survey_response_a):
        resp = client_a.get(reverse("hrm:survey_results", args=[open_survey_a.pk]))
        assert resp.context["response_count"] == 1

    def test_results_get_403_not_get_not_allowed_for_admin(self, client_a, open_survey_a):
        # survey_results has no @require_POST — GET is the normal admin action.
        resp = client_a.get(reverse("hrm:survey_results", args=[open_survey_a.pk]))
        assert resp.status_code == 200


# ================================================================ Suggestion — list/create
class TestSuggestionListView:
    def test_list_200(self, client_a, suggestion_a):
        resp = client_a.get(reverse("hrm:suggestion_list"))
        assert resp.status_code == 200

    def test_list_shows_own_for_self_scoped_employee(self, tenant_a, employee_a, suggestion_a):
        c = _client_for(employee_a.party, tenant_a, email="sug_list@acme.com", username="sug_list_acme")
        resp = c.get(reverse("hrm:suggestion_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert suggestion_a.pk in pks

    def test_list_filter_by_status(self, client_a, suggestion_a):
        resp = client_a.get(reverse("hrm:suggestion_list"), {"status": "draft"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert suggestion_a.pk in pks

    def test_list_filter_by_category(self, client_a, suggestion_a):
        resp = client_a.get(reverse("hrm:suggestion_list"), {"category": "workplace"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert suggestion_a.pk in pks

    def test_list_search_by_title(self, client_a, suggestion_a):
        resp = client_a.get(reverse("hrm:suggestion_list"), {"q": "bike rack"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert suggestion_a.pk in pks

    def test_list_has_choices_context_for_admin(self, client_a, suggestion_a):
        resp = client_a.get(reverse("hrm:suggestion_list"))
        assert resp.context["is_admin"] is True
        assert "status_choices" in resp.context
        assert "category_choices" in resp.context
        assert "employees" in resp.context

    def test_list_query_count_bounded(self, client_a, suggestion_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:suggestion_list"))


class TestSuggestionCreateView:
    def test_get_200_for_self_scoped_employee(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="sug_self@acme.com", username="sug_self_acme")
        resp = c.get(reverse("hrm:suggestion_create"))
        assert resp.status_code == 200

    def test_post_creates_draft_for_self(self, tenant_a, employee_a):
        from apps.hrm.models import Suggestion
        c = _client_for(employee_a.party, tenant_a, email="sug_self2@acme.com", username="sug_self2_acme")
        resp = c.post(reverse("hrm:suggestion_create"), _suggestion_post_data())
        assert resp.status_code == 302
        sug = Suggestion.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert sug is not None
        assert sug.status == "draft"

    def test_post_creates_for_admin_targeting_employee(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import Suggestion
        resp = client_a.post(
            reverse("hrm:suggestion_create"), _suggestion_post_data(employee_pk=str(employee_a.pk)))
        assert resp.status_code == 302
        assert Suggestion.objects.filter(tenant=tenant_a, employee=employee_a).exists()

    def test_form_has_no_employee_tenant_status_number_fields(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="sug_form@acme.com", username="sug_form_acme")
        resp = c.get(reverse("hrm:suggestion_create"))
        fields = resp.context["form"].fields
        for excluded in ("employee", "tenant", "status", "number"):
            assert excluded not in fields


# ================================================================ Suggestion — detail/edit/delete
class TestSuggestionDetailEditDelete:
    def test_detail_200_for_owner(self, tenant_a, employee_a, suggestion_a):
        c = _client_for(employee_a.party, tenant_a, email="sug_det@acme.com", username="sug_det_acme")
        resp = c.get(reverse("hrm:suggestion_detail", args=[suggestion_a.pk]))
        assert resp.status_code == 200

    def test_detail_200_for_admin(self, client_a, suggestion_a):
        resp = client_a.get(reverse("hrm:suggestion_detail", args=[suggestion_a.pk]))
        assert resp.status_code == 200

    def test_detail_403_for_a_different_employee(self, tenant_a, employee_a2, suggestion_a):
        c = _client_for(employee_a2.party, tenant_a, email="sug_det_other@acme.com", username="sug_det_other_acme")
        resp = c.get(reverse("hrm:suggestion_detail", args=[suggestion_a.pk]))
        assert resp.status_code == 403

    def test_edit_blocked_when_not_open(self, tenant_a, employee_a, suggestion_a):
        suggestion_a.status = "approved"
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="sug_edit@acme.com", username="sug_edit_acme")
        resp = c.get(reverse("hrm:suggestion_edit", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:suggestion_detail", args=[suggestion_a.pk])

    def test_edit_post_updates_when_open(self, tenant_a, employee_a, suggestion_a):
        c = _client_for(employee_a.party, tenant_a, email="sug_edit2@acme.com", username="sug_edit2_acme")
        resp = c.post(
            reverse("hrm:suggestion_edit", args=[suggestion_a.pk]),
            _suggestion_post_data(title="Add TWO bike racks"))
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.title == "Add TWO bike racks"

    def test_delete_post_removes_when_open(self, tenant_a, employee_a, suggestion_a):
        from apps.hrm.models import Suggestion
        c = _client_for(employee_a.party, tenant_a, email="sug_del@acme.com", username="sug_del_acme")
        pk = suggestion_a.pk
        resp = c.post(reverse("hrm:suggestion_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Suggestion.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_not_open(self, tenant_a, employee_a, suggestion_a):
        from apps.hrm.models import Suggestion
        suggestion_a.status = "cancelled"
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="sug_del2@acme.com", username="sug_del2_acme")
        resp = c.post(reverse("hrm:suggestion_delete", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        assert Suggestion.objects.filter(pk=suggestion_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, suggestion_a):
        resp = client_a.get(reverse("hrm:suggestion_delete", args=[suggestion_a.pk]))
        assert resp.status_code == 405


# ================================================================ Suggestion — workflow
class TestSuggestionWorkflow:
    def test_submit_draft_to_pending_by_owner(self, tenant_a, employee_a, suggestion_a):
        c = _client_for(employee_a.party, tenant_a, email="sug_sub@acme.com", username="sug_sub_acme")
        resp = c.post(reverse("hrm:suggestion_submit", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "pending"

    def test_cancel_by_owner_sets_cancelled(self, tenant_a, employee_a, suggestion_a):
        c = _client_for(employee_a.party, tenant_a, email="sug_can@acme.com", username="sug_can_acme")
        resp = c.post(reverse("hrm:suggestion_cancel", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "cancelled"

    def test_approve_by_admin_sets_approved(self, client_a, admin_user, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:suggestion_approve", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "approved"
        assert suggestion_a.approver_id == admin_user.pk
        assert suggestion_a.approved_at is not None

    def test_approve_403_for_non_admin(self, tenant_a, employee_a2, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="sug_appr_na@acme.com", username="sug_appr_na_acme")
        resp = c.post(reverse("hrm:suggestion_approve", args=[suggestion_a.pk]))
        assert resp.status_code == 403
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "pending"

    def test_reject_requires_non_blank_decision_note(self, client_a, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:suggestion_reject", args=[suggestion_a.pk]), {"decision_note": ""})
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "pending"  # unchanged

    def test_reject_with_note_sets_rejected(self, client_a, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        resp = client_a.post(
            reverse("hrm:suggestion_reject", args=[suggestion_a.pk]), {"decision_note": "Not feasible"})
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "rejected"
        assert suggestion_a.decision_note == "Not feasible"

    def test_reject_403_for_non_admin(self, tenant_a, employee_a2, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="sug_rej_na@acme.com", username="sug_rej_na_acme")
        resp = c.post(reverse("hrm:suggestion_reject", args=[suggestion_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 403
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "pending"

    def test_implement_approved_to_implemented(self, client_a, suggestion_a):
        suggestion_a.status = "approved"
        suggestion_a.save(update_fields=["status"])
        resp = client_a.post(
            reverse("hrm:suggestion_implement", args=[suggestion_a.pk]),
            {"implementation_note": "Installed a 10-slot rack."})
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "implemented"
        assert suggestion_a.implemented_at is not None
        assert suggestion_a.implementation_note == "Installed a 10-slot rack."

    def test_implement_blocked_when_not_approved(self, client_a, suggestion_a):
        client_a.post(reverse("hrm:suggestion_implement", args=[suggestion_a.pk]), {})  # still draft
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "draft"

    def test_implement_403_for_non_admin(self, tenant_a, employee_a2, suggestion_a):
        suggestion_a.status = "approved"
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="sug_impl_na@acme.com", username="sug_impl_na_acme")
        resp = c.post(reverse("hrm:suggestion_implement", args=[suggestion_a.pk]), {})
        assert resp.status_code == 403
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "approved"

    def test_implement_get_not_allowed(self, client_a, suggestion_a):
        resp = client_a.get(reverse("hrm:suggestion_implement", args=[suggestion_a.pk]))
        assert resp.status_code == 405


class TestSuggestionSelfApprovalGuard:
    def test_approve_blocked_when_admin_is_subject_employee(self, tenant_a, employee_a, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        c = _admin_linked_to(
            employee_a.party, tenant_a, email="sug_admin_emp@acme.com", username="sug_admin_emp_acme")
        resp = c.post(reverse("hrm:suggestion_approve", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "pending"

    def test_reject_blocked_when_admin_is_subject_employee(self, tenant_a, employee_a, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        c = _admin_linked_to(
            employee_a.party, tenant_a, email="sug_admin_emp2@acme.com", username="sug_admin_emp2_acme")
        resp = c.post(reverse("hrm:suggestion_reject", args=[suggestion_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "pending"

    def test_approve_allowed_by_a_different_admin(self, client_a, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:suggestion_approve", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "approved"
