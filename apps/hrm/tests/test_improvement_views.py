"""Tests for HRM 3.21 Performance Improvement views: PerformanceImprovementPlan CRUD + the
draft->pending_hr_approval->active->closed workflow chain (submit/hr_approve/acknowledge/close/
extend); PIPCheckIn nested create/detail/edit/delete; WarningLetter CRUD + issue/acknowledge/print;
CoachingNote CRUD. Cross-tenant IDOR (404) for all 4 models. Mirrors test_feedback_views.py
conventions — client_a is the tenant admin."""
import datetime

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ PerformanceImprovementPlan CRUD
class TestPIPListView:
    def test_list_200(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pip_draft_a.pk in pks

    def test_list_filter_by_status(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pip_draft_a.pk in pks

    def test_list_filter_by_subject(self, client_a, pip_draft_a, employee_a):
        resp = client_a.get(reverse("hrm:pip_list"), {"subject": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pip_draft_a.pk in pks

    def test_list_filter_by_manager(self, client_a, pip_draft_a, employee_a2):
        resp = client_a.get(reverse("hrm:pip_list"), {"manager": employee_a2.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pip_draft_a.pk in pks

    def test_list_search_by_number(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_list"), {"q": pip_draft_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pip_draft_a.pk in pks

    def test_list_has_choices_context(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_list"))
        assert "status_choices" in resp.context
        assert "outcome_choices" in resp.context
        assert "employees" in resp.context
        assert "is_admin" in resp.context
        assert "current_profile_id" in resp.context


class TestPIPCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:pip_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import PerformanceImprovementPlan
        resp = client_a.post(reverse("hrm:pip_create"), {
            "subject": employee_a.pk, "manager": employee_a2.pk, "triggering_review": "",
            "performance_issue": "Missed deadlines.", "expected_standards": "On-time delivery.",
            "improvement_goals": "Hit every sprint commitment.", "support_provided": "",
            "measurement_criteria": "Sprint velocity.",
            "start_date": "2026-07-01", "end_date": "2026-09-29",
        })
        assert resp.status_code == 302
        pip = PerformanceImprovementPlan.objects.filter(tenant=tenant_a, subject=employee_a).first()
        assert pip is not None
        assert pip.tenant_id == tenant_a.pk
        assert pip.number.startswith("PIP-")
        assert pip.status == "draft"

    def test_post_invalid_subject_equal_manager_rejected(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import PerformanceImprovementPlan
        resp = client_a.post(reverse("hrm:pip_create"), {
            "subject": employee_a.pk, "manager": employee_a.pk, "triggering_review": "",
            "performance_issue": "x", "expected_standards": "x", "improvement_goals": "x",
            "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29",
        })
        assert resp.status_code == 200
        assert not PerformanceImprovementPlan.objects.filter(tenant=tenant_a, subject=employee_a, manager=employee_a).exists()

    def test_subject_and_manager_dropdowns_scoped_to_tenant(self, client_a, employee_a, employee_b):
        resp = client_a.get(reverse("hrm:pip_create"))
        subj_pks = list(resp.context["form"].fields["subject"].queryset.values_list("pk", flat=True))
        mgr_pks = list(resp.context["form"].fields["manager"].queryset.values_list("pk", flat=True))
        assert employee_a.pk in subj_pks
        assert employee_b.pk not in subj_pks
        assert employee_a.pk in mgr_pks
        assert employee_b.pk not in mgr_pks

    def test_form_has_no_workflow_or_system_fields(self, client_a):
        resp = client_a.get(reverse("hrm:pip_create"))
        fields = resp.context["form"].fields
        for excluded in ("status", "outcome", "outcome_date", "outcome_notes", "number",
                         "extended_end_date", "acknowledged_at", "acknowledged_by",
                         "hr_approved_at", "hr_approved_by"):
            assert excluded not in fields


class TestPIPDetailEditDelete:
    def test_detail_200(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_detail", args=[pip_draft_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_detail", args=[pip_draft_a.pk]))
        for key in ("obj", "checkins", "can_edit", "is_admin", "is_subject", "is_manager",
                    "can_add_checkin", "can_manage_checkin", "checkin_form"):
            assert key in resp.context

    def test_edit_get_200(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_edit", args=[pip_draft_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_performance_issue(self, client_a, pip_draft_a, employee_a, employee_a2):
        resp = client_a.post(reverse("hrm:pip_edit", args=[pip_draft_a.pk]), {
            "subject": employee_a.pk, "manager": employee_a2.pk, "triggering_review": "",
            "performance_issue": "Updated issue text.", "expected_standards": "x",
            "improvement_goals": "x", "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29",
        })
        assert resp.status_code == 302
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.performance_issue == "Updated issue text."

    def test_edit_blocked_once_not_draft(self, client_a, pip_active_a, employee_a, employee_a2):
        """_can_edit_pip locks once submitted — active plans redirect away from the edit form."""
        resp = client_a.get(reverse("hrm:pip_edit", args=[pip_active_a.pk]))
        assert resp.status_code == 302

    def test_delete_post_removes(self, client_a, pip_draft_a):
        from apps.hrm.models import PerformanceImprovementPlan
        pk = pip_draft_a.pk
        resp = client_a.post(reverse("hrm:pip_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PerformanceImprovementPlan.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_delete", args=[pip_draft_a.pk]))
        assert resp.status_code == 405


# ================================================================ PIP workflow chain
class TestPIPWorkflowChain:
    def test_submit_draft_to_pending_hr_approval(self, client_a, pip_draft_a):
        resp = client_a.post(reverse("hrm:pip_submit", args=[pip_draft_a.pk]))
        assert resp.status_code == 302
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.status == "pending_hr_approval"

    def test_submit_by_manager(self, tenant_a, pip_draft_a, employee_a2):
        from django.test import Client
        from apps.accounts.models import User
        manager_user = User.objects.create_user(
            email="carol_pip@acme.com", username="carol_pip_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        manager_user.party = employee_a2.party
        manager_user.save(update_fields=["party"])
        c = Client()
        c.force_login(manager_user)
        resp = c.post(reverse("hrm:pip_submit", args=[pip_draft_a.pk]))
        assert resp.status_code == 302
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.status == "pending_hr_approval"

    def test_submit_blocked_when_not_draft(self, client_a, pip_active_a):
        client_a.post(reverse("hrm:pip_submit", args=[pip_active_a.pk]))
        pip_active_a.refresh_from_db()
        assert pip_active_a.status == "active"  # unchanged

    def test_submit_get_not_allowed(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_submit", args=[pip_draft_a.pk]))
        assert resp.status_code == 405

    def test_hr_approve_pending_to_active_sets_approved_at_and_by(self, client_a, admin_user, pip_draft_a):
        pip_draft_a.status = "pending_hr_approval"
        pip_draft_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:pip_hr_approve", args=[pip_draft_a.pk]))
        assert resp.status_code == 302
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.status == "active"
        assert pip_draft_a.hr_approved_at is not None

    def test_hr_approve_blocked_for_non_admin(self, tenant_a, pip_draft_a, employee_a2):
        """@tenant_admin_required — a non-admin (even the manager) gets 403."""
        from django.test import Client
        from apps.accounts.models import User
        manager_user = User.objects.create_user(
            email="carol_pip2@acme.com", username="carol_pip2_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        manager_user.party = employee_a2.party
        manager_user.save(update_fields=["party"])
        c = Client()
        c.force_login(manager_user)
        resp = c.post(reverse("hrm:pip_hr_approve", args=[pip_draft_a.pk]))
        assert resp.status_code == 403
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.status == "draft"

    def test_hr_approve_get_not_allowed(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_hr_approve", args=[pip_draft_a.pk]))
        assert resp.status_code == 405

    def test_acknowledge_by_subject_sets_acknowledged_at_and_by(self, tenant_a, pip_active_a, employee_a):
        from django.test import Client
        from apps.accounts.models import User
        subject_user = User.objects.create_user(
            email="alice_pip@acme.com", username="alice_pip_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        subject_user.party = employee_a.party
        subject_user.save(update_fields=["party"])
        c = Client()
        c.force_login(subject_user)
        resp = c.post(reverse("hrm:pip_acknowledge", args=[pip_active_a.pk]))
        assert resp.status_code == 302
        pip_active_a.refresh_from_db()
        assert pip_active_a.acknowledged_at is not None
        assert pip_active_a.acknowledged_by_id == employee_a.pk

    def test_acknowledge_forbidden_for_non_subject(self, tenant_a, pip_active_a, employee_a2):
        """The manager (non-subject, non-admin) may NOT acknowledge — only the subject can."""
        from django.test import Client
        from apps.accounts.models import User
        manager_user = User.objects.create_user(
            email="carol_pip3@acme.com", username="carol_pip3_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        manager_user.party = employee_a2.party
        manager_user.save(update_fields=["party"])
        c = Client()
        c.force_login(manager_user)
        resp = c.post(reverse("hrm:pip_acknowledge", args=[pip_active_a.pk]))
        assert resp.status_code == 403
        pip_active_a.refresh_from_db()
        assert pip_active_a.acknowledged_at is None

    def test_acknowledge_get_not_allowed(self, client_a, pip_active_a):
        resp = client_a.get(reverse("hrm:pip_acknowledge", args=[pip_active_a.pk]))
        assert resp.status_code == 405

    def test_close_post_with_outcome_sets_closed_and_outcome_date(self, client_a, pip_active_a):
        """Assert outcome/outcome_date saved AND the model's outcome-iff-closed clean() passes
        because pip_close sets status=closed on the instance before validation."""
        resp = client_a.post(reverse("hrm:pip_close", args=[pip_active_a.pk]), {
            "outcome": "successful", "outcome_date": "", "outcome_notes": "Met all goals.",
        })
        assert resp.status_code == 302
        pip_active_a.refresh_from_db()
        assert pip_active_a.status == "closed"
        assert pip_active_a.outcome == "successful"
        assert pip_active_a.outcome_date is not None  # defaulted to today by the view

    def test_close_requires_admin(self, tenant_a, pip_active_a, employee_a2):
        from django.test import Client
        from apps.accounts.models import User
        manager_user = User.objects.create_user(
            email="carol_pip4@acme.com", username="carol_pip4_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        manager_user.party = employee_a2.party
        manager_user.save(update_fields=["party"])
        c = Client()
        c.force_login(manager_user)
        resp = c.post(reverse("hrm:pip_close", args=[pip_active_a.pk]), {
            "outcome": "successful", "outcome_date": "", "outcome_notes": "",
        })
        assert resp.status_code == 403
        pip_active_a.refresh_from_db()
        assert pip_active_a.status == "active"

    def test_close_blocked_when_not_active(self, client_a, pip_draft_a):
        resp = client_a.post(reverse("hrm:pip_close", args=[pip_draft_a.pk]), {
            "outcome": "successful", "outcome_date": "", "outcome_notes": "",
        })
        assert resp.status_code == 302
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.status == "draft"  # unchanged

    def test_close_get_200_renders_form(self, client_a, pip_active_a):
        resp = client_a.get(reverse("hrm:pip_close", args=[pip_active_a.pk]))
        assert resp.status_code == 200

    def test_close_missing_outcome_rejected(self, client_a, pip_active_a):
        resp = client_a.post(reverse("hrm:pip_close", args=[pip_active_a.pk]), {
            "outcome": "", "outcome_date": "", "outcome_notes": "",
        })
        assert resp.status_code == 200  # re-renders with form error
        pip_active_a.refresh_from_db()
        assert pip_active_a.status == "active"  # unchanged

    def test_extend_sets_extended_end_date(self, client_a, pip_active_a):
        new_end = (pip_active_a.end_date + datetime.timedelta(days=30)).isoformat()
        resp = client_a.post(reverse("hrm:pip_extend", args=[pip_active_a.pk]), {
            "extended_end_date": new_end,
        })
        assert resp.status_code == 302
        pip_active_a.refresh_from_db()
        assert pip_active_a.extended_end_date.isoformat() == new_end

    def test_extend_rejects_date_not_after_current_end(self, client_a, pip_active_a):
        same_as_end = pip_active_a.end_date.isoformat()
        resp = client_a.post(reverse("hrm:pip_extend", args=[pip_active_a.pk]), {
            "extended_end_date": same_as_end,
        })
        assert resp.status_code == 302
        pip_active_a.refresh_from_db()
        assert pip_active_a.extended_end_date is None  # rejected, unchanged

    def test_extend_rejects_date_before_current_end(self, client_a, pip_active_a):
        earlier = (pip_active_a.end_date - datetime.timedelta(days=1)).isoformat()
        resp = client_a.post(reverse("hrm:pip_extend", args=[pip_active_a.pk]), {
            "extended_end_date": earlier,
        })
        pip_active_a.refresh_from_db()
        assert pip_active_a.extended_end_date is None

    def test_extend_requires_admin(self, tenant_a, pip_active_a, employee_a2):
        from django.test import Client
        from apps.accounts.models import User
        manager_user = User.objects.create_user(
            email="carol_pip5@acme.com", username="carol_pip5_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        manager_user.party = employee_a2.party
        manager_user.save(update_fields=["party"])
        c = Client()
        c.force_login(manager_user)
        new_end = (pip_active_a.end_date + datetime.timedelta(days=30)).isoformat()
        resp = c.post(reverse("hrm:pip_extend", args=[pip_active_a.pk]), {"extended_end_date": new_end})
        assert resp.status_code == 403

    def test_extend_get_not_allowed(self, client_a, pip_active_a):
        resp = client_a.get(reverse("hrm:pip_extend", args=[pip_active_a.pk]))
        assert resp.status_code == 405


# ================================================================ PIPCheckIn nested CRUD
class TestPIPCheckInCreateView:
    def test_get_200(self, client_a, pip_active_a):
        resp = client_a.get(reverse("hrm:pipcheckin_create", args=[pip_active_a.pk]))
        assert resp.status_code == 200

    def test_post_creates_with_tenant_and_pip_from_url(self, client_a, tenant_a, pip_active_a):
        from apps.hrm.models import PIPCheckIn
        resp = client_a.post(reverse("hrm:pipcheckin_create", args=[pip_active_a.pk]), {
            "checkin_date": "2026-07-20", "progress_rating": "at_risk", "progress_notes": "Slipping.",
        })
        assert resp.status_code == 302
        ci = PIPCheckIn.objects.filter(tenant=tenant_a, pip=pip_active_a, progress_rating="at_risk").first()
        assert ci is not None
        assert ci.pip_id == pip_active_a.pk
        assert ci.tenant_id == tenant_a.pk
        assert ci.number.startswith("PCI-")
        assert ci.completed_at is not None

    def test_blocked_when_pip_closed(self, client_a, pip_active_a):
        pip_active_a.status = "closed"
        pip_active_a.outcome = "successful"
        pip_active_a.save(update_fields=["status", "outcome"])
        resp = client_a.get(reverse("hrm:pipcheckin_create", args=[pip_active_a.pk]))
        assert resp.status_code == 302

    def test_form_has_no_pip_or_workflow_fields(self, client_a, pip_active_a):
        resp = client_a.get(reverse("hrm:pipcheckin_create", args=[pip_active_a.pk]))
        fields = resp.context["form"].fields
        assert "pip" not in fields
        assert "number" not in fields
        assert "completed_at" not in fields


class TestPIPCheckInDetailEditDelete:
    def test_detail_200(self, client_a, pipcheckin_a):
        resp = client_a.get(reverse("hrm:pipcheckin_detail", args=[pipcheckin_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, pipcheckin_a):
        resp = client_a.get(reverse("hrm:pipcheckin_detail", args=[pipcheckin_a.pk]))
        assert "obj" in resp.context
        assert "pip" in resp.context
        assert "can_manage_checkin" in resp.context

    def test_edit_get_200(self, client_a, pipcheckin_a):
        resp = client_a.get(reverse("hrm:pipcheckin_edit", args=[pipcheckin_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_progress_notes(self, client_a, pipcheckin_a):
        resp = client_a.post(reverse("hrm:pipcheckin_edit", args=[pipcheckin_a.pk]), {
            "checkin_date": pipcheckin_a.checkin_date.isoformat(), "progress_rating": "off_track",
            "progress_notes": "Regressed badly.",
        })
        assert resp.status_code == 302
        pipcheckin_a.refresh_from_db()
        assert pipcheckin_a.progress_rating == "off_track"

    def test_delete_post_removes(self, client_a, pipcheckin_a):
        from apps.hrm.models import PIPCheckIn
        pk = pipcheckin_a.pk
        resp = client_a.post(reverse("hrm:pipcheckin_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PIPCheckIn.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, pipcheckin_a):
        resp = client_a.get(reverse("hrm:pipcheckin_delete", args=[pipcheckin_a.pk]))
        assert resp.status_code == 405


# ================================================================ WarningLetter CRUD
class TestWarningLetterListView:
    def test_list_200(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert warning_draft_a.pk in pks

    def test_list_filter_by_level(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_list"), {"level": "verbal"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert warning_draft_a.pk in pks

    def test_list_filter_by_category(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_list"), {"category": "attendance"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert warning_draft_a.pk in pks

    def test_list_filter_by_status(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert warning_draft_a.pk in pks

    def test_list_filter_by_issued_to(self, client_a, warning_draft_a, employee_a):
        resp = client_a.get(reverse("hrm:warningletter_list"), {"issued_to": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert warning_draft_a.pk in pks

    def test_list_search_by_number(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_list"), {"q": warning_draft_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert warning_draft_a.pk in pks

    def test_list_has_choices_context(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_list"))
        assert "level_choices" in resp.context
        assert "category_choices" in resp.context
        assert "status_choices" in resp.context
        assert "employees" in resp.context
        assert "is_admin" in resp.context


class TestWarningLetterCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:warningletter_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import WarningLetter
        resp = client_a.post(reverse("hrm:warningletter_create"), {
            "issued_to": employee_a.pk, "issued_by": employee_a2.pk, "level": "written",
            "category": "conduct", "incident_date": "2026-06-15",
            "description": "Repeated policy violation.", "policy_reference": "", "related_pip": "",
            "expiry_date": "",
        })
        assert resp.status_code == 302
        w = WarningLetter.objects.filter(tenant=tenant_a, issued_to=employee_a, level="written").first()
        assert w is not None
        assert w.tenant_id == tenant_a.pk
        assert w.number.startswith("WRN-")
        assert w.status == "draft"

    def test_post_invalid_issued_to_equal_issued_by_rejected(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import WarningLetter
        resp = client_a.post(reverse("hrm:warningletter_create"), {
            "issued_to": employee_a.pk, "issued_by": employee_a.pk, "level": "verbal",
            "category": "conduct", "incident_date": "2026-06-15", "description": "x",
            "policy_reference": "", "related_pip": "", "expiry_date": "",
        })
        assert resp.status_code == 200
        assert not WarningLetter.objects.filter(tenant=tenant_a, issued_to=employee_a, issued_by=employee_a).exists()

    def test_issued_to_and_issued_by_dropdowns_scoped_to_tenant(self, client_a, employee_a, employee_b):
        resp = client_a.get(reverse("hrm:warningletter_create"))
        to_pks = list(resp.context["form"].fields["issued_to"].queryset.values_list("pk", flat=True))
        by_pks = list(resp.context["form"].fields["issued_by"].queryset.values_list("pk", flat=True))
        assert employee_a.pk in to_pks
        assert employee_b.pk not in to_pks
        assert employee_a.pk in by_pks
        assert employee_b.pk not in by_pks

    def test_form_has_no_workflow_fields(self, client_a):
        resp = client_a.get(reverse("hrm:warningletter_create"))
        fields = resp.context["form"].fields
        for excluded in ("status", "number", "acknowledged_at", "acknowledged_by", "employee_response"):
            assert excluded not in fields


class TestWarningLetterDetailEditDelete:
    def test_detail_200(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_detail", args=[warning_draft_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_detail", args=[warning_draft_a.pk]))
        for key in ("obj", "prior_warnings", "can_edit", "is_admin", "is_recipient",
                    "can_acknowledge", "ack_form"):
            assert key in resp.context

    def test_edit_get_200(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_edit", args=[warning_draft_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_description(self, client_a, warning_draft_a, employee_a, employee_a2):
        resp = client_a.post(reverse("hrm:warningletter_edit", args=[warning_draft_a.pk]), {
            "issued_to": employee_a.pk, "issued_by": employee_a2.pk, "level": "verbal",
            "category": "attendance", "incident_date": "2026-06-01",
            "description": "Updated description.", "policy_reference": "", "related_pip": "",
            "expiry_date": "",
        })
        assert resp.status_code == 302
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.description == "Updated description."

    def test_edit_blocked_once_issued(self, client_a, warning_issued_a):
        resp = client_a.get(reverse("hrm:warningletter_edit", args=[warning_issued_a.pk]))
        assert resp.status_code == 302

    def test_delete_post_removes(self, client_a, warning_draft_a):
        from apps.hrm.models import WarningLetter
        pk = warning_draft_a.pk
        resp = client_a.post(reverse("hrm:warningletter_delete", args=[pk]))
        assert resp.status_code == 302
        assert not WarningLetter.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_delete", args=[warning_draft_a.pk]))
        assert resp.status_code == 405


class TestWarningLetterIssueAcknowledge:
    def test_issue_draft_to_issued(self, client_a, warning_draft_a):
        resp = client_a.post(reverse("hrm:warningletter_issue", args=[warning_draft_a.pk]))
        assert resp.status_code == 302
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.status == "issued"

    def test_issue_requires_admin(self, tenant_a, warning_draft_a, employee_a2):
        from django.test import Client
        from apps.accounts.models import User
        issuer_user = User.objects.create_user(
            email="carol_wrn@acme.com", username="carol_wrn_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        issuer_user.party = employee_a2.party
        issuer_user.save(update_fields=["party"])
        c = Client()
        c.force_login(issuer_user)
        resp = c.post(reverse("hrm:warningletter_issue", args=[warning_draft_a.pk]))
        assert resp.status_code == 403
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.status == "draft"

    def test_issue_blocked_when_not_draft(self, client_a, warning_issued_a):
        client_a.post(reverse("hrm:warningletter_issue", args=[warning_issued_a.pk]))
        warning_issued_a.refresh_from_db()
        assert warning_issued_a.status == "issued"  # unchanged

    def test_issue_get_not_allowed(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_issue", args=[warning_draft_a.pk]))
        assert resp.status_code == 405

    def test_acknowledge_post_with_response_by_recipient(self, tenant_a, warning_issued_a, employee_a):
        from django.test import Client
        from apps.accounts.models import User
        recipient_user = User.objects.create_user(
            email="alice_wrn@acme.com", username="alice_wrn_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        recipient_user.party = employee_a.party
        recipient_user.save(update_fields=["party"])
        c = Client()
        c.force_login(recipient_user)
        resp = c.post(reverse("hrm:warningletter_acknowledge", args=[warning_issued_a.pk]), {
            "employee_response": "I disagree, but understand the concern.",
        })
        assert resp.status_code == 302
        warning_issued_a.refresh_from_db()
        assert warning_issued_a.status == "acknowledged"
        assert warning_issued_a.employee_response == "I disagree, but understand the concern."
        assert warning_issued_a.acknowledged_at is not None
        assert warning_issued_a.acknowledged_by_id == employee_a.pk

    def test_acknowledge_forbidden_for_non_recipient(self, tenant_a, warning_issued_a, employee_a2):
        """The issuer (non-recipient, non-admin) may NOT acknowledge."""
        from django.test import Client
        from apps.accounts.models import User
        issuer_user = User.objects.create_user(
            email="carol_wrn2@acme.com", username="carol_wrn2_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        issuer_user.party = employee_a2.party
        issuer_user.save(update_fields=["party"])
        c = Client()
        c.force_login(issuer_user)
        resp = c.post(reverse("hrm:warningletter_acknowledge", args=[warning_issued_a.pk]), {
            "employee_response": "",
        })
        assert resp.status_code == 403
        warning_issued_a.refresh_from_db()
        assert warning_issued_a.status == "issued"

    def test_acknowledge_blocked_when_not_issued(self, client_a, warning_draft_a):
        client_a.post(reverse("hrm:warningletter_acknowledge", args=[warning_draft_a.pk]), {
            "employee_response": "",
        })
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.status == "draft"  # unchanged

    def test_acknowledge_get_not_allowed(self, client_a, warning_issued_a):
        resp = client_a.get(reverse("hrm:warningletter_acknowledge", args=[warning_issued_a.pk]))
        assert resp.status_code == 405


class TestWarningLetterPrint:
    def test_print_renders_200(self, client_a, warning_issued_a):
        resp = client_a.get(reverse("hrm:warningletter_print", args=[warning_issued_a.pk]))
        assert resp.status_code == 200

    def test_print_gated_by_can_view_warning(self, tenant_a, warning_issued_a, outsider_employee_a):
        from django.test import Client
        from apps.accounts.models import User
        outsider_user = User.objects.create_user(
            email="dana_wrn@acme.com", username="dana_wrn_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        outsider_user.party = outsider_employee_a.party
        outsider_user.save(update_fields=["party"])
        c = Client()
        c.force_login(outsider_user)
        resp = c.get(reverse("hrm:warningletter_print", args=[warning_issued_a.pk]))
        assert resp.status_code == 403


# ================================================================ CoachingNote CRUD
class TestCoachingNoteListView:
    def test_list_200(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_list"))
        assert resp.status_code == 200

    def test_list_shows_own_as_admin(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert coaching_note_a.pk in pks

    def test_list_filter_by_category(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_list"), {"category": "skill_development"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert coaching_note_a.pk in pks

    def test_list_filter_by_employee(self, client_a, coaching_note_a, employee_a):
        resp = client_a.get(reverse("hrm:coachingnote_list"), {"employee": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert coaching_note_a.pk in pks

    def test_list_search_by_number(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_list"), {"q": coaching_note_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert coaching_note_a.pk in pks

    def test_list_has_choices_context(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_list"))
        assert "category_choices" in resp.context
        assert "employees" in resp.context


class TestCoachingNoteCreateView:
    def test_get_200(self, client_a, admin_user, employee_a2):
        """coachingnote_create requires the logged-in user to have a linked EmployeeProfile (the
        coach) — link the admin to employee_a2 first."""
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        resp = client_a.get(reverse("hrm:coachingnote_create"))
        assert resp.status_code == 200

    def test_redirects_when_no_linked_profile(self, client_a):
        resp = client_a.get(reverse("hrm:coachingnote_create"))
        assert resp.status_code == 302

    def test_post_creates_with_tenant_and_server_set_coach(
        self, client_a, tenant_a, admin_user, employee_a2, employee_a
    ):
        from apps.hrm.models import CoachingNote
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        resp = client_a.post(reverse("hrm:coachingnote_create"), {
            "employee": employee_a.pk, "related_pip": "", "note_date": "2026-07-10",
            "category": "behavior", "content": "Discussed punctuality expectations.",
        })
        assert resp.status_code == 302
        note = CoachingNote.objects.filter(tenant=tenant_a, employee=employee_a, category="behavior").first()
        assert note is not None
        assert note.tenant_id == tenant_a.pk
        assert note.number.startswith("CN-")
        assert note.coach_id == employee_a2.pk  # server-set from the logged-in user's profile

    def test_post_coach_field_cannot_be_smuggled(self, client_a, tenant_a, admin_user, employee_a2, employee_a):
        """CoachingNoteForm has no `coach` field at all — even if a POST body includes one, the
        server always sets `coach` from the logged-in user's linked profile."""
        from apps.hrm.models import CoachingNote
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        resp = client_a.post(reverse("hrm:coachingnote_create"), {
            "employee": employee_a.pk, "related_pip": "", "note_date": "2026-07-10",
            "category": "other", "content": "x", "coach": employee_a.pk,
        })
        assert resp.status_code == 302
        note = CoachingNote.objects.filter(tenant=tenant_a, employee=employee_a, content="x").first()
        assert note.coach_id == employee_a2.pk  # NOT employee_a — smuggled value ignored

    def test_post_rejects_employee_equal_coach(self, client_a, tenant_a, admin_user, employee_a2):
        """The server sets coach=employee_a2 (the logged-in coach) then re-runs clean() — POSTing
        the coach themself as the coached `employee` must be rejected (employee != coach)."""
        from apps.hrm.models import CoachingNote
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        resp = client_a.post(reverse("hrm:coachingnote_create"), {
            "employee": employee_a2.pk, "related_pip": "", "note_date": "2026-07-10",
            "category": "other", "content": "Self coaching attempt",
        })
        assert resp.status_code == 200  # form re-rendered with a non-field error
        assert not CoachingNote.objects.filter(tenant=tenant_a, content="Self coaching attempt").exists()

    def test_employee_dropdown_scoped_to_tenant(self, client_a, admin_user, employee_a2, employee_a, employee_b):
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        resp = client_a.get(reverse("hrm:coachingnote_create"))
        pks = list(resp.context["form"].fields["employee"].queryset.values_list("pk", flat=True))
        assert employee_a.pk in pks
        assert employee_b.pk not in pks

    def test_form_has_no_coach_status_or_number_field(self, client_a, admin_user, employee_a2):
        admin_user.party = employee_a2.party
        admin_user.save(update_fields=["party"])
        resp = client_a.get(reverse("hrm:coachingnote_create"))
        fields = resp.context["form"].fields
        assert "coach" not in fields
        assert "status" not in fields
        assert "number" not in fields


class TestCoachingNoteDetailEditDelete:
    def test_detail_200_for_admin(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_detail", args=[coaching_note_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_obj(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_detail", args=[coaching_note_a.pk]))
        assert "obj" in resp.context

    def test_edit_get_200_for_admin(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_edit", args=[coaching_note_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_content(self, client_a, coaching_note_a, employee_a):
        resp = client_a.post(reverse("hrm:coachingnote_edit", args=[coaching_note_a.pk]), {
            "employee": employee_a.pk, "related_pip": "", "note_date": "2026-07-05",
            "category": "skill_development", "content": "Updated note content.",
        })
        assert resp.status_code == 302
        coaching_note_a.refresh_from_db()
        assert coaching_note_a.content == "Updated note content."

    def test_delete_post_removes_as_admin(self, client_a, coaching_note_a):
        from apps.hrm.models import CoachingNote
        pk = coaching_note_a.pk
        resp = client_a.post(reverse("hrm:coachingnote_delete", args=[pk]))
        assert resp.status_code == 302
        assert not CoachingNote.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_delete", args=[coaching_note_a.pk]))
        assert resp.status_code == 405


# ================================================================ Cross-tenant IDOR
class TestPIPIDOR:
    def test_detail_cross_tenant_404(self, client_a, pip_b):
        resp = client_a.get(reverse("hrm:pip_detail", args=[pip_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, pip_b):
        resp = client_a.get(reverse("hrm:pip_edit", args=[pip_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, pip_b):
        resp = client_a.post(reverse("hrm:pip_edit", args=[pip_b.pk]), {
            "subject": pip_b.subject_id, "manager": pip_b.manager_id, "triggering_review": "",
            "performance_issue": "hacked", "expected_standards": "x", "improvement_goals": "x",
            "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, pip_b):
        resp = client_a.post(reverse("hrm:pip_delete", args=[pip_b.pk]))
        assert resp.status_code == 404

    def test_submit_cross_tenant_404(self, client_a, pip_b):
        resp = client_a.post(reverse("hrm:pip_submit", args=[pip_b.pk]))
        assert resp.status_code == 404

    def test_hr_approve_cross_tenant_404(self, client_a, pip_b):
        resp = client_a.post(reverse("hrm:pip_hr_approve", args=[pip_b.pk]))
        assert resp.status_code == 404

    def test_acknowledge_cross_tenant_404(self, client_a, pip_b):
        resp = client_a.post(reverse("hrm:pip_acknowledge", args=[pip_b.pk]))
        assert resp.status_code == 404

    def test_close_cross_tenant_404(self, client_a, pip_b):
        resp = client_a.post(reverse("hrm:pip_close", args=[pip_b.pk]), {
            "outcome": "successful", "outcome_date": "", "outcome_notes": "",
        })
        assert resp.status_code == 404

    def test_extend_cross_tenant_404(self, client_a, pip_b):
        resp = client_a.post(reverse("hrm:pip_extend", args=[pip_b.pk]), {
            "extended_end_date": "2099-01-01",
        })
        assert resp.status_code == 404

    def test_list_excludes_b_pips(self, client_a, pip_draft_a, pip_b):
        resp = client_a.get(reverse("hrm:pip_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pip_draft_a.pk in pks
        assert pip_b.pk not in pks

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, pip_b):
        original_issue = pip_b.performance_issue
        client_a.post(reverse("hrm:pip_edit", args=[pip_b.pk]), {
            "subject": pip_b.subject_id, "manager": pip_b.manager_id, "triggering_review": "",
            "performance_issue": "hacked", "expected_standards": "x", "improvement_goals": "x",
            "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29",
        })
        pip_b.refresh_from_db()
        assert pip_b.performance_issue == original_issue


class TestPIPCheckInIDOR:
    def test_detail_cross_tenant_404(self, client_a, pipcheckin_b):
        resp = client_a.get(reverse("hrm:pipcheckin_detail", args=[pipcheckin_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, pipcheckin_b):
        resp = client_a.get(reverse("hrm:pipcheckin_edit", args=[pipcheckin_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, pipcheckin_b):
        resp = client_a.post(reverse("hrm:pipcheckin_edit", args=[pipcheckin_b.pk]), {
            "checkin_date": "2026-07-15", "progress_rating": "off_track", "progress_notes": "hacked",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, pipcheckin_b):
        resp = client_a.post(reverse("hrm:pipcheckin_delete", args=[pipcheckin_b.pk]))
        assert resp.status_code == 404

    def test_create_nested_cross_tenant_parent_404(self, client_a, pip_b):
        from apps.hrm.models import PIPCheckIn
        resp = client_a.post(reverse("hrm:pipcheckin_create", args=[pip_b.pk]), {
            "checkin_date": "2026-07-15", "progress_rating": "on_track", "progress_notes": "hacked",
        })
        assert resp.status_code == 404
        assert not PIPCheckIn.objects.filter(pip=pip_b, progress_notes="hacked").exists()


class TestWarningLetterIDOR:
    def test_detail_cross_tenant_404(self, client_a, warning_b):
        resp = client_a.get(reverse("hrm:warningletter_detail", args=[warning_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, warning_b):
        resp = client_a.get(reverse("hrm:warningletter_edit", args=[warning_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, warning_b):
        resp = client_a.post(reverse("hrm:warningletter_edit", args=[warning_b.pk]), {
            "issued_to": warning_b.issued_to_id, "issued_by": warning_b.issued_by_id, "level": "verbal",
            "category": "conduct", "incident_date": "2026-06-01", "description": "hacked",
            "policy_reference": "", "related_pip": "", "expiry_date": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, warning_b):
        resp = client_a.post(reverse("hrm:warningletter_delete", args=[warning_b.pk]))
        assert resp.status_code == 404

    def test_issue_cross_tenant_404(self, client_a, warning_b):
        resp = client_a.post(reverse("hrm:warningletter_issue", args=[warning_b.pk]))
        assert resp.status_code == 404

    def test_acknowledge_cross_tenant_404(self, client_a, warning_b):
        resp = client_a.post(reverse("hrm:warningletter_acknowledge", args=[warning_b.pk]), {
            "employee_response": "hacked",
        })
        assert resp.status_code == 404

    def test_print_cross_tenant_404(self, client_a, warning_b):
        resp = client_a.get(reverse("hrm:warningletter_print", args=[warning_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_warnings(self, client_a, warning_draft_a, warning_b):
        resp = client_a.get(reverse("hrm:warningletter_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert warning_draft_a.pk in pks
        assert warning_b.pk not in pks


class TestCoachingNoteIDOR:
    def test_detail_cross_tenant_404(self, client_a, coaching_note_b):
        resp = client_a.get(reverse("hrm:coachingnote_detail", args=[coaching_note_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, coaching_note_b):
        resp = client_a.get(reverse("hrm:coachingnote_edit", args=[coaching_note_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, coaching_note_b):
        resp = client_a.post(reverse("hrm:coachingnote_edit", args=[coaching_note_b.pk]), {
            "employee": coaching_note_b.employee_id, "related_pip": "", "note_date": "2026-07-05",
            "category": "other", "content": "hacked",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, coaching_note_b):
        resp = client_a.post(reverse("hrm:coachingnote_delete", args=[coaching_note_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_notes(self, client_a, coaching_note_a, coaching_note_b):
        resp = client_a.get(reverse("hrm:coachingnote_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert coaching_note_a.pk in pks
        assert coaching_note_b.pk not in pks


# ================================================================ Anonymous user -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:pip_list", []),
        ("hrm:warningletter_list", []),
        ("hrm:coachingnote_list", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_pages(
        self, client, pip_draft_a, pipcheckin_a, warning_draft_a, coaching_note_a
    ):
        for url_name, pk in [
            ("hrm:pip_detail", pip_draft_a.pk),
            ("hrm:pipcheckin_detail", pipcheckin_a.pk),
            ("hrm:warningletter_detail", warning_draft_a.pk),
            ("hrm:coachingnote_detail", coaching_note_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_actions(
        self, client, pip_draft_a, pip_active_a, warning_draft_a, coaching_note_a
    ):
        for url_name, pk in [
            ("hrm:pip_delete", pip_draft_a.pk),
            ("hrm:pip_submit", pip_draft_a.pk),
            ("hrm:pip_hr_approve", pip_draft_a.pk),
            ("hrm:pip_acknowledge", pip_active_a.pk),
            ("hrm:pip_extend", pip_active_a.pk),
            ("hrm:warningletter_delete", warning_draft_a.pk),
            ("hrm:warningletter_issue", warning_draft_a.pk),
            ("hrm:coachingnote_delete", coaching_note_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]
