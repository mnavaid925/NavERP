"""Tests for CRM sub-module 1.8 — Project & Delivery Management.

Covers:
  - ResourceAllocation auto-number (RA-) + overlap_hours proration
  - CrmProject.progress_pct / is_overdue
  - resource_workload view: planned vs logged, rejected timesheets excluded, overbooked flag
  - ResourceAllocationForm clean validation + tenant-scoped FK querysets
  - TimesheetForm: status field absent (self-approve guard)
  - Timesheet workflow: submit (owner / non-owner guard) + approve / reject
    (@tenant_admin_required boundary)
  - timesheet_edit / timesheet_delete blocked on approved records
  - crmmilestone_move: valid/invalid status; completed_at stamped/cleared; cross-tenant IDOR
  - CRUD integration: all list/detail/create/edit pages return 200; create persists
  - Multi-tenant IDOR: ResourceAllocation detail/edit/delete by foreign tenant → 404
  - Query-count: resource_workload bounded (no N+1)
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ======================================================================== helpers

def _make_project(tenant, name="Alpha Project", status="active", end_date=None):
    from apps.crm.models import CrmProject
    return CrmProject.objects.create(
        tenant=tenant,
        name=name,
        status=status,
        end_date=end_date,
    )


def _make_milestone(tenant, project, title="MS-1", status="not_started"):
    from apps.crm.models import CrmMilestone
    return CrmMilestone.objects.create(
        tenant=tenant,
        project=project,
        title=title,
        status=status,
    )


def _make_timesheet(tenant, project, employee, date=None, hours=Decimal("8"), status="draft"):
    from apps.crm.models import Timesheet
    if date is None:
        date = timezone.localdate()
    return Timesheet.objects.create(
        tenant=tenant,
        project=project,
        employee=employee,
        date=date,
        hours=hours,
        status=status,
    )


def _make_allocation(tenant, project, assignee, start_date=None, end_date=None,
                     hours_per_week=Decimal("40"), status="active"):
    from apps.crm.models import ResourceAllocation
    if start_date is None:
        start_date = timezone.localdate()
    return ResourceAllocation.objects.create(
        tenant=tenant,
        project=project,
        assignee=assignee,
        start_date=start_date,
        end_date=end_date,
        hours_per_week=hours_per_week,
        status=status,
    )


# ======================================================================== Group 1 — Models

class TestResourceAllocationAutoNumber:
    def test_number_prefix(self, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        alloc = _make_allocation(tenant_a, proj, admin_user)
        assert alloc.number.startswith("RA-")

    def test_first_number_is_00001(self, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        alloc = _make_allocation(tenant_a, proj, admin_user)
        assert alloc.number == "RA-00001"

    def test_per_tenant_numbering(self, tenant_a, tenant_b, admin_user, admin_b):
        proj_a = _make_project(tenant_a)
        proj_b = _make_project(tenant_b)
        a = _make_allocation(tenant_a, proj_a, admin_user)
        b = _make_allocation(tenant_b, proj_b, admin_b)
        assert a.number == "RA-00001"
        assert b.number == "RA-00001"

    def test_sequential_within_tenant(self, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        a1 = _make_allocation(tenant_a, proj, admin_user,
                              start_date=timezone.localdate() + datetime.timedelta(days=0))
        a2 = _make_allocation(tenant_a, proj, admin_user,
                              start_date=timezone.localdate() + datetime.timedelta(days=7))
        assert a1.number == "RA-00001"
        assert a2.number == "RA-00002"

    def test_str_contains_number(self, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        alloc = _make_allocation(tenant_a, proj, admin_user)
        assert "RA-00001" in str(alloc)

    def test_unique_together_tenant_number(self, tenant_a, admin_user):
        from apps.crm.models import ResourceAllocation
        from django.db import IntegrityError
        proj = _make_project(tenant_a)
        _make_allocation(tenant_a, proj, admin_user)
        with pytest.raises(IntegrityError):
            ResourceAllocation.objects.create(
                tenant=tenant_a,
                project=proj,
                assignee=admin_user,
                start_date=timezone.localdate(),
                number="RA-00001",
            )


class TestOverlapHours:
    """ResourceAllocation.overlap_hours(win_start, win_end) proration."""

    def _alloc(self, tenant, admin_user, start, end=None, hours_per_week=Decimal("40"), status="active"):
        proj = _make_project(tenant)
        from apps.crm.models import ResourceAllocation
        return ResourceAllocation.objects.create(
            tenant=tenant,
            project=proj,
            assignee=admin_user,
            start_date=start,
            end_date=end,
            hours_per_week=hours_per_week,
            status=status,
        )

    def test_full_overlap_exactly_7_days_is_one_week(self, tenant_a, admin_user):
        """40 h/wk over exactly 7 days (6 day span + day 0 = 7 days) → 40.00."""
        base = datetime.date(2025, 1, 6)   # Monday
        end = datetime.date(2025, 1, 12)   # Sunday
        alloc = self._alloc(tenant_a, admin_user, start=base, end=end, hours_per_week=Decimal("40"))
        result = alloc.overlap_hours(base, end)
        assert result == Decimal("40.00")

    def test_partial_overlap_half_week(self, tenant_a, admin_user):
        """40 h/wk; allocation covers 3.5 days of a 7-day window → 20 h."""
        base = datetime.date(2025, 1, 6)
        win_end = datetime.date(2025, 1, 12)
        alloc = self._alloc(tenant_a, admin_user, start=base, end=datetime.date(2025, 1, 9),
                            hours_per_week=Decimal("40"))
        # overlapping days: Jan 6–9 = 4 days
        result = alloc.overlap_hours(base, win_end)
        # 40 * 4 / 7 = 22.86
        expected = (Decimal("40") * Decimal(4) / Decimal(7)).quantize(Decimal("0.01"))
        assert result == expected

    def test_null_end_date_is_ongoing_clamped_to_window_end(self, tenant_a, admin_user):
        """Null end_date → ongoing; prorated against the window end."""
        base = datetime.date(2025, 1, 6)
        win_end = datetime.date(2025, 1, 12)
        alloc = self._alloc(tenant_a, admin_user, start=base, end=None, hours_per_week=Decimal("40"))
        result = alloc.overlap_hours(base, win_end)
        # Null treated as win_end → full 7 days
        assert result == Decimal("40.00")

    def test_cancelled_returns_zero(self, tenant_a, admin_user):
        base = datetime.date(2025, 1, 6)
        win_end = datetime.date(2025, 1, 12)
        alloc = self._alloc(tenant_a, admin_user, start=base, end=win_end,
                            hours_per_week=Decimal("40"), status="cancelled")
        assert alloc.overlap_hours(base, win_end) == Decimal("0")

    def test_no_overlap_start_after_window(self, tenant_a, admin_user):
        """Allocation starts after the window end → 0."""
        base = datetime.date(2025, 1, 6)
        win_end = datetime.date(2025, 1, 12)
        alloc = self._alloc(tenant_a, admin_user, start=datetime.date(2025, 1, 20), end=None,
                            hours_per_week=Decimal("40"))
        assert alloc.overlap_hours(base, win_end) == Decimal("0")

    def test_no_overlap_end_before_window(self, tenant_a, admin_user):
        """Allocation ends before the window start → 0."""
        base = datetime.date(2025, 1, 13)
        win_end = datetime.date(2025, 1, 19)
        alloc = self._alloc(tenant_a, admin_user, start=datetime.date(2025, 1, 1),
                            end=datetime.date(2025, 1, 5), hours_per_week=Decimal("40"))
        assert alloc.overlap_hours(base, win_end) == Decimal("0")

    def test_zero_hours_per_week_returns_zero(self, tenant_a, admin_user):
        base = datetime.date(2025, 1, 6)
        win_end = datetime.date(2025, 1, 12)
        alloc = self._alloc(tenant_a, admin_user, start=base, end=win_end, hours_per_week=Decimal("0"))
        assert alloc.overlap_hours(base, win_end) == Decimal("0")


class TestCrmProjectProgressPct:
    def test_no_milestones_returns_zero(self, tenant_a):
        proj = _make_project(tenant_a)
        assert proj.progress_pct == 0

    def test_one_of_two_completed_is_50(self, tenant_a):
        proj = _make_project(tenant_a)
        _make_milestone(tenant_a, proj, "MS-1", status="completed")
        _make_milestone(tenant_a, proj, "MS-2", status="not_started")
        assert proj.progress_pct == 50

    def test_all_completed_is_100(self, tenant_a):
        proj = _make_project(tenant_a)
        _make_milestone(tenant_a, proj, "MS-1", status="completed")
        _make_milestone(tenant_a, proj, "MS-2", status="completed")
        assert proj.progress_pct == 100

    def test_no_completed_returns_zero(self, tenant_a):
        proj = _make_project(tenant_a)
        _make_milestone(tenant_a, proj, "MS-1", status="in_progress")
        assert proj.progress_pct == 0

    def test_uses_ms_total_annotation_when_present(self, tenant_a):
        """Simulates the list-view annotation path (ms_total/ms_done attributes pre-set)."""
        proj = _make_project(tenant_a)
        proj.ms_total = 4
        proj.ms_done = 3
        assert proj.progress_pct == 75


class TestCrmProjectIsOverdue:
    def test_overdue_active_project(self, tenant_a):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        proj = _make_project(tenant_a, status="active", end_date=yesterday)
        assert proj.is_overdue is True

    def test_not_overdue_future_end_date(self, tenant_a):
        future = timezone.localdate() + datetime.timedelta(days=10)
        proj = _make_project(tenant_a, status="active", end_date=future)
        assert proj.is_overdue is False

    def test_completed_project_not_overdue_even_past_date(self, tenant_a):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        proj = _make_project(tenant_a, status="completed", end_date=yesterday)
        assert proj.is_overdue is False

    def test_cancelled_project_not_overdue(self, tenant_a):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        proj = _make_project(tenant_a, status="cancelled", end_date=yesterday)
        assert proj.is_overdue is False

    def test_no_end_date_never_overdue(self, tenant_a):
        proj = _make_project(tenant_a, status="active", end_date=None)
        assert proj.is_overdue is False


class TestCrmMilestoneCompletedAt:
    def test_completed_at_stamped_on_completion(self, tenant_a):
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj, status="not_started")
        ms.status = "completed"
        ms.save()
        ms.refresh_from_db()
        assert ms.completed_at is not None

    def test_completed_at_cleared_on_reopen(self, tenant_a):
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj, status="completed")
        ms.status = "in_progress"
        ms.save()
        ms.refresh_from_db()
        assert ms.completed_at is None


# ======================================================================== Group 2 — resource_workload

class TestResourceWorkloadView:
    def test_returns_200_as_admin(self, client_a):
        resp = client_a.get(reverse("crm:resource_workload"))
        assert resp.status_code == 200

    def test_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:resource_workload"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_overbooked_person_flagged(self, tenant_a, admin_user):
        """A person with planned > capacity shows overbooked=True in context rows."""
        today = timezone.localdate()
        # Start a window: Monday of this week to Sunday+21 days (4 weeks)
        monday = today - datetime.timedelta(days=today.weekday())
        win_end = monday + datetime.timedelta(days=27)

        proj = _make_project(tenant_a)
        # 200 h/wk for the full 4-week window → way over 40 h/wk capacity
        _make_allocation(tenant_a, proj, admin_user, start_date=monday, end_date=win_end,
                         hours_per_week=Decimal("200"))

        c = Client()
        c.force_login(admin_user)
        resp = c.get(reverse("crm:resource_workload"))
        assert resp.status_code == 200
        rows = resp.context["rows"]
        user_row = next((r for r in rows if r["user"] and r["user"].pk == admin_user.pk), None)
        assert user_row is not None
        assert user_row["overbooked"] is True

    def test_rejected_timesheet_excluded_from_logged(self, tenant_a, admin_user):
        """A REJECTED timesheet's hours must NOT appear in a person's logged total."""
        today = timezone.localdate()
        monday = today - datetime.timedelta(days=today.weekday())
        win_end = monday + datetime.timedelta(days=27)

        proj = _make_project(tenant_a)
        # Give the user an allocation so they appear in the row set
        _make_allocation(tenant_a, proj, admin_user, start_date=monday, end_date=win_end,
                         hours_per_week=Decimal("10"))

        # Log 5 h approved + 3 h rejected
        _make_timesheet(tenant_a, proj, admin_user, date=monday, hours=Decimal("5"), status="approved")
        _make_timesheet(tenant_a, proj, admin_user, date=monday, hours=Decimal("3"), status="rejected")

        c = Client()
        c.force_login(admin_user)
        resp = c.get(reverse("crm:resource_workload"))
        rows = resp.context["rows"]
        user_row = next((r for r in rows if r["user"] and r["user"].pk == admin_user.pk), None)
        assert user_row is not None
        # Only the 5 approved hours should count, NOT the 3 rejected
        assert user_row["logged"] == Decimal("5")

    def test_timesheet_only_user_appears_in_rows(self, tenant_a, member_user):
        """A user with timesheets but NO allocation should still appear in rows."""
        today = timezone.localdate()
        monday = today - datetime.timedelta(days=today.weekday())

        proj = _make_project(tenant_a)
        _make_timesheet(tenant_a, proj, member_user, date=monday, hours=Decimal("6"), status="submitted")

        # Login as admin (tenant_a) to see the workload board
        c = Client()
        c.force_login(member_user)
        resp = c.get(reverse("crm:resource_workload"))
        rows = resp.context["rows"]
        user_row = next((r for r in rows if r["user"] and r["user"].pk == member_user.pk), None)
        assert user_row is not None
        assert user_row["logged"] == Decimal("6")


# ======================================================================== Group 3 — Forms

class TestResourceAllocationFormValidation:
    def test_end_before_start_raises_error(self, tenant_a):
        from apps.crm.forms import ResourceAllocationForm
        proj = _make_project(tenant_a)
        data = {
            "project": proj.pk,
            "assignee": "",
            "role": "Developer",
            "hours_per_week": "40",
            "start_date": "2025-01-20",
            "end_date": "2025-01-10",   # before start
            "status": "active",
            "notes": "",
        }
        form = ResourceAllocationForm(data, tenant=tenant_a)
        assert not form.is_valid()
        # clean() raises ValidationError — check __all__ errors
        assert form.non_field_errors()

    def test_end_equal_start_is_valid(self, tenant_a):
        from apps.crm.forms import ResourceAllocationForm
        proj = _make_project(tenant_a)
        data = {
            "project": proj.pk,
            "assignee": "",
            "role": "Designer",
            "hours_per_week": "20",
            "start_date": "2025-01-10",
            "end_date": "2025-01-10",
            "status": "active",
            "notes": "",
        }
        form = ResourceAllocationForm(data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_assignee_queryset_excludes_foreign_tenant_user(self, tenant_a, tenant_b, admin_b):
        """The assignee dropdown must NOT include tenant_b's users."""
        from apps.crm.forms import ResourceAllocationForm
        form = ResourceAllocationForm(tenant=tenant_a)
        qs = form.fields["assignee"].queryset
        assert admin_b not in qs

    def test_project_queryset_excludes_foreign_tenant_project(self, tenant_a, tenant_b):
        """The project dropdown must NOT include tenant_b's projects."""
        from apps.crm.forms import ResourceAllocationForm
        proj_b = _make_project(tenant_b, name="B Corp Project")
        form = ResourceAllocationForm(tenant=tenant_a)
        qs = form.fields["project"].queryset
        assert proj_b not in qs

    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.crm.forms import ResourceAllocationForm
        form = ResourceAllocationForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_a_form_field(self, tenant_a):
        from apps.crm.forms import ResourceAllocationForm
        form = ResourceAllocationForm(tenant=tenant_a)
        assert "number" not in form.fields


