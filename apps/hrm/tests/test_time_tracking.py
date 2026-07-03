"""Comprehensive tests for the HRM 3.11 Time Tracking sub-module — ``Timesheet`` (+
``TimesheetEntry`` inline children), ``OvertimeRequest``, and the two derived report views
(``timesheet_utilization_report`` / ``project_time_report``).

Covers:
  - Timesheet: ``refresh_totals()`` derived total_hours/billable_hours (via views AND the
    admin inline ``save_formset`` path), TS- per-tenant numbering, unique_together
    (tenant, employee, period_start), ``clean()`` period_end >= period_start + the header-edit
    guard that rejects narrowing the period out from under an existing entry.
  - TimesheetEntry: ``clean()`` hours > 0 + date-within-period guard, ``billable_value``
    derived property, optional tenant-scoped ``accounting.Project`` FK.
  - Timesheet workflow via the test client: submit/approve/reject/cancel, lock-on-approval
    (entry add/edit/delete all blocked server-side post-approval, not just hidden buttons),
    edit/delete guards on decided rows, @tenant_admin_required 403 for a non-admin on
    approve/reject.
  - OvertimeRequest: OT- numbering, ``clean()`` hours_claimed > 0 + cross-employee timesheet
    link guard, ``overtime_pay_equivalent_hours`` derived property, full workflow, decided-row
    edit/delete lock, @tenant_admin_required 403 on approve/reject.
  - Reports: timesheet_utilization_report (approved-only, date filter), project_time_report
    (project-only entries, date filter, regression guard against the Sum('hours')-aliased
    FieldError).
  - Multi-tenant IDOR sweep across every Timesheet/TimesheetEntry/OvertimeRequest child-pk
    action.
  - Performance guards on timesheet_list, timesheet_detail, and both reports.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ============================================================
# Timesheet model — refresh_totals()
# ============================================================
class TestTimesheetRefreshTotals:
    def test_refresh_totals_noop_before_save(self, tenant_a, employee_a):
        from apps.hrm.models import Timesheet
        ts = Timesheet(
            tenant=tenant_a, employee=employee_a,
            period_start=datetime.date(2026, 6, 1), period_end=datetime.date(2026, 6, 7),
        )
        ts.refresh_totals()  # no pk yet -> no-op, must not raise
        assert ts.total_hours == Decimal("0")

    def test_refresh_totals_sums_all_entries(self, draft_timesheet_a, tenant_a):
        from apps.hrm.models import TimesheetEntry
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("5"), is_billable=True, billable_rate=Decimal("20"),
        )
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 3),
            hours=Decimal("3"), is_billable=False, billable_rate=Decimal("20"),
        )
        draft_timesheet_a.refresh_totals()
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.total_hours == Decimal("8.00")
        assert draft_timesheet_a.billable_hours == Decimal("5.00")  # only the billable entry

    def test_refresh_totals_after_entry_edit(self, timesheet_entry_a, draft_timesheet_a):
        timesheet_entry_a.hours = Decimal("10")
        timesheet_entry_a.save()
        draft_timesheet_a.refresh_totals()
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.total_hours == Decimal("10.00")
        assert draft_timesheet_a.billable_hours == Decimal("10.00")

    def test_refresh_totals_after_entry_delete(self, timesheet_entry_a, draft_timesheet_a):
        assert draft_timesheet_a.total_hours == Decimal("8.00")
        timesheet_entry_a.delete()
        draft_timesheet_a.refresh_totals()
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.total_hours == Decimal("0")
        assert draft_timesheet_a.billable_hours == Decimal("0")

    def test_refresh_totals_no_entries_is_zero(self, draft_timesheet_a):
        draft_timesheet_a.refresh_totals()
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.total_hours == Decimal("0")
        assert draft_timesheet_a.billable_hours == Decimal("0")

    def test_refresh_totals_via_view_add_entry(self, client_a, draft_timesheet_a):
        resp = client_a.post(
            reverse("hrm:timesheetentry_add", args=[draft_timesheet_a.pk]),
            {"date": "2026-06-03", "task_description": "Dev", "hours": "6",
             "is_billable": "on", "billable_rate": "30"})
        assert resp.status_code == 302
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.total_hours == Decimal("6.00")
        assert draft_timesheet_a.billable_hours == Decimal("6.00")

    def test_refresh_totals_via_view_edit_entry(self, client_a, timesheet_entry_a, draft_timesheet_a):
        resp = client_a.post(
            reverse("hrm:timesheetentry_edit", args=[timesheet_entry_a.pk]),
            {"date": "2026-06-02", "task_description": "Updated", "hours": "3",
             "is_billable": "on", "billable_rate": "50"})
        assert resp.status_code == 302
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.total_hours == Decimal("3.00")
        assert draft_timesheet_a.billable_hours == Decimal("3.00")

    def test_refresh_totals_via_view_delete_entry(self, client_a, timesheet_entry_a, draft_timesheet_a):
        resp = client_a.post(reverse("hrm:timesheetentry_delete", args=[timesheet_entry_a.pk]))
        assert resp.status_code == 302
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.total_hours == Decimal("0")
        assert draft_timesheet_a.billable_hours == Decimal("0")

    def test_admin_inline_save_formset_refreshes_totals(self, tenant_a, employee_a, admin_user):
        """The admin's TimesheetAdmin.save_formset override must call refresh_totals() after
        an inline TimesheetEntry add — mirrors the app's own views (admin.py:181-186)."""
        from django.contrib import admin as admin_site_mod
        from django.forms.models import inlineformset_factory
        from django.test import RequestFactory

        from apps.hrm.admin import TimesheetAdmin
        from apps.hrm.models import Timesheet, TimesheetEntry

        ts = Timesheet.objects.create(
            tenant=tenant_a, employee=employee_a,
            period_start=datetime.date(2026, 6, 1), period_end=datetime.date(2026, 6, 7),
        )
        assert ts.total_hours == Decimal("0")

        ma = TimesheetAdmin(Timesheet, admin_site_mod.site)
        rf = RequestFactory()
        req = rf.post(f"/admin/hrm/timesheet/{ts.pk}/change/")
        req.user = admin_user

        FormSet = inlineformset_factory(
            Timesheet, TimesheetEntry,
            fields=["tenant", "timesheet", "date", "project", "task_description",
                    "hours", "is_billable", "billable_rate", "notes"],
            extra=1,
        )
        data = {
            "entries-TOTAL_FORMS": "1",
            "entries-INITIAL_FORMS": "0",
            "entries-MIN_NUM_FORMS": "0",
            "entries-MAX_NUM_FORMS": "1000",
            "entries-0-tenant": str(tenant_a.pk),
            "entries-0-timesheet": str(ts.pk),
            "entries-0-date": "2026-06-02",
            "entries-0-hours": "8",
            "entries-0-is_billable": "on",
            "entries-0-billable_rate": "50",
        }
        formset = FormSet(data, instance=ts, prefix="entries")
        assert formset.is_valid(), formset.errors

        class _DummyForm:
            instance = ts

        ma.save_formset(req, _DummyForm(), formset, change=True)
        ts.refresh_from_db()
        assert ts.total_hours == Decimal("8.00")
        assert ts.billable_hours == Decimal("8.00")

    def test_admin_inline_save_formset_refreshes_totals_on_edit(self, tenant_a, employee_a, admin_user):
        """A second admin inline pass that edits an existing entry's hours must also refresh
        totals — not just the initial add."""
        from django.contrib import admin as admin_site_mod
        from django.forms.models import inlineformset_factory
        from django.test import RequestFactory

        from apps.hrm.admin import TimesheetAdmin
        from apps.hrm.models import Timesheet, TimesheetEntry

        ts = Timesheet.objects.create(
            tenant=tenant_a, employee=employee_a,
            period_start=datetime.date(2026, 6, 1), period_end=datetime.date(2026, 6, 7),
        )
        entry = TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=ts, date=datetime.date(2026, 6, 2),
            hours=Decimal("4"), is_billable=True, billable_rate=Decimal("10"),
        )
        ts.refresh_totals()
        assert ts.total_hours == Decimal("4.00")

        ma = TimesheetAdmin(Timesheet, admin_site_mod.site)
        rf = RequestFactory()
        req = rf.post(f"/admin/hrm/timesheet/{ts.pk}/change/")
        req.user = admin_user

        FormSet = inlineformset_factory(
            Timesheet, TimesheetEntry,
            fields=["tenant", "timesheet", "date", "project", "task_description",
                    "hours", "is_billable", "billable_rate", "notes"],
            extra=0,
        )
        data = {
            "entries-TOTAL_FORMS": "1",
            "entries-INITIAL_FORMS": "1",
            "entries-MIN_NUM_FORMS": "0",
            "entries-MAX_NUM_FORMS": "1000",
            "entries-0-id": str(entry.pk),
            "entries-0-tenant": str(tenant_a.pk),
            "entries-0-timesheet": str(ts.pk),
            "entries-0-date": "2026-06-02",
            "entries-0-hours": "9",
            "entries-0-is_billable": "on",
            "entries-0-billable_rate": "10",
        }
        formset = FormSet(data, instance=ts, prefix="entries")
        assert formset.is_valid(), formset.errors

        class _DummyForm:
            instance = ts

        ma.save_formset(req, _DummyForm(), formset, change=True)
        ts.refresh_from_db()
        assert ts.total_hours == Decimal("9.00")  # not stuck at the old 4.00


