"""Tests for CRM sub-module 1.5 — Activity & Communication Management.

Covers:
  - CrmTask (recurrence spawn, idempotency, monthly clamp, recurrence_until guard)
  - CalendarEvent (public_token, is_past, duration_display)
  - EventAttendee (blank-email→NULL, responded_at stamp, RSVP unique_together)
  - CommunicationLog (duration_display, is_call, auto-number COM-)
  - Forms: CalendarEventForm / CommunicationLogForm / CrmTaskForm exclusions
  - Views: CRUD happy paths, list, detail, delete
  - Multi-tenant IDOR (cross-tenant 404)
  - Public pages: event_invite GET/POST/first-response-wins, event_ics content-type + VCALENDAR
"""
import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ===================================================================== Fixtures
@pytest.fixture
def party_a(db, tenant_a):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="organization", name="Acme Client")


@pytest.fixture
def party_b(db, tenant_b):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="organization", name="Globex Client")


@pytest.fixture
def event_a(db, tenant_a):
    from apps.crm.models import CalendarEvent
    start = timezone.now() + datetime.timedelta(hours=2)
    end = start + datetime.timedelta(hours=1)
    return CalendarEvent.objects.create(
        tenant=tenant_a,
        title="Acme Planning Meeting",
        event_type="meeting",
        start=start,
        end=end,
        status="scheduled",
    )


@pytest.fixture
def event_b(db, tenant_b):
    from apps.crm.models import CalendarEvent
    start = timezone.now() + datetime.timedelta(hours=3)
    return CalendarEvent.objects.create(
        tenant=tenant_b,
        title="Globex Kick-off",
        event_type="meeting",
        start=start,
        status="scheduled",
    )


@pytest.fixture
def comm_a(db, tenant_a):
    from apps.crm.models import CommunicationLog
    return CommunicationLog.objects.create(
        tenant=tenant_a,
        channel="call",
        direction="outbound",
        subject="Intro call",
        duration_seconds=125,
        outcome="connected",
    )


@pytest.fixture
def comm_b(db, tenant_b):
    from apps.crm.models import CommunicationLog
    return CommunicationLog.objects.create(
        tenant=tenant_b,
        channel="email",
        direction="inbound",
        subject="Globex inquiry",
    )


@pytest.fixture
def recurring_task(db, tenant_a):
    """A daily-recurring task with a known due_date for spawn tests."""
    from apps.crm.models import CrmTask
    due = timezone.localdate() + datetime.timedelta(days=1)
    return CrmTask.objects.create(
        tenant=tenant_a,
        subject="Daily stand-up",
        type="todo",
        priority="medium",
        status="open",
        due_date=due,
        recurrence="daily",
        recurrence_interval=1,
    )


@pytest.fixture
def weekly_task(db, tenant_a):
    from apps.crm.models import CrmTask
    due = timezone.localdate() + datetime.timedelta(days=7)
    return CrmTask.objects.create(
        tenant=tenant_a,
        subject="Weekly review",
        status="open",
        due_date=due,
        recurrence="weekly",
        recurrence_interval=1,
    )


@pytest.fixture
def monthly_task_jan31(db, tenant_a):
    """Task due on Jan 31 for monthly-clamp tests."""
    from apps.crm.models import CrmTask
    due = datetime.date(2026, 1, 31)
    return CrmTask.objects.create(
        tenant=tenant_a,
        subject="End-of-month report",
        status="open",
        due_date=due,
        recurrence="monthly",
        recurrence_interval=1,
    )


# ==================================================================== CrmTask — Recurrence Spawn

