"""Security tests for HRM 3.27 Communication Hub: anonymous redirect-to-login on every view,
cross-tenant IDOR (404) on ``Announcement``/``Survey``/``Suggestion`` detail/edit/delete/workflow
actions (+ list isolation), admin-only gating on the admin-authored actions (announcement
create/edit/delete/publish/archive; survey create/edit/delete/open/close/results; suggestion
approve/reject/implement), cross-EMPLOYEE IDOR on ``Suggestion`` (a non-admin employee can't read
another employee's suggestion — mirrors the 3.26 ownership-before-status guard), tenant is always
server-set (never smuggled via POST data, and creation is blocked outright when request.tenant is
None), and CSRF enforcement on the POST-only actions. Mirrors test_requests_security.py
conventions; client_a is the tenant admin (no linked employee)."""
import json

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _client_for(party, tenant, *, email, username, is_admin=False):
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


# ================================================================ Anonymous -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name", [
        "hrm:celebrations",
        "hrm:announcement_list", "hrm:announcement_create",
        "hrm:survey_list", "hrm:survey_create",
        "hrm:suggestion_list", "hrm:suggestion_create",
    ])
    def test_anon_redirected_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_announcement_detail_and_edit(self, client, announcement_a):
        for action in ("detail", "edit"):
            resp = client.get(reverse(f"hrm:announcement_{action}", args=[announcement_a.pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_announcement_post_only_actions(self, client, announcement_a):
        for action in ("delete", "publish", "archive"):
            resp = client.post(reverse(f"hrm:announcement_{action}", args=[announcement_a.pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_redirected_on_survey_detail_and_edit(self, client, survey_a):
        for action in ("detail", "edit"):
            resp = client.get(reverse(f"hrm:survey_{action}", args=[survey_a.pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_survey_post_only_actions(self, client, survey_a):
        for action in ("delete", "open", "close", "respond"):
            resp = client.post(reverse(f"hrm:survey_{action}", args=[survey_a.pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_redirected_on_survey_results(self, client, survey_a):
        resp = client.get(reverse("hrm:survey_results", args=[survey_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_suggestion_detail_and_edit(self, client, suggestion_a):
        for action in ("detail", "edit"):
            resp = client.get(reverse(f"hrm:suggestion_{action}", args=[suggestion_a.pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_suggestion_post_only_actions(self, client, suggestion_a):
        for action in ("delete", "submit", "cancel", "approve", "reject", "implement"):
            resp = client.post(reverse(f"hrm:suggestion_{action}", args=[suggestion_a.pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]


# ================================================================ Cross-tenant IDOR (404) — Announcement
class TestAnnouncementCrossTenantIDOR:
    def test_detail_cross_tenant_404(self, client_a, announcement_b):
        resp = client_a.get(reverse("hrm:announcement_detail", args=[announcement_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, announcement_b):
        resp = client_a.get(reverse("hrm:announcement_edit", args=[announcement_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404_does_not_mutate(self, client_a, announcement_b):
        original_title = announcement_b.title
        resp = client_a.post(
            reverse("hrm:announcement_edit", args=[announcement_b.pk]), _announcement_post_data())
        assert resp.status_code == 404
        announcement_b.refresh_from_db()
        assert announcement_b.title == original_title

    def test_delete_cross_tenant_404_row_survives(self, client_a, announcement_b):
        from apps.hrm.models import Announcement
        resp = client_a.post(reverse("hrm:announcement_delete", args=[announcement_b.pk]))
        assert resp.status_code == 404
        assert Announcement.objects.filter(pk=announcement_b.pk).exists()

    def test_publish_cross_tenant_404_status_unchanged(self, client_a, announcement_b):
        resp = client_a.post(reverse("hrm:announcement_publish", args=[announcement_b.pk]))
        assert resp.status_code == 404
        announcement_b.refresh_from_db()
        assert announcement_b.status == "draft"

    def test_archive_cross_tenant_404_status_unchanged(self, client_a, announcement_b):
        announcement_b.status = "published"
        announcement_b.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:announcement_archive", args=[announcement_b.pk]))
        assert resp.status_code == 404
        announcement_b.refresh_from_db()
        assert announcement_b.status == "published"

    def test_list_excludes_b_rows(self, client_a, announcement_a, announcement_b):
        resp = client_a.get(reverse("hrm:announcement_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert announcement_a.pk in pks
        assert announcement_b.pk not in pks


# ================================================================ Cross-tenant IDOR (404) — Survey
class TestSurveyCrossTenantIDOR:
    def test_detail_cross_tenant_404(self, client_a, survey_b):
        resp = client_a.get(reverse("hrm:survey_detail", args=[survey_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, survey_b):
        resp = client_a.get(reverse("hrm:survey_edit", args=[survey_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404_row_survives(self, client_a, survey_b):
        from apps.hrm.models import Survey
        resp = client_a.post(reverse("hrm:survey_delete", args=[survey_b.pk]))
        assert resp.status_code == 404
        assert Survey.objects.filter(pk=survey_b.pk).exists()

    def test_open_cross_tenant_404_status_unchanged(self, client_a, survey_b):
        resp = client_a.post(reverse("hrm:survey_open", args=[survey_b.pk]))
        assert resp.status_code == 404
        survey_b.refresh_from_db()
        assert survey_b.status == "draft"

    def test_close_cross_tenant_404_status_unchanged(self, client_a, survey_b):
        survey_b.status = "open"
        survey_b.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:survey_close", args=[survey_b.pk]))
        assert resp.status_code == 404
        survey_b.refresh_from_db()
        assert survey_b.status == "open"

    def test_respond_cross_tenant_404_no_response_created(self, tenant_a, employee_a, survey_b):
        from apps.hrm.models import SurveyResponse
        survey_b.status = "open"
        survey_b.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="sv_ct_resp@acme.com", username="sv_ct_resp_acme")
        resp = c.post(
            reverse("hrm:survey_respond", args=[survey_b.pk]), {"q_0": "1", "q_1": "x", "q_2": "Remote"})
        assert resp.status_code == 404
        assert not SurveyResponse.objects.filter(survey=survey_b).exists()

    def test_results_cross_tenant_404(self, client_a, survey_b):
        resp = client_a.get(reverse("hrm:survey_results", args=[survey_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_rows(self, client_a, survey_a, survey_b):
        resp = client_a.get(reverse("hrm:survey_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert survey_a.pk in pks
        assert survey_b.pk not in pks


# ================================================================ Cross-tenant IDOR (404) — Suggestion
class TestSuggestionCrossTenantIDOR:
    def test_detail_cross_tenant_404(self, client_a, suggestion_b):
        resp = client_a.get(reverse("hrm:suggestion_detail", args=[suggestion_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, suggestion_b):
        resp = client_a.get(reverse("hrm:suggestion_edit", args=[suggestion_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404_does_not_mutate(self, client_a, suggestion_b):
        original_number = suggestion_b.number
        resp = client_a.post(
            reverse("hrm:suggestion_edit", args=[suggestion_b.pk]), _suggestion_post_data())
        assert resp.status_code == 404
        suggestion_b.refresh_from_db()
        assert suggestion_b.number == original_number

    def test_delete_cross_tenant_404_row_survives(self, client_a, suggestion_b):
        from apps.hrm.models import Suggestion
        resp = client_a.post(reverse("hrm:suggestion_delete", args=[suggestion_b.pk]))
        assert resp.status_code == 404
        assert Suggestion.objects.filter(pk=suggestion_b.pk).exists()

    def test_submit_cancel_cross_tenant_404_status_unchanged(self, client_a, suggestion_b):
        original_status = suggestion_b.status
        for action in ("submit", "cancel"):
            resp = client_a.post(reverse(f"hrm:suggestion_{action}", args=[suggestion_b.pk]))
            assert resp.status_code == 404
        suggestion_b.refresh_from_db()
        assert suggestion_b.status == original_status

    def test_approve_reject_cross_tenant_404_status_unchanged(self, client_a, suggestion_b):
        suggestion_b.status = "pending"
        suggestion_b.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:suggestion_approve", args=[suggestion_b.pk]))
        assert resp.status_code == 404
        resp = client_a.post(
            reverse("hrm:suggestion_reject", args=[suggestion_b.pk]), {"decision_note": "no"})
        assert resp.status_code == 404
        suggestion_b.refresh_from_db()
        assert suggestion_b.status == "pending"

    def test_implement_cross_tenant_404(self, client_a, suggestion_b):
        suggestion_b.status = "approved"
        suggestion_b.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:suggestion_implement", args=[suggestion_b.pk]))
        assert resp.status_code == 404
        suggestion_b.refresh_from_db()
        assert suggestion_b.status == "approved"

    def test_list_excludes_b_rows(self, client_a, suggestion_a, suggestion_b):
        resp = client_a.get(reverse("hrm:suggestion_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert suggestion_a.pk in pks
        assert suggestion_b.pk not in pks

    def test_create_cross_tenant_target_employee_ignored(self, client_a, suggestion_b):
        """An admin trying to target a Tenant-B employee via employee_pk on the create form is
        silently ignored (``_ss_child_create`` filters the lookup by ``tenant=request.tenant``)."""
        from apps.hrm.models import Suggestion
        before = Suggestion.objects.filter(tenant=suggestion_b.tenant).count()
        resp = client_a.post(
            reverse("hrm:suggestion_create"),
            _suggestion_post_data(employee_pk=str(suggestion_b.employee_id)))
        assert resp.status_code == 302
        assert Suggestion.objects.filter(tenant=suggestion_b.tenant).count() == before


# ================================================================ Cross-EMPLOYEE IDOR (same tenant) — Suggestion
class TestSuggestionCrossEmployeeIDOR:
    def test_detail_403_for_other_employee(self, tenant_a, employee_a2, suggestion_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_sug_det@acme.com", username="ce_sug_det_acme")
        resp = c.get(reverse("hrm:suggestion_detail", args=[suggestion_a.pk]))
        assert resp.status_code == 403

    def test_edit_get_redirects_to_detail_for_other_employee_when_open(
        self, tenant_a, employee_a2, suggestion_a
    ):
        c = _client_for(employee_a2.party, tenant_a, email="ce_sug_edit@acme.com", username="ce_sug_edit_acme")
        resp = c.get(reverse("hrm:suggestion_edit", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:suggestion_detail", args=[suggestion_a.pk])

    def test_edit_get_redirects_to_detail_for_other_employee_even_when_decided(
        self, tenant_a, employee_a2, suggestion_a
    ):
        """Ownership is checked BEFORE the open-status branch: a non-owner gets the same 'your own
        records' redirect even when the row is in a DECIDED (non-open) status."""
        suggestion_a.status = "rejected"
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="ce_sug_edit2@acme.com", username="ce_sug_edit2_acme")
        resp = c.get(reverse("hrm:suggestion_edit", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:suggestion_detail", args=[suggestion_a.pk])

    def test_edit_post_does_not_mutate_for_other_employee(self, tenant_a, employee_a2, suggestion_a):
        original_number = suggestion_a.number
        c = _client_for(employee_a2.party, tenant_a, email="ce_sug_edit3@acme.com", username="ce_sug_edit3_acme")
        c.post(reverse("hrm:suggestion_edit", args=[suggestion_a.pk]), _suggestion_post_data())
        suggestion_a.refresh_from_db()
        assert suggestion_a.number == original_number

    def test_delete_redirects_and_row_survives_for_other_employee_regardless_of_status(
        self, tenant_a, employee_a2, suggestion_a
    ):
        from apps.hrm.models import Suggestion
        suggestion_a.status = "approved"  # a NON-open status — ownership must still gate first
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="ce_sug_del@acme.com", username="ce_sug_del_acme")
        resp = c.post(reverse("hrm:suggestion_delete", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        assert Suggestion.objects.filter(pk=suggestion_a.pk).exists()

    def test_submit_redirects_and_status_unchanged_for_other_employee(
        self, tenant_a, employee_a2, suggestion_a
    ):
        c = _client_for(employee_a2.party, tenant_a, email="ce_sug_sub@acme.com", username="ce_sug_sub_acme")
        resp = c.post(reverse("hrm:suggestion_submit", args=[suggestion_a.pk]))
        assert resp.status_code == 302
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "draft"  # unchanged

    def test_list_hides_other_employee_rows(self, tenant_a, employee_a2, suggestion_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_sug_list@acme.com", username="ce_sug_list_acme")
        resp = c.get(reverse("hrm:suggestion_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert suggestion_a.pk not in pks


# ================================================================ Admin-only actions
class TestAnnouncementAdminOnly:
    @pytest.mark.parametrize("action", ["edit", "delete", "publish", "archive"])
    def test_403_for_non_admin(self, tenant_a, employee_a, announcement_a, action):
        c = _client_for(employee_a.party, tenant_a, email=f"ann_ao_{action}@acme.com",
                        username=f"ann_ao_{action}_acme")
        if action == "edit":
            resp = c.get(reverse(f"hrm:announcement_{action}", args=[announcement_a.pk]))
        else:
            resp = c.post(reverse(f"hrm:announcement_{action}", args=[announcement_a.pk]))
        assert resp.status_code == 403

    def test_create_403_for_non_admin(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="ann_ao_create@acme.com", username="ann_ao_create_acme")
        resp = c.get(reverse("hrm:announcement_create"))
        assert resp.status_code == 403


class TestSurveyAdminOnly:
    @pytest.mark.parametrize("action", ["edit", "delete", "open", "results"])
    def test_403_for_non_admin(self, tenant_a, employee_a, survey_a, action):
        c = _client_for(employee_a.party, tenant_a, email=f"sv_ao_{action}@acme.com",
                        username=f"sv_ao_{action}_acme")
        if action in ("edit", "results"):
            resp = c.get(reverse(f"hrm:survey_{action}", args=[survey_a.pk]))
        else:
            resp = c.post(reverse(f"hrm:survey_{action}", args=[survey_a.pk]))
        assert resp.status_code == 403

    def test_close_403_for_non_admin(self, tenant_a, employee_a, open_survey_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_ao_close@acme.com", username="sv_ao_close_acme")
        resp = c.post(reverse("hrm:survey_close", args=[open_survey_a.pk]))
        assert resp.status_code == 403

    def test_create_403_for_non_admin(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="sv_ao_create@acme.com", username="sv_ao_create_acme")
        resp = c.get(reverse("hrm:survey_create"))
        assert resp.status_code == 403


class TestSuggestionReviewActionsAdminOnly:
    def test_approve_403_for_non_admin(self, tenant_a, employee_a2, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="na_sug_appr@acme.com", username="na_sug_appr_acme")
        resp = c.post(reverse("hrm:suggestion_approve", args=[suggestion_a.pk]))
        assert resp.status_code == 403
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "pending"

    def test_reject_403_for_non_admin(self, tenant_a, employee_a2, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="na_sug_rej@acme.com", username="na_sug_rej_acme")
        resp = c.post(reverse("hrm:suggestion_reject", args=[suggestion_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 403
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "pending"

    def test_implement_403_for_non_admin(self, tenant_a, employee_a2, suggestion_a):
        suggestion_a.status = "approved"
        suggestion_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="na_sug_impl@acme.com", username="na_sug_impl_acme")
        resp = c.post(reverse("hrm:suggestion_implement", args=[suggestion_a.pk]))
        assert resp.status_code == 403
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "approved"


# ================================================================ Tenant is server-set, never smuggled
class TestTenantServerSet:
    def test_announcement_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b):
        from apps.hrm.models import Announcement
        resp = client_a.post(
            reverse("hrm:announcement_create"), _announcement_post_data(tenant=tenant_b.pk))
        assert resp.status_code == 302
        obj = Announcement.objects.filter(tenant=tenant_a).first()
        assert obj is not None
        assert obj.tenant_id == tenant_a.pk

    def test_announcement_create_blocked_when_request_tenant_is_none(self):
        from apps.accounts.models import User
        from apps.hrm.models import Announcement
        superuser = User.objects.create_superuser(
            email="notenant_ann@example.com", username="notenant_ann_user", password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        resp = c.post(reverse("hrm:announcement_create"), _announcement_post_data())
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not Announcement.objects.exists()

    def test_survey_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b, survey_questions):
        from apps.hrm.models import Survey
        resp = client_a.post(
            reverse("hrm:survey_create"), _survey_post_data(survey_questions, tenant=tenant_b.pk))
        assert resp.status_code == 302
        obj = Survey.objects.filter(tenant=tenant_a).first()
        assert obj is not None
        assert obj.tenant_id == tenant_a.pk

    def test_survey_create_blocked_when_request_tenant_is_none(self, survey_questions):
        from apps.accounts.models import User
        from apps.hrm.models import Survey
        superuser = User.objects.create_superuser(
            email="notenant_sv@example.com", username="notenant_sv_user", password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        resp = c.post(reverse("hrm:survey_create"), _survey_post_data(survey_questions))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not Survey.objects.exists()

    def test_suggestion_create_ignores_smuggled_tenant(self, tenant_a, tenant_b, employee_a):
        from apps.hrm.models import Suggestion
        c = _client_for(employee_a.party, tenant_a, email="tss_sug@acme.com", username="tss_sug_acme")
        resp = c.post(reverse("hrm:suggestion_create"), _suggestion_post_data(tenant=tenant_b.pk))
        assert resp.status_code == 302
        obj = Suggestion.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert obj is not None
        assert obj.tenant_id == tenant_a.pk

    def test_suggestion_create_blocked_when_request_tenant_is_none(self, employee_a):
        from apps.accounts.models import User
        from apps.hrm.models import Suggestion
        tenantless = User.objects.create_user(
            email="notenant_sug@example.com", username="notenant_sug_user",
            password="TestPass123!", tenant=None, is_tenant_admin=False)
        tenantless.party = employee_a.party
        tenantless.save(update_fields=["party"])
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse("hrm:suggestion_create"), _suggestion_post_data())
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not Suggestion.objects.filter(employee=employee_a).exists()


# ================================================================ CSRF enforcement
class TestCSRFEnforcement:
    def test_announcement_delete_enforces_csrf(self, admin_user, announcement_a):
        from apps.hrm.models import Announcement
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:announcement_delete", args=[announcement_a.pk]))
        assert resp.status_code == 403
        assert Announcement.objects.filter(pk=announcement_a.pk).exists()

    def test_announcement_create_enforces_csrf(self, admin_user, tenant_a):
        from apps.hrm.models import Announcement
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:announcement_create"), _announcement_post_data())
        assert resp.status_code == 403
        assert not Announcement.objects.filter(tenant=tenant_a).exists()

    def test_announcement_publish_enforces_csrf(self, admin_user, announcement_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:announcement_publish", args=[announcement_a.pk]))
        assert resp.status_code == 403
        announcement_a.refresh_from_db()
        assert announcement_a.status == "draft"

    def test_survey_delete_enforces_csrf(self, admin_user, survey_a):
        from apps.hrm.models import Survey
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:survey_delete", args=[survey_a.pk]))
        assert resp.status_code == 403
        assert Survey.objects.filter(pk=survey_a.pk).exists()

    def test_survey_open_enforces_csrf(self, admin_user, survey_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:survey_open", args=[survey_a.pk]))
        assert resp.status_code == 403
        survey_a.refresh_from_db()
        assert survey_a.status == "draft"

    def test_survey_respond_enforces_csrf(self, tenant_a, employee_a, open_survey_a):
        from apps.hrm.models import SurveyResponse
        c = _client_for(employee_a.party, tenant_a, email="csrf_sv_resp@acme.com", username="csrf_sv_resp_acme")
        c.handler.enforce_csrf_checks = True
        resp = c.post(
            reverse("hrm:survey_respond", args=[open_survey_a.pk]), {"q_0": "5", "q_1": "x", "q_2": "Remote"})
        assert resp.status_code == 403
        assert not SurveyResponse.objects.filter(survey=open_survey_a, employee=employee_a).exists()

    def test_suggestion_delete_enforces_csrf(self, tenant_a, employee_a, suggestion_a):
        from apps.hrm.models import Suggestion
        c = _client_for(employee_a.party, tenant_a, email="csrf_sug_del@acme.com", username="csrf_sug_del_acme")
        c.handler.enforce_csrf_checks = True
        resp = c.post(reverse("hrm:suggestion_delete", args=[suggestion_a.pk]))
        assert resp.status_code == 403
        assert Suggestion.objects.filter(pk=suggestion_a.pk).exists()

    def test_suggestion_create_enforces_csrf(self, tenant_a, employee_a):
        from apps.hrm.models import Suggestion
        c = _client_for(employee_a.party, tenant_a, email="csrf_sug_create@acme.com", username="csrf_sug_create_acme")
        c.handler.enforce_csrf_checks = True
        resp = c.post(reverse("hrm:suggestion_create"), _suggestion_post_data())
        assert resp.status_code == 403
        assert not Suggestion.objects.filter(tenant=tenant_a, employee=employee_a).exists()

    def test_suggestion_approve_enforces_csrf(self, admin_user, suggestion_a):
        suggestion_a.status = "pending"
        suggestion_a.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:suggestion_approve", args=[suggestion_a.pk]))
        assert resp.status_code == 403
        suggestion_a.refresh_from_db()
        assert suggestion_a.status == "pending"