# ============================================================
# Timesheet model — TS- numbering + unique_together
# ============================================================
class TestTimesheetNumbering:
    def test_number_prefix_and_format(self, draft_timesheet_a):
        assert draft_timesheet_a.number == "TS-00001"

    def test_sequential_within_tenant(self, tenant_a, employee_a, draft_timesheet_a):
        from apps.hrm.models import Timesheet
        ts2 = Timesheet.objects.create(
            tenant=tenant_a, employee=employee_a,
            period_start=datetime.date(2026, 6, 8), period_end=datetime.date(2026, 6, 14),
        )
        assert ts2.number == "TS-00002"

    def test_numbering_isolated_across_tenants(self, draft_timesheet_a, tenant_b, employee_b):
        from apps.hrm.models import Timesheet
        ts_b = Timesheet.objects.create(
            tenant=tenant_b, employee=employee_b,
            period_start=datetime.date(2026, 6, 1), period_end=datetime.date(2026, 6, 7),
        )
        assert draft_timesheet_a.number == "TS-00001"
        assert ts_b.number == "TS-00001"

    def test_unique_together_tenant_number(self, tenant_a, draft_timesheet_a, employee_a):
        from apps.hrm.models import Timesheet
        with pytest.raises(IntegrityError):
            Timesheet.objects.create(
                tenant=tenant_a, employee=employee_a, number="TS-00001",
                period_start=datetime.date(2026, 7, 1), period_end=datetime.date(2026, 7, 7),
            )

    def test_unique_together_tenant_employee_period_start(self, tenant_a, draft_timesheet_a, employee_a):
        """(tenant, employee, period_start) is unique — a second timesheet for the same
        employee starting on the same date must fail even with a distinct number."""
        from apps.hrm.models import Timesheet
        with pytest.raises(IntegrityError):
            Timesheet.objects.create(
                tenant=tenant_a, employee=employee_a,
                period_start=draft_timesheet_a.period_start,
                period_end=datetime.date(2026, 6, 10),
            )

    def test_different_employee_same_period_start_allowed(
            self, tenant_a, draft_timesheet_a, person_a2, dept_a):
        """The unique_together is scoped by employee — a different employee CAN start a
        timesheet on the same period_start."""
        from apps.core.models import Employment
        from apps.hrm.models import EmployeeProfile, Timesheet
        emp2_employment = Employment.objects.create(
            tenant=tenant_a, party=person_a2, org_unit=dept_a, job_title="QA", status="active",
        )
        emp2 = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a2, employment=emp2_employment, employee_type="full_time",
        )
        ts2 = Timesheet.objects.create(
            tenant=tenant_a, employee=emp2,
            period_start=draft_timesheet_a.period_start, period_end=datetime.date(2026, 6, 7),
        )
        assert ts2.pk is not None

    def test_str(self, draft_timesheet_a):
        s = str(draft_timesheet_a)
        assert draft_timesheet_a.number in s


# ============================================================
# Timesheet model — clean() guards
# ============================================================
class TestTimesheetClean:
    def test_rejects_period_end_before_period_start(self, tenant_a, employee_a):
        from apps.hrm.models import Timesheet
        ts = Timesheet(
            tenant=tenant_a, employee=employee_a,
            period_start=datetime.date(2026, 6, 10), period_end=datetime.date(2026, 6, 1),
        )
        with pytest.raises(ValidationError) as exc:
            ts.full_clean()
        assert "period_end" in exc.value.message_dict

    def test_accepts_period_end_equal_to_start(self, tenant_a, employee_a):
        from apps.hrm.models import Timesheet
        ts = Timesheet(
            tenant=tenant_a, employee=employee_a,
            period_start=datetime.date(2026, 6, 10), period_end=datetime.date(2026, 6, 10),
        )
        ts.full_clean()  # must not raise

    def test_header_edit_narrowing_period_rejected_when_entry_would_be_stranded(
            self, timesheet_entry_a, draft_timesheet_a):
        """timesheet_entry_a is dated 2026-06-02; narrowing the period to start on 06-03
        would strand it outside the period."""
        draft_timesheet_a.period_start = datetime.date(2026, 6, 3)
        with pytest.raises(ValidationError) as exc:
            draft_timesheet_a.full_clean()
        assert "period_start" in exc.value.message_dict

    def test_header_edit_widening_period_is_allowed(self, timesheet_entry_a, draft_timesheet_a):
        draft_timesheet_a.period_start = datetime.date(2026, 5, 25)
        draft_timesheet_a.full_clean()  # must not raise — still covers the entry

    def test_header_edit_without_entries_can_narrow_freely(self, draft_timesheet_a):
        draft_timesheet_a.period_start = datetime.date(2026, 6, 5)
        draft_timesheet_a.full_clean()  # no entries -> no guard triggered


# ============================================================
# TimesheetEntry model — clean() guards
# ============================================================
class TestTimesheetEntryClean:
    def test_rejects_zero_hours(self, tenant_a, draft_timesheet_a):
        from apps.hrm.models import TimesheetEntry
        entry = TimesheetEntry(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("0"),
        )
        with pytest.raises(ValidationError) as exc:
            entry.full_clean()
        assert "hours" in exc.value.message_dict

    def test_rejects_negative_hours(self, tenant_a, draft_timesheet_a):
        from apps.hrm.models import TimesheetEntry
        entry = TimesheetEntry(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("-1"),
        )
        with pytest.raises(ValidationError) as exc:
            entry.full_clean()
        assert "hours" in exc.value.message_dict

    def test_rejects_date_before_period_start(self, tenant_a, draft_timesheet_a):
        """draft_timesheet_a period is 2026-06-01..2026-06-07."""
        from apps.hrm.models import TimesheetEntry
        entry = TimesheetEntry(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 5, 31),
            hours=Decimal("2"),
        )
        with pytest.raises(ValidationError) as exc:
            entry.full_clean()
        assert "date" in exc.value.message_dict

    def test_rejects_date_after_period_end(self, tenant_a, draft_timesheet_a):
        from apps.hrm.models import TimesheetEntry
        entry = TimesheetEntry(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 8),
            hours=Decimal("2"),
        )
        with pytest.raises(ValidationError) as exc:
            entry.full_clean()
        assert "date" in exc.value.message_dict

    def test_accepts_date_at_period_boundaries(self, tenant_a, draft_timesheet_a):
        from apps.hrm.models import TimesheetEntry
        entry_start = TimesheetEntry(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 1),
            hours=Decimal("2"),
        )
        entry_start.full_clean()  # must not raise
        entry_end = TimesheetEntry(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 7),
            hours=Decimal("2"),
        )
        entry_end.full_clean()  # must not raise