class TestCrmTaskRecurrenceSpawn:
    """Verify that completing a recurring task spawns exactly one open child."""

    def test_completing_daily_task_spawns_one_child(self, recurring_task):
        from apps.crm.models import CrmTask
        recurring_task.status = "done"
        recurring_task.save()
        children = CrmTask.objects.filter(recurrence_parent=recurring_task)
        assert children.count() == 1

    def test_spawned_child_is_open(self, recurring_task):
        from apps.crm.models import CrmTask
        recurring_task.status = "done"
        recurring_task.save()
        child = CrmTask.objects.get(recurrence_parent=recurring_task)
        assert child.status == "open"

    def test_spawned_child_due_date_advanced_by_interval(self, recurring_task):
        from apps.crm.models import CrmTask
        original_due = recurring_task.due_date
        recurring_task.status = "done"
        recurring_task.save()
        child = CrmTask.objects.get(recurrence_parent=recurring_task)
        assert child.due_date == original_due + datetime.timedelta(days=1)

    def test_spawned_child_inherits_subject(self, recurring_task):
        from apps.crm.models import CrmTask
        recurring_task.status = "done"
        recurring_task.save()
        child = CrmTask.objects.get(recurrence_parent=recurring_task)
        assert child.subject == recurring_task.subject

    def test_spawned_child_inherits_recurrence_settings(self, recurring_task):
        from apps.crm.models import CrmTask
        recurring_task.status = "done"
        recurring_task.save()
        child = CrmTask.objects.get(recurrence_parent=recurring_task)
        assert child.recurrence == "daily"
        assert child.recurrence_interval == 1

    def test_non_recurring_task_spawns_nothing(self, tenant_a):
        from apps.crm.models import CrmTask
        t = CrmTask.objects.create(
            tenant=tenant_a,
            subject="One-off task",
            status="open",
            due_date=timezone.localdate() + datetime.timedelta(days=1),
            recurrence="none",
        )
        t.status = "done"
        t.save()
        assert CrmTask.objects.filter(recurrence_parent=t).count() == 0

    def test_non_recurring_task_no_due_date_spawns_nothing(self, tenant_a):
        from apps.crm.models import CrmTask
        t = CrmTask.objects.create(
            tenant=tenant_a,
            subject="No due date recurring",
            status="open",
            recurrence="daily",
        )
        t.status = "done"
        t.save()
        # recurrence is set but no due_date → no spawn (guard in save())
        assert CrmTask.objects.filter(recurrence_parent=t).count() == 0

    def test_idempotency_no_double_spawn_on_resave(self, recurring_task):
        """Re-saving an already-done recurring task must NOT spawn a second child."""
        from apps.crm.models import CrmTask
        recurring_task.status = "done"
        recurring_task.save()
        # Re-save the done task (e.g. priority change)
        recurring_task.priority = "low"
        recurring_task.save()
        children = CrmTask.objects.filter(recurrence_parent=recurring_task)
        assert children.count() == 1

    def test_recurrence_until_stops_spawn(self, tenant_a):
        """Task whose next due exceeds recurrence_until must NOT spawn."""
        from apps.crm.models import CrmTask
        today = timezone.localdate()
        t = CrmTask.objects.create(
            tenant=tenant_a,
            subject="Short series",
            status="open",
            due_date=today,
            recurrence="daily",
            recurrence_interval=1,
            recurrence_until=today,  # today is the last allowed; next = today+1 > today
        )
        t.status = "done"
        t.save()
        assert CrmTask.objects.filter(recurrence_parent=t).count() == 0

    def test_recurrence_until_allows_spawn_when_in_range(self, tenant_a):
        """Next due still within recurrence_until → spawn happens."""
        from apps.crm.models import CrmTask
        today = timezone.localdate()
        future = today + datetime.timedelta(days=30)
        t = CrmTask.objects.create(
            tenant=tenant_a,
            subject="Long series",
            status="open",
            due_date=today,
            recurrence="daily",
            recurrence_interval=1,
            recurrence_until=future,
        )
        t.status = "done"
        t.save()
        assert CrmTask.objects.filter(recurrence_parent=t).count() == 1

    def test_weekly_task_due_date_advanced_by_7_days(self, weekly_task):
        from apps.crm.models import CrmTask
        original_due = weekly_task.due_date
        weekly_task.status = "done"
        weekly_task.save()
        child = CrmTask.objects.get(recurrence_parent=weekly_task)
        assert child.due_date == original_due + datetime.timedelta(weeks=1)

    def test_spawn_uses_origin_as_parent_not_grandparent(self, recurring_task):
        """The recurrence_parent of the child of a child should be the series origin."""
        from apps.crm.models import CrmTask
        # Complete the original task
        recurring_task.status = "done"
        recurring_task.save()
        child = CrmTask.objects.get(recurrence_parent=recurring_task)
        # Complete the child (first spawned occurrence)
        child.status = "done"
        child.save()
        # The grandchild's parent should still be the original (origin) task
        grandchildren = CrmTask.objects.filter(recurrence_parent=recurring_task).exclude(pk=child.pk)
        assert grandchildren.count() == 1

    def test_idempotency_guard_prevents_duplicate_occurrence(self, recurring_task):
        """If a child with the same due_date already exists, no second child is created."""
        from apps.crm.models import CrmTask
        # Manually pre-create a child at the next due date
        next_due = recurring_task.due_date + datetime.timedelta(days=1)
        CrmTask.objects.create(
            tenant=recurring_task.tenant,
            subject=recurring_task.subject,
            status="open",
            due_date=next_due,
            recurrence="daily",
            recurrence_interval=1,
            recurrence_parent=recurring_task,
        )
        # Now complete the parent
        recurring_task.status = "done"
        recurring_task.save()
        # Still only one child (the pre-created one; no duplicate spawned)
        children = CrmTask.objects.filter(recurrence_parent=recurring_task)
        assert children.count() == 1