class TestTimesheetFormNoStatusField:
    def test_status_not_in_fields(self, tenant_a):
        """status must be absent — accepting it from POST would let a user self-approve."""
        from apps.crm.forms import TimesheetForm
        form = TimesheetForm(tenant=tenant_a)
        assert "status" not in form.fields

    def test_approved_by_not_in_fields(self, tenant_a):
        from apps.crm.forms import TimesheetForm
        form = TimesheetForm(tenant=tenant_a)
        assert "approved_by" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import TimesheetForm
        form = TimesheetForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_in_fields(self, tenant_a):
        from apps.crm.forms import TimesheetForm
        form = TimesheetForm(tenant=tenant_a)
        assert "number" not in form.fields


# ======================================================================== Group 4 — Timesheet workflow + security

class TestTimesheetSubmit:
    def test_owner_can_submit_draft(self, tenant_a, admin_user, client_a):
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="draft")
        url = reverse("crm:timesheet_submit", args=[ts.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        ts.refresh_from_db()
        assert ts.status == "submitted"

    def test_non_owner_non_admin_cannot_submit(self, tenant_a, admin_user, member_user):
        """Member who is NOT the timesheet owner must be blocked."""
        proj = _make_project(tenant_a)
        # Timesheet belongs to admin_user
        ts = _make_timesheet(tenant_a, proj, admin_user, status="draft")
        # Login as member_user (not owner, not admin)
        c = Client()
        c.force_login(member_user)
        url = reverse("crm:timesheet_submit", args=[ts.pk])
        c.post(url)
        ts.refresh_from_db()
        # Status must remain draft
        assert ts.status == "draft"

    def test_admin_can_submit_others_timesheet(self, tenant_a, admin_user, member_user):
        """A tenant admin can submit any timesheet."""
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, member_user, status="draft")
        c = Client()
        c.force_login(admin_user)
        c.post(reverse("crm:timesheet_submit", args=[ts.pk]))
        ts.refresh_from_db()
        assert ts.status == "submitted"

    def test_submit_already_submitted_is_idempotent(self, tenant_a, admin_user, client_a):
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="submitted")
        client_a.post(reverse("crm:timesheet_submit", args=[ts.pk]))
        ts.refresh_from_db()
        # Should not regress or blow up — stays submitted
        assert ts.status == "submitted"


