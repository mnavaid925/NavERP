"""Tests for HRM 3.20 Continuous Feedback models: KudosBadge (usage_count/__str__), Feedback
(clean() giver!=receiver guard, giver_anonymized, __str__, auto-numbering FBK-), OneOnOneMeeting
(clean() manager!=employee guard, open_action_item_count, __str__, auto-numbering O2O-),
MeetingActionItem (is_overdue, __str__, auto-numbering MAI-). Per-tenant sequence + unique_together
on `number`."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ================================================================ KudosBadge
class TestKudosBadgeModel:
    def test_default_is_active_true(self, tenant_a):
        from apps.hrm.models import KudosBadge
        badge = KudosBadge.objects.create(tenant=tenant_a, name="Fresh Badge")
        assert badge.is_active is True

    def test_str_is_name(self, kudos_badge_a):
        assert str(kudos_badge_a) == "Team Player"

    def test_no_auto_number(self, kudos_badge_a):
        """KudosBadge is TenantOwned, not TenantNumbered — no `number` attribute."""
        assert not hasattr(kudos_badge_a, "number")

    def test_unique_together_tenant_name(self, tenant_a, kudos_badge_a):
        from apps.hrm.models import KudosBadge
        with pytest.raises(IntegrityError):
            KudosBadge.objects.create(tenant=tenant_a, name=kudos_badge_a.name)

    def test_usage_count_zero_with_no_feedback(self, kudos_badge_a):
        assert kudos_badge_a.usage_count == 0

    def test_usage_count_reflects_feedback(self, tenant_a, kudos_badge_a, employee_a2, employee_a):
        from apps.hrm.models import Feedback
        Feedback.objects.create(
            tenant=tenant_a, giver=employee_a2, receiver=employee_a,
            feedback_type="kudos", badge=kudos_badge_a,
        )
        assert kudos_badge_a.usage_count == 1

    def test_badge_delete_set_null_on_feedback(self, tenant_a, kudos_badge_a, feedback_a):
        feedback_a.badge = kudos_badge_a
        feedback_a.save(update_fields=["badge"])
        kudos_badge_a.delete()
        feedback_a.refresh_from_db()
        assert feedback_a.badge_id is None


# ================================================================ Feedback
class TestFeedbackModel:
    def test_default_feedback_type_is_kudos(self, tenant_a, employee_a2, employee_a):
        from apps.hrm.models import Feedback
        fb = Feedback.objects.create(tenant=tenant_a, giver=employee_a2, receiver=employee_a)
        assert fb.feedback_type == "kudos"

    def test_default_visibility_is_private(self, tenant_a, employee_a2, employee_a):
        from apps.hrm.models import Feedback
        fb = Feedback.objects.create(tenant=tenant_a, giver=employee_a2, receiver=employee_a)
        assert fb.visibility == "private"

    def test_default_status_is_given(self, tenant_a, employee_a2, employee_a):
        from apps.hrm.models import Feedback
        fb = Feedback.objects.create(tenant=tenant_a, giver=employee_a2, receiver=employee_a)
        assert fb.status == "given"

    def test_default_is_anonymous_false(self, feedback_a):
        assert feedback_a.is_anonymous is False

    def test_number_prefix(self, feedback_a):
        assert feedback_a.number.startswith("FBK-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a2, employee_a):
        from apps.hrm.models import Feedback
        fb1 = Feedback.objects.create(tenant=tenant_a, giver=employee_a2, receiver=employee_a)
        fb2 = Feedback.objects.create(tenant=tenant_a, giver=employee_a2, receiver=employee_a)
        assert fb1.number != fb2.number

    def test_unique_together_tenant_number(self, tenant_a, feedback_a):
        from apps.hrm.models import Feedback
        with pytest.raises(IntegrityError):
            Feedback.objects.create(
                tenant=tenant_a, number=feedback_a.number, giver=feedback_a.giver,
                receiver=feedback_a.receiver,
            )

    def test_str_contains_number_and_receiver_name(self, feedback_a):
        s = str(feedback_a)
        assert feedback_a.number in s
        assert "Alice Smith" in s  # employee_a's party name (root conftest person_a)

    def test_clean_rejects_giver_equal_receiver(self, tenant_a, employee_a):
        from apps.hrm.models import Feedback
        fb = Feedback(tenant=tenant_a, giver=employee_a, receiver=employee_a)
        with pytest.raises(ValidationError):
            fb.clean()

    def test_clean_allows_giver_none(self, tenant_a, employee_a):
        """giver may be null (system/anonymized entry point) — clean() only guards when BOTH ids
        are set."""
        from apps.hrm.models import Feedback
        fb = Feedback(tenant=tenant_a, receiver=employee_a)
        fb.clean()  # must not raise

    def test_clean_allows_distinct_giver_receiver(self, tenant_a, employee_a2, employee_a):
        from apps.hrm.models import Feedback
        fb = Feedback(tenant=tenant_a, giver=employee_a2, receiver=employee_a)
        fb.clean()  # must not raise

    def test_giver_anonymized_true_when_is_anonymous(self, feedback_a):
        feedback_a.is_anonymous = True
        feedback_a.save(update_fields=["is_anonymous"])
        assert feedback_a.giver_anonymized is True

    def test_giver_anonymized_false_by_default(self, feedback_a):
        assert feedback_a.giver_anonymized is False

    def test_acknowledged_at_null_by_default(self, feedback_a):
        assert feedback_a.acknowledged_at is None

    def test_giver_delete_protected(self, tenant_a, feedback_a, employee_a2):
        """giver is on_delete=PROTECT — deleting the giver's EmployeeProfile must not silently
        cascade-delete the feedback row."""
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a2.delete()

    def test_receiver_delete_protected(self, tenant_a, feedback_a, employee_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a.delete()

    def test_related_objective_set_null_on_delete(self, tenant_a, feedback_a, objective_a):
        feedback_a.related_objective = objective_a
        feedback_a.save(update_fields=["related_objective"])
        objective_a.delete()
        feedback_a.refresh_from_db()
        assert feedback_a.related_objective_id is None

    def test_related_review_set_null_on_delete(self, tenant_a, feedback_a, performance_review_a):
        feedback_a.related_review = performance_review_a
        feedback_a.save(update_fields=["related_review"])
        performance_review_a.delete()
        feedback_a.refresh_from_db()
        assert feedback_a.related_review_id is None

    def test_requested_from_self_fk_set_null_on_delete(self, tenant_a, employee_a2, employee_a):
        from apps.hrm.models import Feedback
        ask = Feedback.objects.create(
            tenant=tenant_a, receiver=employee_a2, giver=None,
            feedback_type="request", status="requested",
        )
        response = Feedback.objects.create(
            tenant=tenant_a, giver=employee_a2, receiver=employee_a,
            feedback_type="appreciation", status="given", requested_from=ask,
        )
        ask.delete()
        response.refresh_from_db()
        assert response.requested_from_id is None

    def test_ordering_is_newest_first(self, tenant_a, employee_a2, employee_a):
        """auto_now_add can tie at whole-second/microsecond resolution when rows are created
        back-to-back in the same test — set created_at explicitly (deterministic, no real-clock
        dependency) so the ordering assertion is unambiguous."""
        from apps.hrm.models import Feedback
        older = Feedback.objects.create(tenant=tenant_a, giver=employee_a2, receiver=employee_a)
        newer = Feedback.objects.create(tenant=tenant_a, giver=employee_a2, receiver=employee_a)
        Feedback.objects.filter(pk=older.pk).update(
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc))
        Feedback.objects.filter(pk=newer.pk).update(
            created_at=datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc))
        pks = list(Feedback.objects.filter(tenant=tenant_a).order_by("-created_at").values_list("pk", flat=True))
        assert pks.index(newer.pk) < pks.index(older.pk)


# ================================================================ OneOnOneMeeting
class TestOneOnOneMeetingModel:
    def test_default_status_is_scheduled(self, oneonone_a):
        assert oneonone_a.status == "scheduled"

    def test_number_prefix(self, oneonone_a):
        assert oneonone_a.number.startswith("O2O-")

    def test_unique_together_tenant_number(self, tenant_a, oneonone_a):
        from apps.hrm.models import OneOnOneMeeting
        with pytest.raises(IntegrityError):
            OneOnOneMeeting.objects.create(
                tenant=tenant_a, number=oneonone_a.number,
                manager=oneonone_a.manager, employee=oneonone_a.employee,
                scheduled_at=oneonone_a.scheduled_at,
            )

    def test_str_contains_number_manager_and_employee_names(self, oneonone_a):
        s = str(oneonone_a)
        assert oneonone_a.number in s
        assert "Carol White" in s  # employee_a2's party name (manager)
        assert "Alice Smith" in s  # employee_a's party name (employee)

    def test_clean_rejects_manager_equal_employee(self, tenant_a, employee_a):
        from apps.hrm.models import OneOnOneMeeting
        m = OneOnOneMeeting(
            tenant=tenant_a, manager=employee_a, employee=employee_a,
            scheduled_at=timezone.now(),
        )
        with pytest.raises(ValidationError):
            m.clean()

    def test_clean_allows_distinct_manager_employee(self, tenant_a, employee_a2, employee_a):
        from apps.hrm.models import OneOnOneMeeting
        m = OneOnOneMeeting(
            tenant=tenant_a, manager=employee_a2, employee=employee_a, scheduled_at=timezone.now(),
        )
        m.clean()  # must not raise

    def test_open_action_item_count_zero_with_no_items(self, oneonone_a):
        assert oneonone_a.open_action_item_count == 0

    def test_open_action_item_count_reflects_open_items_only(self, tenant_a, oneonone_a, employee_a):
        from apps.hrm.models import MeetingActionItem
        MeetingActionItem.objects.create(
            tenant=tenant_a, meeting=oneonone_a, description="Open item", owner=employee_a, status="open",
        )
        MeetingActionItem.objects.create(
            tenant=tenant_a, meeting=oneonone_a, description="Done item", owner=employee_a, status="done",
        )
        assert oneonone_a.open_action_item_count == 1

    def test_completed_at_null_by_default(self, oneonone_a):
        assert oneonone_a.completed_at is None

    def test_manager_delete_protected(self, oneonone_a, employee_a2):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a2.delete()

    def test_employee_delete_protected(self, oneonone_a, employee_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a.delete()

    def test_related_objective_set_null_on_delete(self, tenant_a, oneonone_a, objective_a):
        oneonone_a.related_objective = objective_a
        oneonone_a.save(update_fields=["related_objective"])
        objective_a.delete()
        oneonone_a.refresh_from_db()
        assert oneonone_a.related_objective_id is None

    def test_ordering_is_newest_scheduled_first(self, tenant_a, employee_a2, employee_a):
        from apps.hrm.models import OneOnOneMeeting
        earlier = OneOnOneMeeting.objects.create(
            tenant=tenant_a, manager=employee_a2, employee=employee_a,
            scheduled_at=datetime.datetime(2026, 6, 1, 10, 0, tzinfo=datetime.timezone.utc),
        )
        later = OneOnOneMeeting.objects.create(
            tenant=tenant_a, manager=employee_a2, employee=employee_a,
            scheduled_at=datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc),
        )
        pks = list(OneOnOneMeeting.objects.filter(tenant=tenant_a).values_list("pk", flat=True))
        assert pks.index(later.pk) < pks.index(earlier.pk)


# ================================================================ MeetingActionItem
class TestMeetingActionItemModel:
    def test_default_status_is_open(self, action_item_a):
        assert action_item_a.status == "open"

    def test_number_prefix(self, action_item_a):
        assert action_item_a.number.startswith("MAI-")

    def test_unique_together_tenant_number(self, tenant_a, action_item_a):
        from apps.hrm.models import MeetingActionItem
        with pytest.raises(IntegrityError):
            MeetingActionItem.objects.create(
                tenant=tenant_a, number=action_item_a.number, meeting=action_item_a.meeting,
                description="Dup", owner=action_item_a.owner,
            )

    def test_str_contains_number_and_description_prefix(self, action_item_a):
        s = str(action_item_a)
        assert action_item_a.number in s
        assert "Set up mentorship" in s

    def test_is_overdue_false_when_open_no_due_date(self, action_item_a):
        assert action_item_a.is_overdue is False

    def test_is_overdue_false_when_due_date_in_future(self, action_item_a):
        action_item_a.due_date = timezone.now().date() + datetime.timedelta(days=10)
        action_item_a.save(update_fields=["due_date"])
        assert action_item_a.is_overdue is False

    def test_is_overdue_true_when_open_and_past_due(self, action_item_a):
        action_item_a.due_date = timezone.now().date() - datetime.timedelta(days=1)
        action_item_a.save(update_fields=["due_date"])
        assert action_item_a.is_overdue is True

    def test_is_overdue_false_when_done_even_if_past_due(self, action_item_a):
        action_item_a.due_date = timezone.now().date() - datetime.timedelta(days=1)
        action_item_a.status = "done"
        action_item_a.save(update_fields=["due_date", "status"])
        assert action_item_a.is_overdue is False

    def test_completed_at_null_by_default(self, action_item_a):
        assert action_item_a.completed_at is None

    def test_meeting_delete_cascades(self, tenant_a, oneonone_a, action_item_a):
        from apps.hrm.models import MeetingActionItem
        pk = action_item_a.pk
        oneonone_a.delete()
        assert not MeetingActionItem.objects.filter(pk=pk).exists()

    def test_owner_delete_protected(self, action_item_a, employee_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a.delete()