# ============================================================
# TimesheetEntry model — billable_value property
# ============================================================
class TestTimesheetEntryBillableValue:
    def test_billable_value_when_billable(self, timesheet_entry_a):
        assert timesheet_entry_a.billable_value == Decimal("400")  # 8h * 50

    def test_billable_value_zero_when_not_billable(self, tenant_a, draft_timesheet_a):
        from apps.hrm.models import TimesheetEntry
        entry = TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("8"), is_billable=False, billable_rate=Decimal("50"),
        )
        assert entry.billable_value == Decimal("0")

    def test_billable_value_zero_rate(self, tenant_a, draft_timesheet_a):
        from apps.hrm.models import TimesheetEntry
        entry = TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("8"), is_billable=True, billable_rate=Decimal("0"),
        )
        assert entry.billable_value == Decimal("0")

    def test_str(self, timesheet_entry_a):
        s = str(timesheet_entry_a)
        assert timesheet_entry_a.timesheet.number in s


# ============================================================
# TimesheetEntry — optional Project FK + tenant scoping in the form
# ============================================================
class TestTimesheetEntryProjectField:
    def test_project_is_optional(self, tenant_a, draft_timesheet_a):
        from apps.hrm.models import TimesheetEntry
        entry = TimesheetEntry(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("2"), project=None,
        )
        entry.full_clean()  # must not raise

    def test_form_rejects_cross_tenant_project(self, tenant_a, draft_timesheet_a, project_b):
        from apps.hrm.forms import TimesheetEntryForm
        from apps.hrm.models import TimesheetEntry
        # Instance bound to the parent timesheet, like the view does (timesheetentry_add).
        form = TimesheetEntryForm({
            "date": "2026-06-02", "hours": "3", "is_billable": "on",
            "billable_rate": "10", "project": project_b.pk,
        }, instance=TimesheetEntry(tenant=tenant_a, timesheet=draft_timesheet_a), tenant=tenant_a)
        assert not form.is_valid()
        assert "project" in form.errors

    def test_form_accepts_same_tenant_project(self, tenant_a, draft_timesheet_a, project_a):
        from apps.hrm.forms import TimesheetEntryForm
        from apps.hrm.models import TimesheetEntry
        form = TimesheetEntryForm({
            "date": "2026-06-02", "hours": "3", "is_billable": "on",
            "billable_rate": "10", "project": project_a.pk,
        }, instance=TimesheetEntry(tenant=tenant_a, timesheet=draft_timesheet_a), tenant=tenant_a)
        assert form.is_valid(), form.errors