class TestTimesheetApproveReject:
    def test_non_admin_approve_blocked(self, tenant_a, admin_user, member_user):
        """A non-admin member POSTing approve must get PermissionDenied (403)."""
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="submitted")
        c = Client()
        c.force_login(member_user)
        url = reverse("crm:timesheet_approve", args=[ts.pk])
        resp = c.post(url)
        # @tenant_admin_required raises PermissionDenied → Django returns 403
        assert resp.status_code == 403
        ts.refresh_from_db()
        assert ts.status == "submitted"

    def test_admin_can_approve(self, tenant_a, admin_user, client_a):
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="submitted")
        resp = client_a.post(reverse("crm:timesheet_approve", args=[ts.pk]))
        assert resp.status_code == 302
        ts.refresh_from_db()
        assert ts.status == "approved"
        assert ts.approved_by_id == admin_user.pk

    def test_non_admin_reject_blocked(self, tenant_a, admin_user, member_user):
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="submitted")
        c = Client()
        c.force_login(member_user)
        resp = c.post(reverse("crm:timesheet_reject", args=[ts.pk]))
        assert resp.status_code == 403
        ts.refresh_from_db()
        assert ts.status == "submitted"

    def test_admin_can_reject(self, tenant_a, admin_user, client_a):
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="submitted")
        resp = client_a.post(reverse("crm:timesheet_reject", args=[ts.pk]))
        assert resp.status_code == 302
        ts.refresh_from_db()
        assert ts.status == "rejected"