class TestCrmTaskMonthlyClamp:
    """Verify month-end clamping for monthly recurrence (Jan 31 → Feb 28)."""

    def test_jan31_monthly_spawns_feb28(self, monthly_task_jan31):
        from apps.crm.models import CrmTask
        monthly_task_jan31.status = "done"
        monthly_task_jan31.save()
        child = CrmTask.objects.get(recurrence_parent=monthly_task_jan31)
        # Jan 31 + 1 month → Feb 28 (2026 is not a leap year)
        assert child.due_date == datetime.date(2026, 2, 28)

    def test_monthly_drift_on_subsequent_spawn(self, monthly_task_jan31):
        """Document known last-day drift: Feb 28 + 1 month → Mar 28 (not Mar 31).

        The algorithm clamps day to month-end at spawn time, so after Feb 28 the
        day is already reduced to 28 and subsequent spawns advance from day=28, not
        the original day=31. This is the current model behavior — assert it, not fix it.
        """
        from apps.crm.models import CrmTask
        # Spawn: Jan 31 → Feb 28
        monthly_task_jan31.status = "done"
        monthly_task_jan31.save()
        child = CrmTask.objects.get(recurrence_parent=monthly_task_jan31)
        assert child.due_date == datetime.date(2026, 2, 28)  # clamped

        # Second spawn: Feb 28 → Mar 28 (drift — March has 31 days but we start from day=28)
        child.status = "done"
        child.save()
        grandchild = CrmTask.objects.filter(recurrence_parent=monthly_task_jan31).exclude(pk=child.pk).first()
        assert grandchild is not None
        # Current behavior: Mar 28 (drift from Feb 28), NOT Mar 31.
        assert grandchild.due_date == datetime.date(2026, 3, 28)

    def test_monthly_clamp_to_feb_leap_year(self, tenant_a):
        """Jan 31, 2028 (leap year) + 1 month → Feb 29 (29 days in leap Feb)."""
        from apps.crm.models import CrmTask
        t = CrmTask.objects.create(
            tenant=tenant_a,
            subject="Leap year clamp",
            status="open",
            due_date=datetime.date(2028, 1, 31),
            recurrence="monthly",
            recurrence_interval=1,
        )
        t.status = "done"
        t.save()
        child = CrmTask.objects.get(recurrence_parent=t)
        assert child.due_date == datetime.date(2028, 2, 29)

    def test_monthly_interval_2(self, tenant_a):
        """Every-2-months: Jan 31 → Mar 31 (no clamp needed)."""
        from apps.crm.models import CrmTask
        t = CrmTask.objects.create(
            tenant=tenant_a,
            subject="Bi-monthly",
            status="open",
            due_date=datetime.date(2026, 1, 31),
            recurrence="monthly",
            recurrence_interval=2,
        )
        t.status = "done"
        t.save()
        child = CrmTask.objects.get(recurrence_parent=t)
        assert child.due_date == datetime.date(2026, 3, 31)


# ==================================================================== CalendarEvent — Model

class TestCalendarEventModel:
    def test_str(self, event_a):
        assert "EVT-00001" in str(event_a)
        assert "Acme Planning Meeting" in str(event_a)

    def test_auto_number_format(self, event_a):
        assert event_a.number.startswith("EVT-")
        assert len(event_a.number) > 4

    def test_public_token_auto_set_on_save(self, event_a):
        assert event_a.public_token
        assert len(event_a.public_token) >= 40

    def test_public_token_unique_per_event(self, tenant_a):
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=1)
        e1 = CalendarEvent.objects.create(tenant=tenant_a, title="E1", start=start)
        e2 = CalendarEvent.objects.create(tenant=tenant_a, title="E2", start=start)
        assert e1.public_token != e2.public_token

    def test_public_token_not_overwritten_on_resave(self, event_a):
        original = event_a.public_token
        event_a.title = "Updated Title"
        event_a.save()
        event_a.refresh_from_db()
        assert event_a.public_token == original

    def test_is_past_true_for_past_start(self, tenant_a):
        from apps.crm.models import CalendarEvent
        past_start = timezone.now() - datetime.timedelta(hours=2)
        e = CalendarEvent.objects.create(tenant=tenant_a, title="Past event", start=past_start)
        assert e.is_past is True

    def test_is_past_false_for_future_start(self, event_a):
        assert event_a.is_past is False

    def test_duration_display_h_mm(self, tenant_a):
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=1)
        end = start + datetime.timedelta(hours=1, minutes=30)
        e = CalendarEvent.objects.create(tenant=tenant_a, title="Long meeting", start=start, end=end)
        assert e.duration_display == "1:30"

    def test_duration_display_zero_minutes(self, tenant_a):
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=1)
        end = start + datetime.timedelta(hours=2)
        e = CalendarEvent.objects.create(tenant=tenant_a, title="Two hour", start=start, end=end)
        assert e.duration_display == "2:00"

    def test_duration_display_empty_when_no_end(self, tenant_a):
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=1)
        e = CalendarEvent.objects.create(tenant=tenant_a, title="No end", start=start)
        assert e.duration_display == ""

    def test_duration_display_empty_when_end_equals_start(self, tenant_a):
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=1)
        e = CalendarEvent.objects.create(tenant=tenant_a, title="Zero dur", start=start, end=start)
        assert e.duration_display == ""

    def test_status_choices(self):
        from apps.crm.models import CalendarEvent
        keys = [k for k, _ in CalendarEvent.STATUS_CHOICES]
        for expected in ("scheduled", "confirmed", "cancelled", "completed"):
            assert expected in keys

    def test_type_choices(self):
        from apps.crm.models import CalendarEvent
        keys = [k for k, _ in CalendarEvent.TYPE_CHOICES]
        for expected in ("meeting", "call", "demo", "deadline", "reminder", "other"):
            assert expected in keys

    def test_unique_together_tenant_number(self, tenant_a, event_a):
        from apps.crm.models import CalendarEvent
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            CalendarEvent.objects.create(
                tenant=tenant_a,
                title="Dup",
                start=timezone.now(),
                number="EVT-00001",
            )


# ==================================================================== EventAttendee — Model