# ============================================================
# Timesheet workflow — submit / approve / reject / cancel
# ============================================================
class TestTimesheetWorkflow:
    def test_submit_draft_to_pending(self, client_a, draft_timesheet_a):
        resp = client_a.post(reverse("hrm:timesheet_submit", args=[draft_timesheet_a.pk]))
        assert resp.status_code == 302
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.status == "pending"

    def test_submit_noop_when_not_draft(self, client_a, pending_timesheet_a):
        resp = client_a.post(reverse("hrm:timesheet_submit", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 302
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "pending"

    def test_approve_pending_to_approved(self, client_a, admin_user, pending_timesheet_a):
        resp = client_a.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 302
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "approved"
        assert pending_timesheet_a.approver == admin_user
        assert pending_timesheet_a.approved_at is not None

    def test_approve_does_final_refresh_of_totals(self, client_a, tenant_a, pending_timesheet_a):
        """approve() calls refresh_totals(save=False) then saves total/billable explicitly —
        confirm the persisted totals reflect the entries at approval time."""
        from apps.hrm.models import TimesheetEntry
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=pending_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("6"), is_billable=True, billable_rate=Decimal("25"),
        )
        # Deliberately do NOT call refresh_totals() here — approve() must do its own final pass.
        resp = client_a.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 302
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.total_hours == Decimal("6.00")
        assert pending_timesheet_a.billable_hours == Decimal("6.00")

    def test_reject_pending_to_rejected(self, client_a, pending_timesheet_a):
        resp = client_a.post(
            reverse("hrm:timesheet_reject", args=[pending_timesheet_a.pk]),
            {"rejected_reason": "Missing task detail"})
        assert resp.status_code == 302
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "rejected"
        assert pending_timesheet_a.rejected_reason == "Missing task detail"

    def test_cancel_draft(self, client_a, draft_timesheet_a):
        resp = client_a.post(reverse("hrm:timesheet_cancel", args=[draft_timesheet_a.pk]))
        assert resp.status_code == 302
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.status == "cancelled"

    def test_cancel_pending(self, client_a, pending_timesheet_a):
        resp = client_a.post(reverse("hrm:timesheet_cancel", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 302
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "cancelled"

    def test_cancel_noop_once_approved(self, client_a, pending_timesheet_a):
        client_a.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "approved"
        resp = client_a.post(reverse("hrm:timesheet_cancel", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 302
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "approved"  # unchanged


# ============================================================
# Timesheet workflow — lock-on-approval for entries
# ============================================================
class TestTimesheetLockOnApproval:
    def test_entry_add_blocked_after_approval(self, client_a, timesheet_entry_a, draft_timesheet_a):
        client_a.post(reverse("hrm:timesheet_submit", args=[draft_timesheet_a.pk]))
        client_a.post(reverse("hrm:timesheet_approve", args=[draft_timesheet_a.pk]))
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.status == "approved"
        total_before = draft_timesheet_a.total_hours

        resp = client_a.post(
            reverse("hrm:timesheetentry_add", args=[draft_timesheet_a.pk]),
            {"date": "2026-06-03", "hours": "99", "is_billable": "on", "billable_rate": "10"})
        assert resp.status_code == 302
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.total_hours == total_before  # unchanged — not mutated
        from apps.hrm.models import TimesheetEntry
        assert TimesheetEntry.objects.filter(timesheet=draft_timesheet_a).count() == 1  # no new row

    def test_entry_edit_blocked_after_approval(self, client_a, timesheet_entry_a, draft_timesheet_a):
        client_a.post(reverse("hrm:timesheet_submit", args=[draft_timesheet_a.pk]))
        client_a.post(reverse("hrm:timesheet_approve", args=[draft_timesheet_a.pk]))
        original_hours = timesheet_entry_a.hours
        resp = client_a.post(
            reverse("hrm:timesheetentry_edit", args=[timesheet_entry_a.pk]),
            {"date": "2026-06-02", "hours": "99", "is_billable": "on", "billable_rate": "50"})
        assert resp.status_code == 302
        timesheet_entry_a.refresh_from_db()
        assert timesheet_entry_a.hours == original_hours  # unchanged — locked

    def test_entry_delete_blocked_after_approval(self, client_a, timesheet_entry_a, draft_timesheet_a):
        client_a.post(reverse("hrm:timesheet_submit", args=[draft_timesheet_a.pk]))
        client_a.post(reverse("hrm:timesheet_approve", args=[draft_timesheet_a.pk]))
        resp = client_a.post(reverse("hrm:timesheetentry_delete", args=[timesheet_entry_a.pk]))
        assert resp.status_code == 302
        from apps.hrm.models import TimesheetEntry
        assert TimesheetEntry.objects.filter(pk=timesheet_entry_a.pk).exists()  # not deleted

    def test_entry_add_blocked_after_rejection(self, client_a, draft_timesheet_a):
        client_a.post(reverse("hrm:timesheet_submit", args=[draft_timesheet_a.pk]))
        client_a.post(reverse("hrm:timesheet_reject", args=[draft_timesheet_a.pk]))
        resp = client_a.post(
            reverse("hrm:timesheetentry_add", args=[draft_timesheet_a.pk]),
            {"date": "2026-06-03", "hours": "2", "is_billable": "on", "billable_rate": "10"})
        assert resp.status_code == 302
        from apps.hrm.models import TimesheetEntry
        assert TimesheetEntry.objects.filter(timesheet=draft_timesheet_a).count() == 0

    def test_entry_add_allowed_while_draft(self, client_a, draft_timesheet_a):
        resp = client_a.post(
            reverse("hrm:timesheetentry_add", args=[draft_timesheet_a.pk]),
            {"date": "2026-06-03", "hours": "2", "is_billable": "on", "billable_rate": "10"})
        assert resp.status_code == 302
        from apps.hrm.models import TimesheetEntry
        assert TimesheetEntry.objects.filter(timesheet=draft_timesheet_a).count() == 1

    def test_entry_add_allowed_while_pending(self, client_a, pending_timesheet_a):
        resp = client_a.post(
            reverse("hrm:timesheetentry_add", args=[pending_timesheet_a.pk]),
            {"date": "2026-06-03", "hours": "2", "is_billable": "on", "billable_rate": "10"})
        assert resp.status_code == 302
        from apps.hrm.models import TimesheetEntry
        assert TimesheetEntry.objects.filter(timesheet=pending_timesheet_a).count() == 1


# ============================================================
# Timesheet workflow — edit/delete guards on the header
# ============================================================
class TestTimesheetEditDeleteGuards:
    def test_edit_get_allowed_for_draft(self, client_a, draft_timesheet_a):
        resp = client_a.get(reverse("hrm:timesheet_edit", args=[draft_timesheet_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_allowed_for_pending(self, client_a, pending_timesheet_a):
        resp = client_a.get(reverse("hrm:timesheet_edit", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 200

    def test_edit_redirects_when_approved(self, client_a, pending_timesheet_a):
        client_a.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        resp = client_a.get(reverse("hrm:timesheet_edit", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:timesheet_detail", args=[pending_timesheet_a.pk])

    def test_edit_post_does_not_mutate_when_approved(self, client_a, pending_timesheet_a):
        client_a.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        original_start = pending_timesheet_a.period_start
        client_a.post(reverse("hrm:timesheet_edit", args=[pending_timesheet_a.pk]), {
            "employee": pending_timesheet_a.employee_id,
            "period_start": "2000-01-01", "period_end": "2000-01-07",
        })
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.period_start == original_start  # unchanged — locked

    def test_delete_allowed_for_draft(self, client_a, draft_timesheet_a):
        from apps.hrm.models import Timesheet
        pk = draft_timesheet_a.pk
        resp = client_a.post(reverse("hrm:timesheet_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Timesheet.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_approved(self, client_a, pending_timesheet_a):
        from apps.hrm.models import Timesheet
        client_a.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        pk = pending_timesheet_a.pk
        resp = client_a.post(reverse("hrm:timesheet_delete", args=[pk]))
        assert resp.status_code == 302
        assert Timesheet.objects.filter(pk=pk).exists()  # not deleted

    def test_delete_blocked_when_rejected(self, client_a, pending_timesheet_a):
        from apps.hrm.models import Timesheet
        client_a.post(reverse("hrm:timesheet_reject", args=[pending_timesheet_a.pk]))
        pk = pending_timesheet_a.pk
        resp = client_a.post(reverse("hrm:timesheet_delete", args=[pk]))
        assert resp.status_code == 302
        assert Timesheet.objects.filter(pk=pk).exists()  # not deleted

    def test_delete_requires_post(self, client_a, draft_timesheet_a):
        from apps.hrm.models import Timesheet
        resp = client_a.get(reverse("hrm:timesheet_delete", args=[draft_timesheet_a.pk]))
        assert resp.status_code == 405
        assert Timesheet.objects.filter(pk=draft_timesheet_a.pk).exists()


# ============================================================
# Timesheet workflow — authorization (@tenant_admin_required)
# ============================================================
class TestTimesheetWorkflowAuthorization:
    def test_nonadmin_approve_403(self, member_client, pending_timesheet_a):
        resp = member_client.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 403
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "pending"

    def test_nonadmin_reject_403(self, member_client, pending_timesheet_a):
        resp = member_client.post(reverse("hrm:timesheet_reject", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 403
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "pending"

    def test_nonadmin_submit_allowed(self, member_client, draft_timesheet_a):
        resp = member_client.post(reverse("hrm:timesheet_submit", args=[draft_timesheet_a.pk]))
        assert resp.status_code == 302
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.status == "pending"

    def test_nonadmin_cancel_allowed(self, member_client, draft_timesheet_a):
        resp = member_client.post(reverse("hrm:timesheet_cancel", args=[draft_timesheet_a.pk]))
        assert resp.status_code == 302
        draft_timesheet_a.refresh_from_db()
        assert draft_timesheet_a.status == "cancelled"

    def test_admin_approve_succeeds(self, client_a, pending_timesheet_a):
        resp = client_a.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 302
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "approved"

    def test_template_gate_is_not_the_only_guard(self, member_client, pending_timesheet_a):
        """A crafted POST straight to the approve endpoint (no hidden-button click) must
        still be blocked server-side."""
        resp = member_client.post(
            reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]), {"decision_note": "forged"})
        assert resp.status_code == 403
        pending_timesheet_a.refresh_from_db()
        assert pending_timesheet_a.status == "pending"


# ============================================================
# Timesheet list/detail views
# ============================================================
class TestTimesheetListDetailViews:
    def test_list_ok(self, client_a, pending_timesheet_a):
        resp = client_a.get(reverse("hrm:timesheet_list"))
        assert resp.status_code == 200
        assert pending_timesheet_a.number.encode() in resp.content

    def test_filter_by_status(self, client_a, draft_timesheet_a):
        resp = client_a.get(reverse("hrm:timesheet_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_timesheet_a.pk in pks

    def test_search_by_employee_name(self, client_a, draft_timesheet_a, employee_a):
        resp = client_a.get(reverse("hrm:timesheet_list"), {"q": employee_a.party.name})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_timesheet_a.pk in pks

    def test_date_from_filters_by_period_start(self, client_a, draft_timesheet_a):
        resp = client_a.get(reverse("hrm:timesheet_list"), {"date_from": "2026-07-01"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_timesheet_a.pk not in pks  # period_start is 2026-06-01, before the filter

    def test_create_view_post(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import Timesheet
        resp = client_a.post(reverse("hrm:timesheet_create"), {
            "employee": employee_a.pk,
            "period_start": "2026-09-01", "period_end": "2026-09-07",
        })
        assert resp.status_code == 302
        ts = Timesheet.objects.get(tenant=tenant_a, employee=employee_a, period_start=datetime.date(2026, 9, 1))
        assert ts.tenant_id == tenant_a.pk
        assert ts.status == "draft"

    def test_detail_ok(self, client_a, pending_timesheet_a):
        resp = client_a.get(reverse("hrm:timesheet_detail", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == pending_timesheet_a.pk

    def test_detail_has_entries_in_context(self, client_a, timesheet_entry_a, draft_timesheet_a):
        resp = client_a.get(reverse("hrm:timesheet_detail", args=[draft_timesheet_a.pk]))
        entry_pks = [e.pk for e in resp.context["entries"]]
        assert timesheet_entry_a.pk in entry_pks

    def test_detail_can_edit_entries_true_while_draft(self, client_a, draft_timesheet_a):
        resp = client_a.get(reverse("hrm:timesheet_detail", args=[draft_timesheet_a.pk]))
        assert resp.context["can_edit_entries"] is True

    def test_detail_can_edit_entries_false_when_approved(self, client_a, pending_timesheet_a):
        client_a.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        resp = client_a.get(reverse("hrm:timesheet_detail", args=[pending_timesheet_a.pk]))
        assert resp.context["can_edit_entries"] is False


# ============================================================
# TimesheetForm — excluded fields
# ============================================================
class TestTimesheetForm:
    def test_excludes_workflow_and_derived_fields(self):
        from apps.hrm.forms import TimesheetForm
        excluded = {"status", "approver", "approved_at", "decision_note", "rejected_reason",
                    "total_hours", "billable_hours", "number", "tenant"}
        assert not (excluded & set(TimesheetForm.Meta.fields))

    def test_required_fields_missing(self, tenant_a):
        from apps.hrm.forms import TimesheetForm
        form = TimesheetForm({}, tenant=tenant_a)
        assert not form.is_valid()
        for f in ("employee", "period_start", "period_end"):
            assert f in form.errors

    def test_valid_form_saves(self, tenant_a, employee_a):
        from apps.hrm.forms import TimesheetForm
        form = TimesheetForm({
            "employee": employee_a.pk, "period_start": "2026-10-01", "period_end": "2026-10-07",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save(commit=False)
        obj.tenant = tenant_a
        obj.save()
        assert obj.status == "draft"
        assert obj.number.startswith("TS-")


# ============================================================
# TimesheetEntryForm — excluded fields
# ============================================================
class TestTimesheetEntryForm:
    def test_timesheet_not_a_form_field(self):
        """timesheet is set from the view/URL, never on the form (no cross-timesheet reassign)."""
        from apps.hrm.forms import TimesheetEntryForm
        assert "timesheet" not in TimesheetEntryForm.Meta.fields
        assert "tenant" not in TimesheetEntryForm.Meta.fields

    def test_required_fields_missing(self, tenant_a, draft_timesheet_a):
        from apps.hrm.forms import TimesheetEntryForm
        from apps.hrm.models import TimesheetEntry
        form = TimesheetEntryForm({}, instance=TimesheetEntry(tenant=tenant_a, timesheet=draft_timesheet_a),
                                  tenant=tenant_a)
        assert not form.is_valid()
        for f in ("date", "hours"):
            assert f in form.errors

    def test_out_of_period_date_rejected_by_form(self, tenant_a, draft_timesheet_a):
        from apps.hrm.forms import TimesheetEntryForm
        from apps.hrm.models import TimesheetEntry
        form = TimesheetEntryForm({
            "date": "2026-06-30", "hours": "2", "is_billable": "on", "billable_rate": "10",
        }, instance=TimesheetEntry(tenant=tenant_a, timesheet=draft_timesheet_a), tenant=tenant_a)
        assert not form.is_valid()
        assert "date" in form.errors


# ============================================================
# OvertimeRequest model — OT- numbering
# ============================================================
class TestOvertimeRequestNumbering:
    def test_number_prefix_and_format(self, draft_overtime_a):
        assert draft_overtime_a.number == "OT-00001"

    def test_sequential_within_tenant(self, tenant_a, employee_a, draft_overtime_a):
        from apps.hrm.models import OvertimeRequest
        ot2 = OvertimeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 3),
            hours_claimed=Decimal("2"), reason="More overtime",
        )
        assert ot2.number == "OT-00002"

    def test_numbering_isolated_across_tenants(self, draft_overtime_a, tenant_b, employee_b):
        from apps.hrm.models import OvertimeRequest
        ot_b = OvertimeRequest.objects.create(
            tenant=tenant_b, employee=employee_b, date=datetime.date(2026, 6, 2),
            hours_claimed=Decimal("2"), reason="Overtime B",
        )
        assert draft_overtime_a.number == "OT-00001"
        assert ot_b.number == "OT-00001"

    def test_unique_together_tenant_number(self, tenant_a, draft_overtime_a, employee_a):
        from apps.hrm.models import OvertimeRequest
        with pytest.raises(IntegrityError):
            OvertimeRequest.objects.create(
                tenant=tenant_a, employee=employee_a, number="OT-00001",
                date=datetime.date(2026, 6, 5), hours_claimed=Decimal("1"), reason="Dup",
            )

    def test_str(self, draft_overtime_a):
        s = str(draft_overtime_a)
        assert draft_overtime_a.number in s


# ============================================================
# OvertimeRequest model — clean() guards
# ============================================================
class TestOvertimeRequestClean:
    def test_rejects_zero_hours_claimed(self, tenant_a, employee_a):
        from apps.hrm.models import OvertimeRequest
        ot = OvertimeRequest(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 2),
            hours_claimed=Decimal("0"), reason="x",
        )
        with pytest.raises(ValidationError) as exc:
            ot.full_clean()
        assert "hours_claimed" in exc.value.message_dict

    def test_rejects_negative_hours_claimed(self, tenant_a, employee_a):
        from apps.hrm.models import OvertimeRequest
        ot = OvertimeRequest(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 2),
            hours_claimed=Decimal("-2"), reason="x",
        )
        with pytest.raises(ValidationError) as exc:
            ot.full_clean()
        assert "hours_claimed" in exc.value.message_dict

    def test_rejects_timesheet_belonging_to_different_employee(
            self, tenant_a, employee_a, person_a2, dept_a):
        from apps.core.models import Employment
        from apps.hrm.models import EmployeeProfile, OvertimeRequest, Timesheet
        other_employment = Employment.objects.create(
            tenant=tenant_a, party=person_a2, org_unit=dept_a, job_title="QA", status="active",
        )
        other_employee = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a2, employment=other_employment, employee_type="full_time",
        )
        other_ts = Timesheet.objects.create(
            tenant=tenant_a, employee=other_employee,
            period_start=datetime.date(2026, 6, 1), period_end=datetime.date(2026, 6, 7),
        )
        ot = OvertimeRequest(
            tenant=tenant_a, employee=employee_a, timesheet=other_ts,
            date=datetime.date(2026, 6, 2), hours_claimed=Decimal("2"), reason="x",
        )
        with pytest.raises(ValidationError) as exc:
            ot.full_clean()
        assert "timesheet" in exc.value.message_dict

    def test_accepts_timesheet_belonging_to_same_employee(self, tenant_a, employee_a, draft_timesheet_a):
        from apps.hrm.models import OvertimeRequest
        ot = OvertimeRequest(
            tenant=tenant_a, employee=employee_a, timesheet=draft_timesheet_a,
            date=datetime.date(2026, 6, 2), hours_claimed=Decimal("2"), reason="x",
        )
        ot.full_clean()  # must not raise

    def test_accepts_no_timesheet(self, tenant_a, employee_a):
        from apps.hrm.models import OvertimeRequest
        ot = OvertimeRequest(
            tenant=tenant_a, employee=employee_a, timesheet=None,
            date=datetime.date(2026, 6, 2), hours_claimed=Decimal("2"), reason="x",
        )
        ot.full_clean()  # must not raise


# ============================================================
# OvertimeRequest model — overtime_pay_equivalent_hours
# ============================================================
class TestOvertimePayEquivalentHours:
    def test_computed_from_hours_and_multiplier(self, draft_overtime_a):
        assert draft_overtime_a.overtime_pay_equivalent_hours == Decimal("4.500")  # 3 * 1.5

    def test_default_multiplier(self, tenant_a, employee_a):
        from apps.hrm.models import OvertimeRequest
        ot = OvertimeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 2),
            hours_claimed=Decimal("4"), reason="x",
        )
        assert ot.multiplier == Decimal("1.50")
        assert ot.overtime_pay_equivalent_hours == Decimal("6.000")

    def test_custom_multiplier(self, tenant_a, employee_a):
        from apps.hrm.models import OvertimeRequest
        ot = OvertimeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 2),
            hours_claimed=Decimal("2"), multiplier=Decimal("2.00"), reason="Holiday OT",
        )
        assert ot.overtime_pay_equivalent_hours == Decimal("4.000")


# ============================================================
# OvertimeRequest workflow — submit / approve / reject / cancel
# ============================================================
class TestOvertimeRequestWorkflow:
    def test_submit_draft_to_pending(self, client_a, draft_overtime_a):
        resp = client_a.post(reverse("hrm:overtimerequest_submit", args=[draft_overtime_a.pk]))
        assert resp.status_code == 302
        draft_overtime_a.refresh_from_db()
        assert draft_overtime_a.status == "pending"

    def test_approve_pending_to_approved(self, client_a, admin_user, pending_overtime_a):
        resp = client_a.post(reverse("hrm:overtimerequest_approve", args=[pending_overtime_a.pk]))
        assert resp.status_code == 302
        pending_overtime_a.refresh_from_db()
        assert pending_overtime_a.status == "approved"
        assert pending_overtime_a.approver == admin_user
        assert pending_overtime_a.approved_at is not None

    def test_reject_pending_to_rejected(self, client_a, pending_overtime_a):
        resp = client_a.post(
            reverse("hrm:overtimerequest_reject", args=[pending_overtime_a.pk]),
            {"decision_note": "Not authorized"})
        assert resp.status_code == 302
        pending_overtime_a.refresh_from_db()
        assert pending_overtime_a.status == "rejected"

    def test_cancel_draft(self, client_a, draft_overtime_a):
        resp = client_a.post(reverse("hrm:overtimerequest_cancel", args=[draft_overtime_a.pk]))
        assert resp.status_code == 302
        draft_overtime_a.refresh_from_db()
        assert draft_overtime_a.status == "cancelled"

    def test_cancel_pending(self, client_a, pending_overtime_a):
        resp = client_a.post(reverse("hrm:overtimerequest_cancel", args=[pending_overtime_a.pk]))
        assert resp.status_code == 302
        pending_overtime_a.refresh_from_db()
        assert pending_overtime_a.status == "cancelled"

    def test_cancel_noop_once_approved(self, client_a, pending_overtime_a):
        client_a.post(reverse("hrm:overtimerequest_approve", args=[pending_overtime_a.pk]))
        resp = client_a.post(reverse("hrm:overtimerequest_cancel", args=[pending_overtime_a.pk]))
        assert resp.status_code == 302
        pending_overtime_a.refresh_from_db()
        assert pending_overtime_a.status == "approved"  # unchanged


# ============================================================
# OvertimeRequest workflow — edit/delete guards on decided rows
# ============================================================
class TestOvertimeRequestEditDeleteGuards:
    def test_edit_get_allowed_for_draft(self, client_a, draft_overtime_a):
        resp = client_a.get(reverse("hrm:overtimerequest_edit", args=[draft_overtime_a.pk]))
        assert resp.status_code == 200

    def test_edit_redirects_when_approved(self, client_a, pending_overtime_a):
        client_a.post(reverse("hrm:overtimerequest_approve", args=[pending_overtime_a.pk]))
        resp = client_a.get(reverse("hrm:overtimerequest_edit", args=[pending_overtime_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:overtimerequest_detail", args=[pending_overtime_a.pk])

    def test_edit_post_does_not_mutate_when_approved(self, client_a, pending_overtime_a):
        client_a.post(reverse("hrm:overtimerequest_approve", args=[pending_overtime_a.pk]))
        original_hours = pending_overtime_a.hours_claimed
        client_a.post(reverse("hrm:overtimerequest_edit", args=[pending_overtime_a.pk]), {
            "employee": pending_overtime_a.employee_id,
            "date": "2026-06-02", "hours_claimed": "999", "multiplier": "1.5",
            "payout_method": "pay", "reason": "forged",
        })
        pending_overtime_a.refresh_from_db()
        assert pending_overtime_a.hours_claimed == original_hours  # unchanged — locked

    def test_delete_allowed_for_draft(self, client_a, draft_overtime_a):
        from apps.hrm.models import OvertimeRequest
        pk = draft_overtime_a.pk
        resp = client_a.post(reverse("hrm:overtimerequest_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OvertimeRequest.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_approved(self, client_a, pending_overtime_a):
        from apps.hrm.models import OvertimeRequest
        client_a.post(reverse("hrm:overtimerequest_approve", args=[pending_overtime_a.pk]))
        pk = pending_overtime_a.pk
        resp = client_a.post(reverse("hrm:overtimerequest_delete", args=[pk]))
        assert resp.status_code == 302
        assert OvertimeRequest.objects.filter(pk=pk).exists()  # not deleted

    def test_delete_requires_post(self, client_a, draft_overtime_a):
        from apps.hrm.models import OvertimeRequest
        resp = client_a.get(reverse("hrm:overtimerequest_delete", args=[draft_overtime_a.pk]))
        assert resp.status_code == 405
        assert OvertimeRequest.objects.filter(pk=draft_overtime_a.pk).exists()


# ============================================================
# OvertimeRequest workflow — authorization (@tenant_admin_required)
# ============================================================
class TestOvertimeRequestWorkflowAuthorization:
    def test_nonadmin_approve_403(self, member_client, pending_overtime_a):
        resp = member_client.post(reverse("hrm:overtimerequest_approve", args=[pending_overtime_a.pk]))
        assert resp.status_code == 403
        pending_overtime_a.refresh_from_db()
        assert pending_overtime_a.status == "pending"

    def test_nonadmin_reject_403(self, member_client, pending_overtime_a):
        resp = member_client.post(reverse("hrm:overtimerequest_reject", args=[pending_overtime_a.pk]))
        assert resp.status_code == 403
        pending_overtime_a.refresh_from_db()
        assert pending_overtime_a.status == "pending"

    def test_admin_approve_succeeds(self, client_a, pending_overtime_a):
        resp = client_a.post(reverse("hrm:overtimerequest_approve", args=[pending_overtime_a.pk]))
        assert resp.status_code == 302
        pending_overtime_a.refresh_from_db()
        assert pending_overtime_a.status == "approved"


# ============================================================
# OvertimeRequest list/detail views
# ============================================================
class TestOvertimeRequestListDetailViews:
    def test_list_ok(self, client_a, pending_overtime_a):
        resp = client_a.get(reverse("hrm:overtimerequest_list"))
        assert resp.status_code == 200
        assert pending_overtime_a.number.encode() in resp.content

    def test_filter_by_status(self, client_a, draft_overtime_a):
        resp = client_a.get(reverse("hrm:overtimerequest_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_overtime_a.pk in pks

    def test_filter_by_payout_method(self, client_a, draft_overtime_a):
        resp = client_a.get(reverse("hrm:overtimerequest_list"), {"payout_method": "pay"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_overtime_a.pk in pks

    def test_create_view_post(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import OvertimeRequest
        resp = client_a.post(reverse("hrm:overtimerequest_create"), {
            "employee": employee_a.pk, "date": "2026-06-05", "hours_claimed": "3",
            "multiplier": "1.5", "payout_method": "pay", "reason": "Deployment support",
        })
        assert resp.status_code == 302
        ot = OvertimeRequest.objects.get(tenant=tenant_a, employee=employee_a)
        assert ot.tenant_id == tenant_a.pk
        assert ot.status == "draft"

    def test_detail_ok(self, client_a, pending_overtime_a):
        resp = client_a.get(reverse("hrm:overtimerequest_detail", args=[pending_overtime_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == pending_overtime_a.pk


# ============================================================
# OvertimeRequestForm
# ============================================================
class TestOvertimeRequestForm:
    def test_required_fields_missing(self, tenant_a):
        from apps.hrm.forms import OvertimeRequestForm
        form = OvertimeRequestForm({}, tenant=tenant_a)
        assert not form.is_valid()
        for f in ("employee", "date", "hours_claimed", "reason"):
            assert f in form.errors

    def test_excludes_workflow_fields(self):
        from apps.hrm.forms import OvertimeRequestForm
        excluded = {"status", "approver", "approved_at", "decision_note", "number", "tenant"}
        assert not (excluded & set(OvertimeRequestForm.Meta.fields))

    def test_timesheet_queryset_scoped_to_tenant(self, tenant_a, draft_timesheet_a, timesheet_b):
        from apps.hrm.forms import OvertimeRequestForm
        form = OvertimeRequestForm(tenant=tenant_a)
        qs = form.fields["timesheet"].queryset
        assert draft_timesheet_a in qs
        assert timesheet_b not in qs


# ============================================================
# Reports — timesheet_utilization_report
# ============================================================
class TestUtilizationReport:
    def test_only_approved_timesheets_counted(self, client_a, tenant_a, employee_a, timesheet_entry_a, draft_timesheet_a):
        """draft_timesheet_a (with timesheet_entry_a) is still draft — must be excluded."""
        resp = client_a.get(reverse("hrm:timesheet_utilization_report"))
        assert resp.status_code == 200
        assert resp.context["rows"] == []

    def test_approved_timesheet_entries_appear(self, client_a, employee_a, timesheet_entry_a, draft_timesheet_a):
        draft_timesheet_a.status = "pending"
        draft_timesheet_a.save(update_fields=["status", "updated_at"])
        client_a.post(reverse("hrm:timesheet_approve", args=[draft_timesheet_a.pk]))
        resp = client_a.get(reverse("hrm:timesheet_utilization_report"))
        rows = resp.context["rows"]
        assert len(rows) == 1
        assert rows[0]["employee"] == employee_a.party.name
        assert rows[0]["total"] == Decimal("8")
        assert rows[0]["billable"] == Decimal("8")
        assert rows[0]["utilization"] == Decimal("100.0")

    def test_partial_billable_utilization_percentage(self, client_a, tenant_a, employee_a, draft_timesheet_a):
        from apps.hrm.models import TimesheetEntry
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 3),
            hours=Decimal("10"), is_billable=True, billable_rate=Decimal("1"),
        )
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 4),
            hours=Decimal("10"), is_billable=False, billable_rate=Decimal("1"),
        )
        draft_timesheet_a.status = "pending"
        draft_timesheet_a.save(update_fields=["status", "updated_at"])
        client_a.post(reverse("hrm:timesheet_approve", args=[draft_timesheet_a.pk]))
        resp = client_a.get(reverse("hrm:timesheet_utilization_report"))
        rows = resp.context["rows"]
        assert rows[0]["total"] == Decimal("20")
        assert rows[0]["billable"] == Decimal("10")
        assert rows[0]["utilization"] == Decimal("50.0")

    def test_date_from_narrows_by_period_start(self, client_a, tenant_a, employee_a, draft_timesheet_a):
        client_a.post(reverse("hrm:timesheet_submit", args=[draft_timesheet_a.pk]))
        client_a.post(reverse("hrm:timesheet_approve", args=[draft_timesheet_a.pk]))
        from apps.hrm.models import TimesheetEntry
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("4"), is_billable=True, billable_rate=Decimal("1"),
        )
        resp = client_a.get(reverse("hrm:timesheet_utilization_report"), {"date_from": "2026-07-01"})
        assert resp.context["rows"] == []  # period_start (06-01) is before the filter

    def test_date_to_narrows_by_period_start(self, client_a, tenant_a, employee_a, draft_timesheet_a):
        client_a.post(reverse("hrm:timesheet_submit", args=[draft_timesheet_a.pk]))
        client_a.post(reverse("hrm:timesheet_approve", args=[draft_timesheet_a.pk]))
        from apps.hrm.models import TimesheetEntry
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("4"), is_billable=True, billable_rate=Decimal("1"),
        )
        resp = client_a.get(reverse("hrm:timesheet_utilization_report"), {"date_to": "2026-05-01"})
        assert resp.context["rows"] == []  # period_start (06-01) is after the filter

    def test_rejected_timesheet_excluded(self, client_a, pending_timesheet_a, tenant_a):
        from apps.hrm.models import TimesheetEntry
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=pending_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("5"), is_billable=True, billable_rate=Decimal("1"),
        )
        client_a.post(reverse("hrm:timesheet_reject", args=[pending_timesheet_a.pk]))
        resp = client_a.get(reverse("hrm:timesheet_utilization_report"))
        assert resp.context["rows"] == []


# ============================================================
# Reports — project_time_report
# ============================================================
class TestProjectTimeReport:
    def test_only_entries_with_project_counted(self, client_a, tenant_a, draft_timesheet_a):
        from apps.hrm.models import TimesheetEntry
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("3"), project=None, is_billable=True, billable_rate=Decimal("1"),
        )
        resp = client_a.get(reverse("hrm:project_time_report"))
        assert resp.status_code == 200
        assert resp.context["rows"] == []

    def test_regression_no_hours_fielderror_and_correct_aggregation(
            self, client_a, timesheet_entry_a, project_a):
        """Regression guard: the view must alias its Sum('hours') aggregates away from the
        `hours` field name (views.py ~1524-1529) — annotating `hours=Sum('hours', ...)` directly
        would shadow the field and raise a FieldError on the second Sum('hours', filter=...).
        Must return 200 with the correct logged/billable totals, not 500."""
        resp = client_a.get(reverse("hrm:project_time_report"))
        assert resp.status_code == 200
        rows = resp.context["rows"]
        assert len(rows) == 1
        assert rows[0]["number"] == project_a.number
        assert rows[0]["name"] == project_a.name
        assert rows[0]["hours"] == Decimal("8")
        assert rows[0]["billable_hours"] == Decimal("8")
        assert rows[0]["budget"] == project_a.budget_amount

    def test_non_billable_entry_excluded_from_billable_hours(self, client_a, tenant_a, draft_timesheet_a, project_a):
        from apps.hrm.models import TimesheetEntry
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("6"), project=project_a, is_billable=False, billable_rate=Decimal("1"),
        )
        resp = client_a.get(reverse("hrm:project_time_report"))
        rows = resp.context["rows"]
        assert rows[0]["hours"] == Decimal("6")
        assert rows[0]["billable_hours"] == Decimal("0")

    def test_date_filter_narrows_by_entry_date(self, client_a, timesheet_entry_a):
        """timesheet_entry_a is dated 2026-06-02."""
        resp = client_a.get(reverse("hrm:project_time_report"), {"date_from": "2026-07-01"})
        assert resp.context["rows"] == []

    def test_date_to_filter_narrows_by_entry_date(self, client_a, timesheet_entry_a):
        resp = client_a.get(reverse("hrm:project_time_report"), {"date_to": "2026-05-01"})
        assert resp.context["rows"] == []

    def test_includes_entries_regardless_of_timesheet_status(self, client_a, tenant_a, draft_timesheet_a, project_a):
        """Unlike the utilization report, project_time_report does not filter by timesheet
        status — a draft timesheet's project-tagged entries still show up here."""
        from apps.hrm.models import TimesheetEntry
        TimesheetEntry.objects.create(
            tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
            hours=Decimal("2"), project=project_a, is_billable=True, billable_rate=Decimal("1"),
        )
        assert draft_timesheet_a.status == "draft"
        resp = client_a.get(reverse("hrm:project_time_report"))
        assert resp.context["rows"][0]["hours"] == Decimal("2")


# ============================================================
# Multi-tenant IDOR sweep
# ============================================================
class TestTimesheetIDOR:
    def test_detail_cross_tenant_404(self, client_a, timesheet_b):
        resp = client_a.get(reverse("hrm:timesheet_detail", args=[timesheet_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, timesheet_b):
        resp = client_a.get(reverse("hrm:timesheet_edit", args=[timesheet_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, timesheet_b):
        resp = client_a.post(reverse("hrm:timesheet_edit", args=[timesheet_b.pk]), {
            "employee": timesheet_b.employee_id, "period_start": "2000-01-01", "period_end": "2000-01-07",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, timesheet_b):
        from apps.hrm.models import Timesheet
        resp = client_a.post(reverse("hrm:timesheet_delete", args=[timesheet_b.pk]))
        assert resp.status_code == 404
        assert Timesheet.objects.filter(pk=timesheet_b.pk).exists()

    def test_submit_cross_tenant_404(self, client_a, timesheet_b):
        resp = client_a.post(reverse("hrm:timesheet_submit", args=[timesheet_b.pk]))
        assert resp.status_code == 404

    def test_approve_cross_tenant_404(self, client_a, timesheet_b):
        resp = client_a.post(reverse("hrm:timesheet_approve", args=[timesheet_b.pk]))
        assert resp.status_code == 404
        timesheet_b.refresh_from_db()
        assert timesheet_b.status == "pending"

    def test_reject_cross_tenant_404(self, client_a, timesheet_b):
        resp = client_a.post(reverse("hrm:timesheet_reject", args=[timesheet_b.pk]))
        assert resp.status_code == 404

    def test_cancel_cross_tenant_404(self, client_a, timesheet_b):
        resp = client_a.post(reverse("hrm:timesheet_cancel", args=[timesheet_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_tenant_b(self, client_a, draft_timesheet_a, timesheet_b):
        resp = client_a.get(reverse("hrm:timesheet_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_timesheet_a.pk in pks
        assert timesheet_b.pk not in pks

    def test_entry_add_cross_tenant_ts_pk_404(self, client_a, timesheet_b):
        resp = client_a.post(
            reverse("hrm:timesheetentry_add", args=[timesheet_b.pk]),
            {"date": "2026-06-02", "hours": "2", "is_billable": "on", "billable_rate": "10"})
        assert resp.status_code == 404
        from apps.hrm.models import TimesheetEntry
        assert TimesheetEntry.objects.filter(timesheet=timesheet_b).count() == 0

    def test_entry_edit_cross_tenant_404(self, client_a, timesheet_entry_b):
        resp = client_a.get(reverse("hrm:timesheetentry_edit", args=[timesheet_entry_b.pk]))
        assert resp.status_code == 404

    def test_entry_edit_post_cross_tenant_404(self, client_a, timesheet_entry_b):
        original_hours = timesheet_entry_b.hours
        resp = client_a.post(
            reverse("hrm:timesheetentry_edit", args=[timesheet_entry_b.pk]),
            {"date": "2026-06-02", "hours": "999", "is_billable": "on", "billable_rate": "10"})
        assert resp.status_code == 404
        timesheet_entry_b.refresh_from_db()
        assert timesheet_entry_b.hours == original_hours

    def test_entry_delete_cross_tenant_404(self, client_a, timesheet_entry_b):
        from apps.hrm.models import TimesheetEntry
        resp = client_a.post(reverse("hrm:timesheetentry_delete", args=[timesheet_entry_b.pk]))
        assert resp.status_code == 404
        assert TimesheetEntry.objects.filter(pk=timesheet_entry_b.pk).exists()


class TestOvertimeRequestIDOR:
    def test_detail_cross_tenant_404(self, client_a, overtime_b):
        resp = client_a.get(reverse("hrm:overtimerequest_detail", args=[overtime_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, overtime_b):
        resp = client_a.get(reverse("hrm:overtimerequest_edit", args=[overtime_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, overtime_b):
        resp = client_a.post(reverse("hrm:overtimerequest_edit", args=[overtime_b.pk]), {
            "employee": overtime_b.employee_id, "date": "2026-06-02", "hours_claimed": "999",
            "multiplier": "1.5", "payout_method": "pay", "reason": "forged",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, overtime_b):
        from apps.hrm.models import OvertimeRequest
        resp = client_a.post(reverse("hrm:overtimerequest_delete", args=[overtime_b.pk]))
        assert resp.status_code == 404
        assert OvertimeRequest.objects.filter(pk=overtime_b.pk).exists()

    def test_submit_cross_tenant_404(self, client_a, overtime_b):
        resp = client_a.post(reverse("hrm:overtimerequest_submit", args=[overtime_b.pk]))
        assert resp.status_code == 404

    def test_approve_cross_tenant_404(self, client_a, overtime_b):
        resp = client_a.post(reverse("hrm:overtimerequest_approve", args=[overtime_b.pk]))
        assert resp.status_code == 404
        overtime_b.refresh_from_db()
        assert overtime_b.status == "pending"

    def test_reject_cross_tenant_404(self, client_a, overtime_b):
        resp = client_a.post(reverse("hrm:overtimerequest_reject", args=[overtime_b.pk]))
        assert resp.status_code == 404

    def test_cancel_cross_tenant_404(self, client_a, overtime_b):
        resp = client_a.post(reverse("hrm:overtimerequest_cancel", args=[overtime_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_tenant_b(self, client_a, draft_overtime_a, overtime_b):
        resp = client_a.get(reverse("hrm:overtimerequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_overtime_a.pk in pks
        assert overtime_b.pk not in pks


# ============================================================
# Anonymous access
# ============================================================
class TestAnonymousBlockedTimeTrackingEndpoints:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:timesheet_list", []),
        ("hrm:timesheet_create", []),
        ("hrm:overtimerequest_list", []),
        ("hrm:overtimerequest_create", []),
        ("hrm:timesheet_utilization_report", []),
        ("hrm:project_time_report", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================
# CSRF enforcement on POST-only endpoints
# ============================================================
class TestCSRFEnforcementTimeTrackingEndpoints:
    def test_delete_enforces_csrf(self, admin_user, draft_timesheet_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:timesheet_delete", args=[draft_timesheet_a.pk]))
        assert resp.status_code == 403

    def test_approve_enforces_csrf(self, admin_user, pending_timesheet_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:timesheet_approve", args=[pending_timesheet_a.pk]))
        assert resp.status_code == 403

    def test_overtime_approve_enforces_csrf(self, admin_user, pending_overtime_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:overtimerequest_approve", args=[pending_overtime_a.pk]))
        assert resp.status_code == 403


# ============================================================
# Performance guards
# ============================================================
class TestTimeTrackingPerformance:
    def test_timesheet_list_query_count_bounded_with_many_rows(
            self, client_a, tenant_a, employee_a, draft_timesheet_a, django_assert_max_num_queries):
        from apps.hrm.models import Timesheet
        for i in range(15):
            Timesheet.objects.create(
                tenant=tenant_a, employee=employee_a,
                period_start=datetime.date(2026, 1, 1) + datetime.timedelta(days=i * 8),
                period_end=datetime.date(2026, 1, 7) + datetime.timedelta(days=i * 8),
            )
        with django_assert_max_num_queries(12):
            resp = client_a.get(reverse("hrm:timesheet_list"))
        assert resp.status_code == 200
        assert len(resp.context["object_list"]) >= 10

    def test_timesheet_detail_query_count_bounded_with_many_entries(
            self, client_a, tenant_a, draft_timesheet_a, project_a, django_assert_max_num_queries):
        """Locks in select_related("project") on the entries queryset (views.py:1220)."""
        from apps.hrm.models import TimesheetEntry
        for i in range(15):
            TimesheetEntry.objects.create(
                tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 1),
                project=project_a, hours=Decimal("1"), is_billable=True, billable_rate=Decimal("10"),
            )
        with django_assert_max_num_queries(10):
            resp = client_a.get(reverse("hrm:timesheet_detail", args=[draft_timesheet_a.pk]))
        assert resp.status_code == 200
        assert len(resp.context["entries"]) >= 10

    def test_utilization_report_query_count_bounded(
            self, client_a, tenant_a, employee_a, draft_timesheet_a, django_assert_max_num_queries):
        from apps.hrm.models import TimesheetEntry
        draft_timesheet_a.status = "pending"
        draft_timesheet_a.save(update_fields=["status", "updated_at"])
        for i in range(20):
            TimesheetEntry.objects.create(
                tenant=tenant_a, timesheet=draft_timesheet_a,
                date=datetime.date(2026, 6, 1) + datetime.timedelta(days=i % 7),
                hours=Decimal("1"), is_billable=(i % 2 == 0), billable_rate=Decimal("10"),
            )
        client_a.post(reverse("hrm:timesheet_approve", args=[draft_timesheet_a.pk]))
        with django_assert_max_num_queries(8):
            resp = client_a.get(reverse("hrm:timesheet_utilization_report"))
        assert resp.status_code == 200

    def test_project_time_report_query_count_bounded(
            self, client_a, tenant_a, draft_timesheet_a, project_a, django_assert_max_num_queries):
        from apps.hrm.models import TimesheetEntry
        for i in range(20):
            TimesheetEntry.objects.create(
                tenant=tenant_a, timesheet=draft_timesheet_a,
                date=datetime.date(2026, 6, 1) + datetime.timedelta(days=i % 7),
                project=project_a, hours=Decimal("1"), is_billable=(i % 2 == 0), billable_rate=Decimal("10"),
            )
        with django_assert_max_num_queries(8):
            resp = client_a.get(reverse("hrm:project_time_report"))
        assert resp.status_code == 200