class TestTimesheetEditDelete:
    def test_edit_blocked_on_approved_timesheet(self, tenant_a, admin_user, client_a):
        """Editing an approved timesheet must be blocked (redirects away)."""
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="approved")
        url = reverse("crm:timesheet_edit", args=[ts.pk])
        resp = client_a.get(url)
        # View redirects when status not in (draft, rejected)
        assert resp.status_code == 302

    def test_edit_allowed_on_draft(self, tenant_a, admin_user, client_a):
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="draft")
        resp = client_a.get(reverse("crm:timesheet_edit", args=[ts.pk]))
        assert resp.status_code == 200

    def test_edit_allowed_on_rejected(self, tenant_a, admin_user, client_a):
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="rejected")
        resp = client_a.get(reverse("crm:timesheet_edit", args=[ts.pk]))
        assert resp.status_code == 200

    def test_self_approve_via_post_edit_ignored(self, tenant_a, admin_user, client_a):
        """POSTing status=approved via the edit form must NOT change status (form excludes status)."""
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="draft")
        today = timezone.localdate()
        # Post with injected status=approved — the form must ignore it
        client_a.post(reverse("crm:timesheet_edit", args=[ts.pk]), {
            "project": proj.pk,
            "milestone": "",
            "employee": admin_user.pk,
            "client": "",
            "date": today.strftime("%Y-%m-%d"),
            "hours": "6",
            "description": "Hacking the form",
            "is_billable": "on",
            "status": "approved",  # must be ignored
        })
        ts.refresh_from_db()
        assert ts.status == "draft"  # should remain draft

    def test_delete_blocked_on_approved_timesheet(self, tenant_a, admin_user, client_a):
        """Deleting an approved timesheet must be blocked (record still exists)."""
        from apps.crm.models import Timesheet
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="approved")
        pk = ts.pk
        client_a.post(reverse("crm:timesheet_delete", args=[pk]))
        assert Timesheet.objects.filter(pk=pk).exists()

    def test_delete_succeeds_on_draft_timesheet(self, tenant_a, admin_user, client_a):
        from apps.crm.models import Timesheet
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="draft")
        pk = ts.pk
        resp = client_a.post(reverse("crm:timesheet_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Timesheet.objects.filter(pk=pk).exists()

    def test_delete_succeeds_on_rejected_timesheet(self, tenant_a, admin_user, client_a):
        from apps.crm.models import Timesheet
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="rejected")
        pk = ts.pk
        client_a.post(reverse("crm:timesheet_delete", args=[pk]))
        assert not Timesheet.objects.filter(pk=pk).exists()

    def test_delete_approved_leaves_record_unchanged(self, tenant_a, admin_user, client_a):
        from apps.crm.models import Timesheet
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="approved")
        pk = ts.pk
        client_a.post(reverse("crm:timesheet_delete", args=[pk]))
        ts.refresh_from_db()
        assert ts.status == "approved"  # untouched