class TestEventAttendeeModel:
    def test_blank_email_stored_as_null(self, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        att = EventAttendee.objects.create(
            tenant=tenant_a, event=event_a,
            name="Alice", email="",
        )
        att.refresh_from_db()
        assert att.email is None

    def test_two_blank_email_attendees_on_same_event_coexist(self, event_a, tenant_a):
        """Two attendees with no email on the same event must NOT violate unique_together."""
        from apps.crm.models import EventAttendee
        a1 = EventAttendee.objects.create(tenant=tenant_a, event=event_a, name="Alice", email="")
        a2 = EventAttendee.objects.create(tenant=tenant_a, event=event_a, name="Bob", email="")
        a1.refresh_from_db()
        a2.refresh_from_db()
        assert a1.email is None
        assert a2.email is None
        assert a1.pk != a2.pk

    def test_responded_at_stamped_on_accepted(self, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        att = EventAttendee.objects.create(
            tenant=tenant_a, event=event_a,
            name="Bob", email="bob@example.com",
            rsvp_status="accepted",
        )
        att.refresh_from_db()
        assert att.responded_at is not None

    def test_responded_at_stamped_on_declined(self, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        att = EventAttendee.objects.create(
            tenant=tenant_a, event=event_a,
            name="Carol", email="carol@example.com",
            rsvp_status="declined",
        )
        att.refresh_from_db()
        assert att.responded_at is not None

    def test_responded_at_null_when_no_response(self, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        att = EventAttendee.objects.create(
            tenant=tenant_a, event=event_a,
            name="Dave", email="dave@example.com",
            rsvp_status="no_response",
        )
        att.refresh_from_db()
        assert att.responded_at is None

    def test_responded_at_not_overwritten_on_resave(self, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        att = EventAttendee.objects.create(
            tenant=tenant_a, event=event_a,
            name="Eve", email="eve@example.com",
            rsvp_status="accepted",
        )
        att.refresh_from_db()
        first_stamp = att.responded_at
        att.name = "Eve Updated"
        att.save()
        att.refresh_from_db()
        assert att.responded_at == first_stamp

    def test_str(self, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        att = EventAttendee.objects.create(
            tenant=tenant_a, event=event_a, name="Frank",
            rsvp_status="no_response",
        )
        assert "Frank" in str(att)

    def test_unique_together_event_email(self, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        from django.db import IntegrityError
        EventAttendee.objects.create(
            tenant=tenant_a, event=event_a,
            name="Grace", email="grace@example.com",
        )
        with pytest.raises(IntegrityError):
            EventAttendee.objects.create(
                tenant=tenant_a, event=event_a,
                name="Grace Again", email="grace@example.com",
            )

    def test_rsvp_choices(self):
        from apps.crm.models import EventAttendee
        keys = [k for k, _ in EventAttendee.RSVP_CHOICES]
        for expected in ("no_response", "accepted", "declined", "tentative"):
            assert expected in keys


# ==================================================================== CommunicationLog — Model

class TestCommunicationLogModel:
    def test_str(self, comm_a):
        assert "COM-00001" in str(comm_a)
        assert "Call" in str(comm_a)

    def test_auto_number_format(self, comm_a):
        assert comm_a.number.startswith("COM-")

    def test_duration_display_mm_ss(self, comm_a):
        # 125 seconds = 2 minutes 5 seconds
        assert comm_a.duration_display == "2:05"

    def test_duration_display_zero_seconds(self, tenant_a):
        from apps.crm.models import CommunicationLog
        log = CommunicationLog.objects.create(
            tenant=tenant_a, channel="call", duration_seconds=0
        )
        assert log.duration_display == "0:00"

    def test_duration_display_large_value(self, tenant_a):
        from apps.crm.models import CommunicationLog
        # 3661 seconds = 61 minutes 1 second → "61:01"
        log = CommunicationLog.objects.create(
            tenant=tenant_a, channel="call", duration_seconds=3661
        )
        assert log.duration_display == "61:01"

    def test_duration_display_empty_when_none(self, tenant_a):
        from apps.crm.models import CommunicationLog
        log = CommunicationLog.objects.create(
            tenant=tenant_a, channel="email", duration_seconds=None
        )
        assert log.duration_display == ""

    def test_is_call_true_for_call_channel(self, comm_a):
        assert comm_a.is_call is True

    def test_is_call_false_for_email_channel(self, comm_b):
        assert comm_b.is_call is False

    def test_is_call_false_for_other_channels(self, tenant_a):
        from apps.crm.models import CommunicationLog
        for channel in ("email", "sms", "note", "meeting"):
            log = CommunicationLog.objects.create(tenant=tenant_a, channel=channel)
            assert log.is_call is False, f"Expected is_call=False for channel={channel}"

    def test_channel_choices(self):
        from apps.crm.models import CommunicationLog
        keys = [k for k, _ in CommunicationLog.CHANNEL_CHOICES]
        for expected in ("call", "email", "sms", "note", "meeting"):
            assert expected in keys

    def test_unique_together_tenant_number(self, tenant_a, comm_a):
        from apps.crm.models import CommunicationLog
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            CommunicationLog.objects.create(
                tenant=tenant_a, channel="call", number="COM-00001"
            )

    def test_per_tenant_number_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import CommunicationLog
        la = CommunicationLog.objects.create(tenant=tenant_a, channel="call")
        lb = CommunicationLog.objects.create(tenant=tenant_b, channel="email")
        assert la.number == "COM-00001"
        assert lb.number == "COM-00001"


# ==================================================================== Forms — System Field Exclusions

class TestCalendarEventFormExclusions:
    def test_public_token_not_in_fields(self, tenant_a):
        from apps.crm.forms import CalendarEventForm
        form = CalendarEventForm(tenant=tenant_a)
        assert "public_token" not in form.fields

    def test_number_not_in_fields(self, tenant_a):
        from apps.crm.forms import CalendarEventForm
        form = CalendarEventForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import CalendarEventForm
        form = CalendarEventForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_created_at_not_in_fields(self, tenant_a):
        from apps.crm.forms import CalendarEventForm
        form = CalendarEventForm(tenant=tenant_a)
        assert "created_at" not in form.fields

    def test_form_valid_with_minimal_data(self, tenant_a):
        from apps.crm.forms import CalendarEventForm
        start = timezone.now() + datetime.timedelta(hours=1)
        data = {
            "title": "Quick meeting",
            "event_type": "meeting",
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "all_day": False,
            "status": "scheduled",
            "sync_source": "manual",
        }
        form = CalendarEventForm(data, tenant=tenant_a)
        assert form.is_valid(), form.errors


class TestCommunicationLogFormExclusions:
    def test_number_not_in_fields(self, tenant_a):
        from apps.crm.forms import CommunicationLogForm
        form = CommunicationLogForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import CommunicationLogForm
        form = CommunicationLogForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_email_message_id_not_in_fields(self, tenant_a):
        """email_message_id is sync-engine only, not a user form field."""
        from apps.crm.forms import CommunicationLogForm
        form = CommunicationLogForm(tenant=tenant_a)
        assert "email_message_id" not in form.fields

    def test_created_at_not_in_fields(self, tenant_a):
        from apps.crm.forms import CommunicationLogForm
        form = CommunicationLogForm(tenant=tenant_a)
        assert "created_at" not in form.fields


class TestCrmTaskFormExclusionsActivity:
    def test_recurrence_parent_not_in_fields(self, tenant_a):
        """recurrence_parent is system-set on spawn — must not appear in user form."""
        from apps.crm.forms import CrmTaskForm
        form = CrmTaskForm(tenant=tenant_a)
        assert "recurrence_parent" not in form.fields

    def test_completed_at_not_in_fields(self, tenant_a):
        from apps.crm.forms import CrmTaskForm
        form = CrmTaskForm(tenant=tenant_a)
        assert "completed_at" not in form.fields

    def test_recurrence_defaults_to_none_when_blank(self, tenant_a):
        """clean_recurrence() coerces blank submission to 'none'."""
        from apps.crm.forms import CrmTaskForm
        start = timezone.localdate() + datetime.timedelta(days=1)
        data = {
            "subject": "Simple task",
            "type": "todo",
            "priority": "medium",
            "status": "open",
            "due_date": start.strftime("%Y-%m-%d"),
            "recurrence": "",          # blank — should default to 'none'
            "recurrence_interval": "",  # blank — should default to 1
        }
        form = CrmTaskForm(data, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["recurrence"] == "none"
        assert form.cleaned_data["recurrence_interval"] == 1

    def test_form_valid_without_recurrence_fields(self, tenant_a):
        """A valid task form with NO recurrence fields at all should still be valid."""
        from apps.crm.forms import CrmTaskForm
        data = {
            "subject": "Bare minimum task",
            "type": "todo",
            "priority": "medium",
            "status": "open",
        }
        form = CrmTaskForm(data, tenant=tenant_a)
        assert form.is_valid(), form.errors


# ==================================================================== Views — CalendarEvent CRUD

class TestCalendarEventListView:
    def test_list_200(self, client_a, event_a):
        resp = client_a.get(reverse("crm:calendarevent_list"))
        assert resp.status_code == 200

    def test_list_shows_own_event(self, client_a, event_a):
        resp = client_a.get(reverse("crm:calendarevent_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert event_a.pk in pks

    def test_list_excludes_other_tenant_event(self, client_a, event_a, event_b):
        resp = client_a.get(reverse("crm:calendarevent_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert event_b.pk not in pks

    def test_context_has_status_choices(self, client_a):
        resp = client_a.get(reverse("crm:calendarevent_list"))
        assert "status_choices" in resp.context

    def test_context_has_type_choices(self, client_a):
        resp = client_a.get(reverse("crm:calendarevent_list"))
        assert "type_choices" in resp.context

    def test_anon_redirects(self, client):
        resp = client.get(reverse("crm:calendarevent_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_search_filters_by_title(self, client_a, event_a, tenant_a):
        from apps.crm.models import CalendarEvent
        CalendarEvent.objects.create(
            tenant=tenant_a, title="Unrelated", start=timezone.now() + datetime.timedelta(hours=5)
        )
        resp = client_a.get(reverse("crm:calendarevent_list") + "?q=Acme")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert event_a.pk in pks


class TestCalendarEventCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:calendarevent_create"))
        assert resp.status_code == 200

    def test_post_creates_event_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=3)
        resp = client_a.post(reverse("crm:calendarevent_create"), {
            "title": "New Event",
            "event_type": "meeting",
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "all_day": False,
            "status": "scheduled",
            "sync_source": "manual",
        })
        assert resp.status_code == 302
        event = CalendarEvent.objects.filter(tenant=tenant_a, title="New Event").first()
        assert event is not None
        assert event.number.startswith("EVT-")

    def test_post_auto_assigns_public_token(self, client_a, tenant_a):
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=3)
        client_a.post(reverse("crm:calendarevent_create"), {
            "title": "Token Event",
            "event_type": "meeting",
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "scheduled",
            "sync_source": "manual",
        })
        event = CalendarEvent.objects.filter(tenant=tenant_a, title="Token Event").first()
        assert event is not None
        assert event.public_token  # non-empty
        assert len(event.public_token) >= 40

    def test_anon_redirects(self, client):
        resp = client.post(reverse("crm:calendarevent_create"), {})
        assert resp.status_code == 302


class TestCalendarEventDetailView:
    def test_detail_200(self, client_a, event_a):
        resp = client_a.get(reverse("crm:calendarevent_detail", args=[event_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj_context(self, client_a, event_a):
        resp = client_a.get(reverse("crm:calendarevent_detail", args=[event_a.pk]))
        assert resp.context["obj"].pk == event_a.pk

    def test_detail_has_attendees_context(self, client_a, event_a):
        resp = client_a.get(reverse("crm:calendarevent_detail", args=[event_a.pk]))
        assert "attendees" in resp.context

    def test_detail_has_attendee_form_context(self, client_a, event_a):
        resp = client_a.get(reverse("crm:calendarevent_detail", args=[event_a.pk]))
        assert "attendee_form" in resp.context

    def test_anon_redirects(self, client, event_a):
        resp = client.get(reverse("crm:calendarevent_detail", args=[event_a.pk]))
        assert resp.status_code == 302


class TestCalendarEventEditView:
    def test_get_200(self, client_a, event_a):
        resp = client_a.get(reverse("crm:calendarevent_edit", args=[event_a.pk]))
        assert resp.status_code == 200

    def test_post_updates_event(self, client_a, event_a):
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=4)
        resp = client_a.post(reverse("crm:calendarevent_edit", args=[event_a.pk]), {
            "title": "Renamed Meeting",
            "event_type": "demo",
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "confirmed",
            "sync_source": "manual",
        })
        assert resp.status_code == 302
        event_a.refresh_from_db()
        assert event_a.title == "Renamed Meeting"
        assert event_a.status == "confirmed"


class TestCalendarEventDeleteView:
    def test_post_deletes_event(self, client_a, event_a):
        from apps.crm.models import CalendarEvent
        pk = event_a.pk
        resp = client_a.post(reverse("crm:calendarevent_delete", args=[pk]))
        assert resp.status_code == 302
        assert not CalendarEvent.objects.filter(pk=pk).exists()

    def test_anon_redirects(self, client, event_a):
        resp = client.post(reverse("crm:calendarevent_delete", args=[event_a.pk]))
        assert resp.status_code == 302


# ==================================================================== Views — CommunicationLog CRUD

class TestCommunicationLogListView:
    def test_list_200(self, client_a, comm_a):
        resp = client_a.get(reverse("crm:communicationlog_list"))
        assert resp.status_code == 200

    def test_list_shows_own_log(self, client_a, comm_a):
        resp = client_a.get(reverse("crm:communicationlog_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert comm_a.pk in pks

    def test_list_excludes_other_tenant_log(self, client_a, comm_a, comm_b):
        resp = client_a.get(reverse("crm:communicationlog_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert comm_b.pk not in pks

    def test_context_has_channel_choices(self, client_a):
        resp = client_a.get(reverse("crm:communicationlog_list"))
        assert "channel_choices" in resp.context

    def test_anon_redirects(self, client):
        resp = client.get(reverse("crm:communicationlog_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestCommunicationLogCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:communicationlog_create"))
        assert resp.status_code == 200

    def test_post_creates_log_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import CommunicationLog
        now = timezone.now()
        resp = client_a.post(reverse("crm:communicationlog_create"), {
            "channel": "call",
            "direction": "outbound",
            "subject": "Test call log",
            "occurred_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "logged_via": "manual",
        })
        assert resp.status_code == 302
        log = CommunicationLog.objects.filter(tenant=tenant_a, subject="Test call log").first()
        assert log is not None
        assert log.number.startswith("COM-")

    def test_anon_redirects(self, client):
        resp = client.post(reverse("crm:communicationlog_create"), {})
        assert resp.status_code == 302


class TestCommunicationLogDetailView:
    def test_detail_200(self, client_a, comm_a):
        resp = client_a.get(reverse("crm:communicationlog_detail", args=[comm_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj_context(self, client_a, comm_a):
        resp = client_a.get(reverse("crm:communicationlog_detail", args=[comm_a.pk]))
        assert resp.context["obj"].pk == comm_a.pk

    def test_anon_redirects(self, client, comm_a):
        resp = client.get(reverse("crm:communicationlog_detail", args=[comm_a.pk]))
        assert resp.status_code == 302


class TestCommunicationLogEditView:
    def test_get_200(self, client_a, comm_a):
        resp = client_a.get(reverse("crm:communicationlog_edit", args=[comm_a.pk]))
        assert resp.status_code == 200

    def test_post_updates_log(self, client_a, comm_a):
        now = timezone.now()
        resp = client_a.post(reverse("crm:communicationlog_edit", args=[comm_a.pk]), {
            "channel": "email",
            "direction": "inbound",
            "subject": "Updated subject",
            "occurred_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "logged_via": "manual",
        })
        assert resp.status_code == 302
        comm_a.refresh_from_db()
        assert comm_a.subject == "Updated subject"
        assert comm_a.channel == "email"


class TestCommunicationLogDeleteView:
    def test_post_deletes_log(self, client_a, comm_a):
        from apps.crm.models import CommunicationLog
        pk = comm_a.pk
        resp = client_a.post(reverse("crm:communicationlog_delete", args=[pk]))
        assert resp.status_code == 302
        assert not CommunicationLog.objects.filter(pk=pk).exists()

    def test_anon_redirects(self, client, comm_a):
        resp = client.post(reverse("crm:communicationlog_delete", args=[comm_a.pk]))
        assert resp.status_code == 302


# ==================================================================== Multi-Tenant IDOR

class TestCalendarEventIDOR:
    def test_detail_cross_tenant_404(self, client_a, event_b):
        resp = client_a.get(reverse("crm:calendarevent_detail", args=[event_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, event_b):
        resp = client_a.get(reverse("crm:calendarevent_edit", args=[event_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, event_b):
        start = timezone.now() + datetime.timedelta(hours=1)
        resp = client_a.post(reverse("crm:calendarevent_edit", args=[event_b.pk]), {
            "title": "Hijacked",
            "event_type": "meeting",
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "scheduled",
            "sync_source": "manual",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, event_b):
        resp = client_a.post(reverse("crm:calendarevent_delete", args=[event_b.pk]))
        assert resp.status_code == 404

    def test_list_never_contains_other_tenant_events(self, client_a, event_a, event_b):
        resp = client_a.get(reverse("crm:calendarevent_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert event_b.pk not in pks


class TestCommunicationLogIDOR:
    def test_detail_cross_tenant_404(self, client_a, comm_b):
        resp = client_a.get(reverse("crm:communicationlog_detail", args=[comm_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, comm_b):
        resp = client_a.get(reverse("crm:communicationlog_edit", args=[comm_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, comm_b):
        now = timezone.now()
        resp = client_a.post(reverse("crm:communicationlog_edit", args=[comm_b.pk]), {
            "channel": "call",
            "direction": "inbound",
            "subject": "Hijacked",
            "occurred_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "logged_via": "manual",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, comm_b):
        resp = client_a.post(reverse("crm:communicationlog_delete", args=[comm_b.pk]))
        assert resp.status_code == 404

    def test_list_never_contains_other_tenant_logs(self, client_a, comm_a, comm_b):
        resp = client_a.get(reverse("crm:communicationlog_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert comm_b.pk not in pks


# ==================================================================== Auth Enforcement

class TestActivityAuthEnforcement:
    @pytest.mark.parametrize("url_name", [
        "crm:calendarevent_list",
        "crm:communicationlog_list",
    ])
    def test_anon_redirected_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ==================================================================== CSRF Enforcement

class TestActivityCSRF:
    def test_calendarevent_delete_enforces_csrf(self, admin_user, event_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:calendarevent_delete", args=[event_a.pk]))
        assert resp.status_code == 403

    def test_communicationlog_delete_enforces_csrf(self, admin_user, comm_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:communicationlog_delete", args=[comm_a.pk]))
        assert resp.status_code == 403


# ==================================================================== Public Pages — event_invite

class TestEventInvitePublicView:
    def test_get_by_token_200(self, event_a, client):
        """Unauthenticated GET by public_token returns 200."""
        resp = client.get(reverse("crm:event_invite", args=[event_a.public_token]))
        assert resp.status_code == 200

    def test_invalid_token_404(self, client):
        resp = client.get(reverse("crm:event_invite", args=["this-token-does-not-exist"]))
        assert resp.status_code == 404

    def test_post_rsvp_creates_attendee(self, event_a, client):
        from apps.crm.models import EventAttendee
        resp = client.post(reverse("crm:event_invite", args=[event_a.public_token]), {
            "name": "New Attendee",
            "email": "attendee@example.com",
            "rsvp_status": "accepted",
        })
        # Redirects back to the invite page after RSVP
        assert resp.status_code == 302
        att = EventAttendee.objects.filter(event=event_a, email="attendee@example.com").first()
        assert att is not None
        assert att.rsvp_status == "accepted"

    def test_post_rsvp_stamps_responded_at(self, event_a, client):
        from apps.crm.models import EventAttendee
        client.post(reverse("crm:event_invite", args=[event_a.public_token]), {
            "name": "Respondee",
            "email": "respondee@example.com",
            "rsvp_status": "tentative",
        })
        att = EventAttendee.objects.filter(event=event_a, email="respondee@example.com").first()
        assert att is not None
        assert att.responded_at is not None

    def test_first_response_wins_second_post_does_not_overwrite(self, event_a, client):
        """Security: a second RSVP with the same email must NOT overwrite the first response."""
        from apps.crm.models import EventAttendee
        # First response: accepted
        client.post(reverse("crm:event_invite", args=[event_a.public_token]), {
            "name": "First",
            "email": "first@example.com",
            "rsvp_status": "accepted",
        })
        att = EventAttendee.objects.get(event=event_a, email="first@example.com")
        assert att.rsvp_status == "accepted"

        # Second POST (attacker or re-submission): tries to change to declined
        client.post(reverse("crm:event_invite", args=[event_a.public_token]), {
            "name": "Second",
            "email": "first@example.com",
            "rsvp_status": "declined",
        })
        att.refresh_from_db()
        # Must still be "accepted" — first response wins
        assert att.rsvp_status == "accepted"

    def test_first_response_no_response_can_be_overwritten(self, event_a, client):
        """An attendee at 'no_response' has not yet responded, so a POST may set their status."""
        from apps.crm.models import EventAttendee
        # Create an attendee at no_response (the default / invite state)
        from apps.crm.models import EventAttendee
        EventAttendee.objects.create(
            tenant=event_a.tenant,
            event=event_a,
            name="Pending",
            email="pending@example.com",
            rsvp_status="no_response",
        )
        # RSVP via public page
        client.post(reverse("crm:event_invite", args=[event_a.public_token]), {
            "name": "Pending",
            "email": "pending@example.com",
            "rsvp_status": "accepted",
        })
        att = EventAttendee.objects.get(event=event_a, email="pending@example.com")
        assert att.rsvp_status == "accepted"

    def test_event_and_attendees_in_context(self, event_a, client):
        resp = client.get(reverse("crm:event_invite", args=[event_a.public_token]))
        assert "event" in resp.context
        assert "attendees" in resp.context
        assert "form" in resp.context
        assert resp.context["event"].pk == event_a.pk


# ==================================================================== Public Pages — event_ics

class TestEventIcsPublicView:
    def test_get_by_token_200(self, event_a, client):
        resp = client.get(reverse("crm:event_ics", args=[event_a.public_token]))
        assert resp.status_code == 200

    def test_content_type_is_text_calendar(self, event_a, client):
        resp = client.get(reverse("crm:event_ics", args=[event_a.public_token]))
        assert "text/calendar" in resp["Content-Type"]

    def test_body_starts_with_begin_vcalendar(self, event_a, client):
        resp = client.get(reverse("crm:event_ics", args=[event_a.public_token]))
        body = resp.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in body

    def test_body_has_begin_vevent(self, event_a, client):
        resp = client.get(reverse("crm:event_ics", args=[event_a.public_token]))
        body = resp.content.decode("utf-8")
        assert "BEGIN:VEVENT" in body

    def test_body_has_end_vcalendar(self, event_a, client):
        resp = client.get(reverse("crm:event_ics", args=[event_a.public_token]))
        body = resp.content.decode("utf-8")
        assert "END:VCALENDAR" in body

    def test_summary_contains_title(self, event_a, client):
        resp = client.get(reverse("crm:event_ics", args=[event_a.public_token]))
        body = resp.content.decode("utf-8")
        # event_a title is "Acme Planning Meeting"
        assert "Acme Planning Meeting" in body

    def test_rfc5545_semicolon_escaped(self, tenant_a, client):
        """RFC-5545: semicolons in SUMMARY must be escaped as \\;"""
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=1)
        e = CalendarEvent.objects.create(
            tenant=tenant_a,
            title="Meeting; urgent",
            start=start,
        )
        resp = client.get(reverse("crm:event_ics", args=[e.public_token]))
        body = resp.content.decode("utf-8")
        assert r"Meeting\; urgent" in body

    def test_rfc5545_comma_escaped(self, tenant_a, client):
        """RFC-5545: commas in SUMMARY must be escaped as \\,"""
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=1)
        e = CalendarEvent.objects.create(
            tenant=tenant_a,
            title="Meeting, review",
            start=start,
        )
        resp = client.get(reverse("crm:event_ics", args=[e.public_token]))
        body = resp.content.decode("utf-8")
        assert r"Meeting\, review" in body

    def test_invalid_token_404(self, client):
        resp = client.get(reverse("crm:event_ics", args=["bad-token"]))
        assert resp.status_code == 404

    def test_cancelled_event_has_cancelled_status(self, tenant_a, client):
        from apps.crm.models import CalendarEvent
        start = timezone.now() + datetime.timedelta(hours=1)
        e = CalendarEvent.objects.create(
            tenant=tenant_a,
            title="Cancelled Meeting",
            start=start,
            status="cancelled",
        )
        resp = client.get(reverse("crm:event_ics", args=[e.public_token]))
        body = resp.content.decode("utf-8")
        assert "STATUS:CANCELLED" in body

    def test_non_cancelled_event_has_confirmed_status(self, event_a, client):
        resp = client.get(reverse("crm:event_ics", args=[event_a.public_token]))
        body = resp.content.decode("utf-8")
        assert "STATUS:CONFIRMED" in body


# ==================================================================== EventAttendee — Inline Add/Delete Views

class TestEventAttendeeAddView:
    def test_post_adds_attendee(self, client_a, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        resp = client_a.post(
            reverse("crm:event_attendee_add", args=[event_a.pk]),
            {"name": "Ivan", "email": "ivan@example.com", "rsvp_status": "no_response", "is_organizer": False},
        )
        assert resp.status_code == 302
        assert EventAttendee.objects.filter(event=event_a, email="ivan@example.com").exists()

    def test_post_cross_tenant_event_404(self, client_a, event_b):
        """Tenant A must get 404 when adding an attendee to Tenant B's event."""
        resp = client_a.post(
            reverse("crm:event_attendee_add", args=[event_b.pk]),
            {"name": "Hacker", "email": "hack@example.com", "rsvp_status": "no_response"},
        )
        assert resp.status_code == 404

    def test_anon_redirects(self, client, event_a):
        resp = client.post(
            reverse("crm:event_attendee_add", args=[event_a.pk]),
            {"name": "Anon", "email": "anon@example.com", "rsvp_status": "no_response"},
        )
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestEventAttendeeDeleteView:
    def test_post_deletes_attendee(self, client_a, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        att = EventAttendee.objects.create(
            tenant=tenant_a, event=event_a, name="Jack", email="jack@example.com"
        )
        resp = client_a.post(reverse("crm:event_attendee_delete", args=[att.pk]))
        assert resp.status_code == 302
        assert not EventAttendee.objects.filter(pk=att.pk).exists()

    def test_anon_redirects(self, client, event_a, tenant_a):
        from apps.crm.models import EventAttendee
        att = EventAttendee.objects.create(
            tenant=tenant_a, event=event_a, name="Kate", email="kate@example.com"
        )
        resp = client.post(reverse("crm:event_attendee_delete", args=[att.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]