# ======================================================================== Group 5 — crmmilestone_move

class TestCrmMilestoneMove:
    def test_valid_status_moves_milestone(self, tenant_a, admin_user, client_a):
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj, status="not_started")
        url = reverse("crm:crmmilestone_move", args=[ms.pk])
        client_a.post(url, {"status": "in_progress"})
        ms.refresh_from_db()
        assert ms.status == "in_progress"

    def test_invalid_status_is_ignored(self, tenant_a, admin_user, client_a):
        """An unrecognised status must not mutate the milestone."""
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj, status="not_started")
        url = reverse("crm:crmmilestone_move", args=[ms.pk])
        client_a.post(url, {"status": "bogus_status"})
        ms.refresh_from_db()
        assert ms.status == "not_started"

    def test_completed_sets_completed_at(self, tenant_a, admin_user, client_a):
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj, status="in_progress")
        url = reverse("crm:crmmilestone_move", args=[ms.pk])
        client_a.post(url, {"status": "completed"})
        ms.refresh_from_db()
        assert ms.status == "completed"
        assert ms.completed_at is not None

    def test_reopen_clears_completed_at(self, tenant_a, admin_user, client_a):
        """Moving from completed to in_progress must clear completed_at."""
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj, status="completed")
        url = reverse("crm:crmmilestone_move", args=[ms.pk])
        client_a.post(url, {"status": "in_progress"})
        ms.refresh_from_db()
        assert ms.completed_at is None

    def test_cross_tenant_move_returns_404(self, tenant_b, admin_b, client_a):
        """Tenant A's client posting to tenant B's milestone → 404."""
        proj_b = _make_project(tenant_b)
        ms_b = _make_milestone(tenant_b, proj_b, status="not_started")
        url = reverse("crm:crmmilestone_move", args=[ms_b.pk])
        resp = client_a.post(url, {"status": "in_progress"})
        assert resp.status_code == 404

    def test_same_status_post_is_no_op(self, tenant_a, admin_user, client_a):
        """Posting the existing status must not error and must leave status unchanged."""
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj, status="in_progress")
        client_a.post(reverse("crm:crmmilestone_move", args=[ms.pk]), {"status": "in_progress"})
        ms.refresh_from_db()
        assert ms.status == "in_progress"

    def test_anon_redirects_to_login(self, tenant_a):
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj, status="not_started")
        c = Client()
        resp = c.post(reverse("crm:crmmilestone_move", args=[ms.pk]), {"status": "in_progress"})
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ======================================================================== Group 6 — CRUD integration

class TestCrmProjectCRUD:
    def test_list_200(self, client_a, tenant_a):
        _make_project(tenant_a)
        resp = client_a.get(reverse("crm:crmproject_list"))
        assert resp.status_code == 200

    def test_list_tenant_isolation(self, client_a, tenant_a, tenant_b):
        proj_b = _make_project(tenant_b, name="B Project")
        resp = client_a.get(reverse("crm:crmproject_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert proj_b.pk not in pks

    def test_detail_200(self, client_a, tenant_a):
        proj = _make_project(tenant_a)
        resp = client_a.get(reverse("crm:crmproject_detail", args=[proj.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:crmproject_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import CrmProject
        resp = client_a.post(reverse("crm:crmproject_create"), {
            "name": "New Test Project",
            "status": "planning",
            "budget": "0",
            "description": "",
        })
        assert resp.status_code == 302
        obj = CrmProject.objects.filter(tenant=tenant_a, name="New Test Project").first()
        assert obj is not None
        assert obj.tenant_id == tenant_a.pk

    def test_create_assigns_auto_number(self, client_a, tenant_a):
        from apps.crm.models import CrmProject
        client_a.post(reverse("crm:crmproject_create"), {
            "name": "Auto-num Project",
            "status": "planning",
            "budget": "0",
        })
        obj = CrmProject.objects.filter(tenant=tenant_a, name="Auto-num Project").first()
        assert obj is not None
        assert obj.number.startswith("PRJ-")

    def test_edit_get_200(self, client_a, tenant_a):
        proj = _make_project(tenant_a)
        resp = client_a.get(reverse("crm:crmproject_edit", args=[proj.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, tenant_a):
        proj = _make_project(tenant_a)
        client_a.post(reverse("crm:crmproject_edit", args=[proj.pk]), {
            "name": "Updated Name",
            "status": "active",
            "budget": "0",
        })
        proj.refresh_from_db()
        assert proj.name == "Updated Name"

    def test_delete_post_removes(self, client_a, tenant_a):
        from apps.crm.models import CrmProject
        proj = _make_project(tenant_a)
        pk = proj.pk
        client_a.post(reverse("crm:crmproject_delete", args=[pk]))
        assert not CrmProject.objects.filter(pk=pk).exists()

    def test_anon_redirects_to_login(self):
        c = Client()
        resp = c.get(reverse("crm:crmproject_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestResourceAllocationCRUD:
    def test_list_200(self, client_a, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        _make_allocation(tenant_a, proj, admin_user)
        resp = client_a.get(reverse("crm:resourceallocation_list"))
        assert resp.status_code == 200

    def test_detail_200(self, client_a, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        alloc = _make_allocation(tenant_a, proj, admin_user)
        resp = client_a.get(reverse("crm:resourceallocation_detail", args=[alloc.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:resourceallocation_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant_and_number(self, client_a, tenant_a, admin_user):
        from apps.crm.models import ResourceAllocation
        proj = _make_project(tenant_a)
        today = timezone.localdate()
        resp = client_a.post(reverse("crm:resourceallocation_create"), {
            "project": proj.pk,
            "assignee": admin_user.pk,
            "role": "Developer",
            "hours_per_week": "40",
            "start_date": today.strftime("%Y-%m-%d"),
            "end_date": "",
            "status": "active",
            "notes": "",
        })
        assert resp.status_code == 302
        obj = ResourceAllocation.objects.filter(tenant=tenant_a).first()
        assert obj is not None
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("RA-")

    def test_edit_get_200(self, client_a, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        alloc = _make_allocation(tenant_a, proj, admin_user)
        resp = client_a.get(reverse("crm:resourceallocation_edit", args=[alloc.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_role(self, client_a, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        alloc = _make_allocation(tenant_a, proj, admin_user)
        today = timezone.localdate()
        client_a.post(reverse("crm:resourceallocation_edit", args=[alloc.pk]), {
            "project": proj.pk,
            "assignee": admin_user.pk,
            "role": "QA Lead",
            "hours_per_week": "20",
            "start_date": today.strftime("%Y-%m-%d"),
            "end_date": "",
            "status": "active",
            "notes": "",
        })
        alloc.refresh_from_db()
        assert alloc.role == "QA Lead"

    def test_delete_post_removes(self, client_a, tenant_a, admin_user):
        from apps.crm.models import ResourceAllocation
        proj = _make_project(tenant_a)
        alloc = _make_allocation(tenant_a, proj, admin_user)
        pk = alloc.pk
        client_a.post(reverse("crm:resourceallocation_delete", args=[pk]))
        assert not ResourceAllocation.objects.filter(pk=pk).exists()

    def test_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:resourceallocation_list"))
        assert resp.status_code == 302

    def test_status_choices_in_context(self, client_a, tenant_a, admin_user):
        from apps.crm.models import ResourceAllocation
        _make_allocation(tenant_a, _make_project(tenant_a), admin_user)
        resp = client_a.get(reverse("crm:resourceallocation_list"))
        assert "status_choices" in resp.context


class TestTimesheetCRUD:
    def test_list_200(self, client_a, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        _make_timesheet(tenant_a, proj, admin_user)
        resp = client_a.get(reverse("crm:timesheet_list"))
        assert resp.status_code == 200

    def test_detail_200(self, client_a, tenant_a, admin_user):
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user)
        resp = client_a.get(reverse("crm:timesheet_detail", args=[ts.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:timesheet_create"))
        assert resp.status_code == 200

    def test_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:timesheet_list"))
        assert resp.status_code == 302

    def test_list_tenant_isolation(self, client_a, tenant_a, tenant_b, admin_user, admin_b):
        proj_a = _make_project(tenant_a)
        proj_b = _make_project(tenant_b)
        ts_b = _make_timesheet(tenant_b, proj_b, admin_b)
        _make_timesheet(tenant_a, proj_a, admin_user)
        resp = client_a.get(reverse("crm:timesheet_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert ts_b.pk not in pks


class TestCrmMilestoneCRUD:
    def test_list_200(self, client_a, tenant_a):
        proj = _make_project(tenant_a)
        _make_milestone(tenant_a, proj)
        resp = client_a.get(reverse("crm:crmmilestone_list"))
        assert resp.status_code == 200

    def test_detail_200(self, client_a, tenant_a):
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj)
        resp = client_a.get(reverse("crm:crmmilestone_detail", args=[ms.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:crmmilestone_create"))
        assert resp.status_code == 200

    def test_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:crmmilestone_list"))
        assert resp.status_code == 302


class TestCrmProjectBoardView:
    def test_board_200(self, client_a, tenant_a):
        _make_project(tenant_a)
        resp = client_a.get(reverse("crm:crmproject_board"))
        assert resp.status_code == 200

    def test_board_has_columns_context(self, client_a, tenant_a):
        resp = client_a.get(reverse("crm:crmproject_board"))
        assert "columns" in resp.context

    def test_board_filter_by_project(self, client_a, tenant_a):
        proj = _make_project(tenant_a)
        _make_milestone(tenant_a, proj, status="in_progress")
        resp = client_a.get(reverse("crm:crmproject_board"), {"project": str(proj.pk)})
        assert resp.status_code == 200

    def test_board_only_shows_own_tenant_milestones(self, client_a, tenant_a, tenant_b):
        proj_b = _make_project(tenant_b)
        ms_b = _make_milestone(tenant_b, proj_b, title="Secret B")
        resp = client_a.get(reverse("crm:crmproject_board"))
        all_cards = []
        for col in resp.context["columns"]:
            all_cards.extend(col["cards"])
        ms_pks = [m.pk for m in all_cards]
        assert ms_b.pk not in ms_pks

    def test_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:crmproject_board"))
        assert resp.status_code == 302


# ======================================================================== Group 7 — Multi-tenant IDOR

class TestResourceAllocationIDOR:
    def test_detail_cross_tenant_404(self, client_a, tenant_b, admin_b):
        proj_b = _make_project(tenant_b)
        alloc_b = _make_allocation(tenant_b, proj_b, admin_b)
        resp = client_a.get(reverse("crm:resourceallocation_detail", args=[alloc_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, tenant_b, admin_b):
        proj_b = _make_project(tenant_b)
        alloc_b = _make_allocation(tenant_b, proj_b, admin_b)
        resp = client_a.get(reverse("crm:resourceallocation_edit", args=[alloc_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, tenant_b, admin_b):
        proj_b = _make_project(tenant_b)
        alloc_b = _make_allocation(tenant_b, proj_b, admin_b)
        today = timezone.localdate()
        resp = client_a.post(reverse("crm:resourceallocation_edit", args=[alloc_b.pk]), {
            "project": proj_b.pk,
            "role": "Hacker",
            "hours_per_week": "80",
            "start_date": today.strftime("%Y-%m-%d"),
            "status": "active",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, tenant_b, admin_b):
        from apps.crm.models import ResourceAllocation
        proj_b = _make_project(tenant_b)
        alloc_b = _make_allocation(tenant_b, proj_b, admin_b)
        pk = alloc_b.pk
        resp = client_a.post(reverse("crm:resourceallocation_delete", args=[pk]))
        assert resp.status_code == 404
        assert ResourceAllocation.objects.filter(pk=pk).exists()

    def test_list_never_contains_other_tenant_rows(self, client_a, tenant_a, tenant_b, admin_user, admin_b):
        proj_a = _make_project(tenant_a)
        proj_b = _make_project(tenant_b)
        alloc_a = _make_allocation(tenant_a, proj_a, admin_user)
        alloc_b = _make_allocation(tenant_b, proj_b, admin_b)
        resp = client_a.get(reverse("crm:resourceallocation_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert alloc_b.pk not in pks
        assert alloc_a.pk in pks


class TestTimesheetIDOR:
    def test_detail_cross_tenant_404(self, client_a, tenant_b, admin_b):
        proj_b = _make_project(tenant_b)
        ts_b = _make_timesheet(tenant_b, proj_b, admin_b)
        resp = client_a.get(reverse("crm:timesheet_detail", args=[ts_b.pk]))
        assert resp.status_code == 404

    def test_submit_cross_tenant_404(self, client_a, tenant_b, admin_b):
        proj_b = _make_project(tenant_b)
        ts_b = _make_timesheet(tenant_b, proj_b, admin_b, status="draft")
        resp = client_a.post(reverse("crm:timesheet_submit", args=[ts_b.pk]))
        assert resp.status_code == 404

    def test_approve_cross_tenant_404(self, client_a, tenant_b, admin_b):
        proj_b = _make_project(tenant_b)
        ts_b = _make_timesheet(tenant_b, proj_b, admin_b, status="submitted")
        resp = client_a.post(reverse("crm:timesheet_approve", args=[ts_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404_record_intact(self, client_a, tenant_b, admin_b):
        from apps.crm.models import Timesheet
        proj_b = _make_project(tenant_b)
        ts_b = _make_timesheet(tenant_b, proj_b, admin_b, status="draft")
        pk = ts_b.pk
        resp = client_a.post(reverse("crm:timesheet_delete", args=[pk]))
        assert resp.status_code == 404
        assert Timesheet.objects.filter(pk=pk).exists()


class TestCrmProjectIDOR:
    def test_detail_cross_tenant_404(self, client_a, tenant_b):
        proj_b = _make_project(tenant_b)
        resp = client_a.get(reverse("crm:crmproject_detail", args=[proj_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, tenant_b):
        proj_b = _make_project(tenant_b)
        resp = client_a.get(reverse("crm:crmproject_edit", args=[proj_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import CrmProject
        proj_b = _make_project(tenant_b)
        pk = proj_b.pk
        resp = client_a.post(reverse("crm:crmproject_delete", args=[pk]))
        assert resp.status_code == 404
        assert CrmProject.objects.filter(pk=pk).exists()


# ======================================================================== Group 8 — Query-count guard

class TestResourceWorkloadQueryCount:
    """resource_workload uses two grouped queries (allocations + timesheets) — no per-person N+1."""

    def test_bounded_queries_with_multiple_users(self, tenant_a, admin_user, member_user):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        today = timezone.localdate()
        monday = today - datetime.timedelta(days=today.weekday())
        win_end = monday + datetime.timedelta(days=27)

        proj = _make_project(tenant_a)
        # Two people, two allocations + two timesheets each
        for user in (admin_user, member_user):
            _make_allocation(tenant_a, proj, user, start_date=monday, end_date=win_end,
                             hours_per_week=Decimal("30"))
            _make_timesheet(tenant_a, proj, user, date=monday, hours=Decimal("5"), status="approved")
            _make_timesheet(tenant_a, proj, user, date=monday + datetime.timedelta(days=1),
                            hours=Decimal("5"), status="submitted")

        c = Client()
        c.force_login(admin_user)
        # Warm up (session/middleware)
        c.get(reverse("crm:resource_workload"))

        with CaptureQueriesContext(connection) as ctx:
            resp = c.get(reverse("crm:resource_workload"))
        assert resp.status_code == 200
        # The view uses two aggregate queries + at most one user-resolve query.
        # Generous cap: must be well under 20 regardless of person count.
        assert len(ctx.captured_queries) < 20, (
            f"Expected <20 queries for workload board (2 users, 4 timesheets), "
            f"got {len(ctx.captured_queries)}. Possible N+1 regression."
        )


# ======================================================================== Auth boundary summary

class TestAuthEnforcement:
    """Anon user must be redirected to login on all 1.8 list/detail/create pages."""

    @pytest.mark.parametrize("url_name", [
        "crm:crmproject_list",
        "crm:crmproject_create",
        "crm:crmproject_board",
        "crm:crmmilestone_list",
        "crm:crmmilestone_create",
        "crm:timesheet_list",
        "crm:timesheet_create",
        "crm:resourceallocation_list",
        "crm:resourceallocation_create",
        "crm:resource_workload",
    ])
    def test_anon_redirects_to_login(self, url_name):
        c = Client()
        resp = c.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestCSRFEnforcement:
    """Destructive POST endpoints must enforce CSRF."""

    def test_timesheet_submit_enforces_csrf(self, admin_user, tenant_a):
        proj = _make_project(tenant_a)
        ts = _make_timesheet(tenant_a, proj, admin_user, status="draft")
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:timesheet_submit", args=[ts.pk]))
        assert resp.status_code == 403

    def test_resourceallocation_delete_enforces_csrf(self, admin_user, tenant_a):
        proj = _make_project(tenant_a)
        alloc = _make_allocation(tenant_a, proj, admin_user)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:resourceallocation_delete", args=[alloc.pk]))
        assert resp.status_code == 403

    def test_crmmilestone_move_enforces_csrf(self, admin_user, tenant_a):
        proj = _make_project(tenant_a)
        ms = _make_milestone(tenant_a, proj, status="not_started")
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:crmmilestone_move", args=[ms.pk]), {"status": "in_progress"})
        assert resp.status_code == 403

    def test_crmproject_delete_enforces_csrf(self, admin_user, tenant_a):
        proj = _make_project(tenant_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:crmproject_delete", args=[proj.pk]))
        assert resp.status_code == 403
