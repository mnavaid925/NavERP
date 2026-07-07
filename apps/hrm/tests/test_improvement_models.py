"""Tests for HRM 3.21 Performance Improvement models: PerformanceImprovementPlan (PIP-;
clean() subject!=manager + outcome-iff-closed both directions + end>start + extended_end>end;
effective_end_date/checkin_count), PIPCheckIn (PCI-; child of PIP), WarningLetter (WRN-; clean()
issued_to!=issued_by + expiry>incident; is_expired/prior_warnings), CoachingNote (CN-; clean()
employee!=coach). Per-tenant sequence + unique_together on `number` for all 4."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ================================================================ PerformanceImprovementPlan
class TestPerformanceImprovementPlanModel:
    def test_default_status_is_draft(self, pip_draft_a):
        assert pip_draft_a.status == "draft"

    def test_default_outcome_is_blank(self, pip_draft_a):
        assert pip_draft_a.outcome == ""

    def test_number_prefix(self, pip_draft_a):
        assert pip_draft_a.number.startswith("PIP-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import PerformanceImprovementPlan
        common = dict(
            tenant=tenant_a, subject=employee_a, manager=employee_a2,
            performance_issue="x", expected_standards="x", improvement_goals="x",
            measurement_criteria="x", start_date=datetime.date(2026, 7, 1),
            end_date=datetime.date(2026, 9, 29),
        )
        p1 = PerformanceImprovementPlan.objects.create(**common)
        p2 = PerformanceImprovementPlan.objects.create(**common)
        assert p1.number != p2.number

    def test_unique_together_tenant_number(self, tenant_a, pip_draft_a):
        from apps.hrm.models import PerformanceImprovementPlan
        with pytest.raises(IntegrityError):
            PerformanceImprovementPlan.objects.create(
                tenant=tenant_a, number=pip_draft_a.number,
                subject=pip_draft_a.subject, manager=pip_draft_a.manager,
                performance_issue="x", expected_standards="x", improvement_goals="x",
                measurement_criteria="x", start_date=pip_draft_a.start_date, end_date=pip_draft_a.end_date,
            )

    def test_str_contains_number_and_subject_name(self, pip_draft_a):
        s = str(pip_draft_a)
        assert pip_draft_a.number in s
        assert "Alice Smith" in s  # employee_a's party name

    def test_str_falls_back_to_number_when_no_subject(self, tenant_a):
        from apps.hrm.models import PerformanceImprovementPlan
        pip = PerformanceImprovementPlan(tenant=tenant_a, number="PIP-00099")
        assert str(pip) == "PIP-00099"

    # -------------------------------------------------- clean(): subject != manager
    def test_clean_rejects_subject_equal_manager(self, tenant_a, employee_a):
        from apps.hrm.models import PerformanceImprovementPlan
        pip = PerformanceImprovementPlan(
            tenant=tenant_a, subject=employee_a, manager=employee_a,
            start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
        )
        with pytest.raises(ValidationError):
            pip.clean()

    def test_clean_allows_distinct_subject_manager(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import PerformanceImprovementPlan
        pip = PerformanceImprovementPlan(
            tenant=tenant_a, subject=employee_a, manager=employee_a2,
            start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
        )
        pip.clean()  # must not raise

    # -------------------------------------------------- clean(): outcome iff closed (both directions)
    def test_clean_rejects_closed_without_outcome(self, pip_active_a):
        pip_active_a.status = "closed"
        with pytest.raises(ValidationError):
            pip_active_a.clean()

    def test_clean_rejects_outcome_when_not_closed(self, pip_active_a):
        pip_active_a.outcome = "successful"
        with pytest.raises(ValidationError):
            pip_active_a.clean()

    def test_clean_allows_closed_with_outcome(self, pip_active_a):
        pip_active_a.status = "closed"
        pip_active_a.outcome = "successful"
        pip_active_a.clean()  # must not raise

    def test_clean_allows_draft_with_no_outcome(self, pip_draft_a):
        pip_draft_a.clean()  # must not raise

    # -------------------------------------------------- clean(): end_date > start_date
    def test_clean_rejects_end_date_not_after_start(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import PerformanceImprovementPlan
        pip = PerformanceImprovementPlan(
            tenant=tenant_a, subject=employee_a, manager=employee_a2,
            start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 7, 1),
        )
        with pytest.raises(ValidationError):
            pip.clean()

    def test_clean_rejects_end_date_before_start(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import PerformanceImprovementPlan
        pip = PerformanceImprovementPlan(
            tenant=tenant_a, subject=employee_a, manager=employee_a2,
            start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 6, 1),
        )
        with pytest.raises(ValidationError):
            pip.clean()

    # -------------------------------------------------- clean(): extended_end_date > end_date
    def test_clean_rejects_extended_end_not_after_end(self, pip_active_a):
        pip_active_a.extended_end_date = pip_active_a.end_date
        with pytest.raises(ValidationError):
            pip_active_a.clean()

    def test_clean_allows_extended_end_after_end(self, pip_active_a):
        pip_active_a.extended_end_date = pip_active_a.end_date + datetime.timedelta(days=30)
        pip_active_a.clean()  # must not raise

    def test_clean_allows_no_extended_end_date(self, pip_draft_a):
        pip_draft_a.clean()  # must not raise (extended_end_date is None)

    # -------------------------------------------------- derived properties
    def test_effective_end_date_defaults_to_end_date(self, pip_draft_a):
        assert pip_draft_a.effective_end_date == pip_draft_a.end_date

    def test_effective_end_date_uses_extension_when_set(self, pip_active_a):
        extended = pip_active_a.end_date + datetime.timedelta(days=30)
        pip_active_a.extended_end_date = extended
        pip_active_a.save(update_fields=["extended_end_date"])
        assert pip_active_a.effective_end_date == extended

    def test_checkin_count_zero_with_no_checkins(self, pip_active_a):
        assert pip_active_a.checkin_count == 0

    def test_checkin_count_reflects_checkins(self, tenant_a, pip_active_a):
        from apps.hrm.models import PIPCheckIn
        PIPCheckIn.objects.create(
            tenant=tenant_a, pip=pip_active_a, checkin_date=datetime.date(2026, 7, 15))
        PIPCheckIn.objects.create(
            tenant=tenant_a, pip=pip_active_a, checkin_date=datetime.date(2026, 8, 1))
        assert pip_active_a.checkin_count == 2

    # -------------------------------------------------- FK on_delete behavior
    def test_subject_delete_protected(self, pip_draft_a, employee_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a.delete()

    def test_manager_delete_protected(self, pip_draft_a, employee_a2):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a2.delete()

    def test_triggering_review_set_null_on_delete(self, tenant_a, pip_draft_a, performance_review_a):
        pip_draft_a.triggering_review = performance_review_a
        pip_draft_a.save(update_fields=["triggering_review"])
        performance_review_a.delete()
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.triggering_review_id is None

    def test_hr_approved_at_null_by_default(self, pip_draft_a):
        assert pip_draft_a.hr_approved_at is None

    def test_acknowledged_at_null_by_default(self, pip_draft_a):
        assert pip_draft_a.acknowledged_at is None


# ================================================================ PIPCheckIn
class TestPIPCheckInModel:
    def test_default_progress_rating_is_on_track(self, pipcheckin_a):
        assert pipcheckin_a.progress_rating == "on_track"

    def test_number_prefix(self, pipcheckin_a):
        assert pipcheckin_a.number.startswith("PCI-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, pip_active_a):
        from apps.hrm.models import PIPCheckIn
        c1 = PIPCheckIn.objects.create(
            tenant=tenant_a, pip=pip_active_a, checkin_date=datetime.date(2026, 7, 15))
        c2 = PIPCheckIn.objects.create(
            tenant=tenant_a, pip=pip_active_a, checkin_date=datetime.date(2026, 8, 1))
        assert c1.number != c2.number

    def test_unique_together_tenant_number(self, tenant_a, pipcheckin_a):
        from apps.hrm.models import PIPCheckIn
        with pytest.raises(IntegrityError):
            PIPCheckIn.objects.create(
                tenant=tenant_a, number=pipcheckin_a.number, pip=pipcheckin_a.pip,
                checkin_date=pipcheckin_a.checkin_date,
            )

    def test_str_contains_number_and_pip_number(self, pipcheckin_a):
        s = str(pipcheckin_a)
        assert pipcheckin_a.number in s
        assert pipcheckin_a.pip.number in s

    def test_str_falls_back_to_number_when_no_pip(self, tenant_a):
        from apps.hrm.models import PIPCheckIn
        ci = PIPCheckIn(tenant=tenant_a, number="PCI-00099")
        assert str(ci) == "PCI-00099"

    def test_completed_at_null_by_default(self, tenant_a, pip_active_a):
        from apps.hrm.models import PIPCheckIn
        ci = PIPCheckIn.objects.create(
            tenant=tenant_a, pip=pip_active_a, checkin_date=datetime.date(2026, 7, 15))
        assert ci.completed_at is None

    def test_pip_delete_cascades(self, tenant_a, pip_active_a, pipcheckin_a):
        from apps.hrm.models import PIPCheckIn
        pk = pipcheckin_a.pk
        pip_active_a.delete()
        assert not PIPCheckIn.objects.filter(pk=pk).exists()

    def test_ordering_is_pip_then_checkin_date(self, tenant_a, pip_active_a):
        from apps.hrm.models import PIPCheckIn
        later = PIPCheckIn.objects.create(
            tenant=tenant_a, pip=pip_active_a, checkin_date=datetime.date(2026, 9, 1))
        earlier = PIPCheckIn.objects.create(
            tenant=tenant_a, pip=pip_active_a, checkin_date=datetime.date(2026, 7, 1))
        pks = list(PIPCheckIn.objects.filter(pip=pip_active_a).values_list("pk", flat=True))
        assert pks.index(earlier.pk) < pks.index(later.pk)


# ================================================================ WarningLetter
class TestWarningLetterModel:
    def test_default_level_is_verbal(self, warning_draft_a):
        assert warning_draft_a.level == "verbal"

    def test_default_status_is_draft(self, warning_draft_a):
        assert warning_draft_a.status == "draft"

    def test_number_prefix(self, warning_draft_a):
        assert warning_draft_a.number.startswith("WRN-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import WarningLetter
        common = dict(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1), description="x",
        )
        w1 = WarningLetter.objects.create(**common)
        w2 = WarningLetter.objects.create(**common)
        assert w1.number != w2.number

    def test_unique_together_tenant_number(self, tenant_a, warning_draft_a):
        from apps.hrm.models import WarningLetter
        with pytest.raises(IntegrityError):
            WarningLetter.objects.create(
                tenant=tenant_a, number=warning_draft_a.number,
                issued_to=warning_draft_a.issued_to, issued_by=warning_draft_a.issued_by,
                incident_date=warning_draft_a.incident_date, description="dup",
            )

    def test_str_contains_number_recipient_and_level(self, warning_draft_a):
        s = str(warning_draft_a)
        assert warning_draft_a.number in s
        assert "Alice Smith" in s  # employee_a's party name
        assert "Verbal Warning" in s

    def test_str_falls_back_to_unknown_recipient(self, tenant_a):
        from apps.hrm.models import WarningLetter
        w = WarningLetter(tenant=tenant_a, number="WRN-00099", level="verbal")
        assert "?" in str(w)

    # -------------------------------------------------- clean(): issued_to != issued_by
    def test_clean_rejects_issued_to_equal_issued_by(self, tenant_a, employee_a):
        from apps.hrm.models import WarningLetter
        w = WarningLetter(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a,
            incident_date=datetime.date(2026, 6, 1),
        )
        with pytest.raises(ValidationError):
            w.clean()

    def test_clean_allows_distinct_issued_to_issued_by(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import WarningLetter
        w = WarningLetter(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1),
        )
        w.clean()  # must not raise

    # -------------------------------------------------- clean(): expiry_date > incident_date
    def test_clean_rejects_expiry_not_after_incident(self, warning_draft_a):
        warning_draft_a.expiry_date = warning_draft_a.incident_date
        with pytest.raises(ValidationError):
            warning_draft_a.clean()

    def test_clean_rejects_expiry_before_incident(self, warning_draft_a):
        warning_draft_a.expiry_date = warning_draft_a.incident_date - datetime.timedelta(days=1)
        with pytest.raises(ValidationError):
            warning_draft_a.clean()

    def test_clean_allows_expiry_after_incident(self, warning_draft_a):
        warning_draft_a.expiry_date = warning_draft_a.incident_date + datetime.timedelta(days=365)
        warning_draft_a.clean()  # must not raise

    def test_clean_allows_no_expiry_date(self, warning_draft_a):
        warning_draft_a.clean()  # must not raise (expiry_date is None)

    # -------------------------------------------------- is_expired
    def test_is_expired_false_when_no_expiry_date(self, warning_draft_a):
        assert warning_draft_a.is_expired is False

    def test_is_expired_false_when_expiry_in_future(self, warning_draft_a):
        warning_draft_a.expiry_date = timezone.now().date() + datetime.timedelta(days=10)
        warning_draft_a.save(update_fields=["expiry_date"])
        assert warning_draft_a.is_expired is False

    def test_is_expired_true_when_expiry_in_past(self, warning_draft_a):
        warning_draft_a.expiry_date = timezone.now().date() - datetime.timedelta(days=1)
        warning_draft_a.save(update_fields=["expiry_date"])
        assert warning_draft_a.is_expired is True

    # -------------------------------------------------- prior_warnings
    def test_prior_warnings_empty_with_no_history(self, warning_draft_a):
        assert list(warning_draft_a.prior_warnings) == []

    def test_prior_warnings_returns_earlier_warnings_to_same_employee(
        self, tenant_a, employee_a, employee_a2
    ):
        from apps.hrm.models import WarningLetter
        earlier = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 3, 1), description="Earlier incident",
        )
        later = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1), description="Later incident",
        )
        pks = list(later.prior_warnings.values_list("pk", flat=True))
        assert earlier.pk in pks
        assert later.pk not in pks  # excludes self

    def test_prior_warnings_excludes_other_employees(
        self, tenant_a, employee_a, employee_a2, outsider_employee_a
    ):
        from apps.hrm.models import WarningLetter
        WarningLetter.objects.create(
            tenant=tenant_a, issued_to=outsider_employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 3, 1), description="Someone else's warning",
        )
        current = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1), description="Current incident",
        )
        assert current.prior_warnings.count() == 0

    def test_prior_warnings_ordered_desc_by_incident_date(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import WarningLetter
        oldest = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 1, 1), description="Oldest",
        )
        middle = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 3, 1), description="Middle",
        )
        latest = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1), description="Latest",
        )
        pks = list(latest.prior_warnings.values_list("pk", flat=True))
        assert pks == [middle.pk, oldest.pk]

    def test_prior_warnings_empty_when_no_issued_to_or_incident_date(self, tenant_a):
        from apps.hrm.models import WarningLetter
        w = WarningLetter(tenant=tenant_a)
        assert list(w.prior_warnings) == []

    # -------------------------------------------------- FK on_delete behavior
    def test_issued_to_delete_protected(self, warning_draft_a, employee_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a.delete()

    def test_issued_by_delete_protected(self, warning_draft_a, employee_a2):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a2.delete()

    def test_related_pip_set_null_on_delete(self, tenant_a, warning_draft_a, pip_draft_a):
        warning_draft_a.related_pip = pip_draft_a
        warning_draft_a.save(update_fields=["related_pip"])
        pip_draft_a.delete()
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.related_pip_id is None

    def test_acknowledged_at_null_by_default(self, warning_draft_a):
        assert warning_draft_a.acknowledged_at is None

    def test_employee_response_blank_by_default(self, warning_draft_a):
        assert warning_draft_a.employee_response == ""


# ================================================================ CoachingNote
class TestCoachingNoteModel:
    def test_default_category_is_other(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import CoachingNote
        note = CoachingNote.objects.create(
            tenant=tenant_a, employee=employee_a, coach=employee_a2, content="x")
        assert note.category == "other"

    def test_default_note_date_is_today(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import CoachingNote
        note = CoachingNote.objects.create(
            tenant=tenant_a, employee=employee_a, coach=employee_a2, content="x")
        assert note.note_date == timezone.localdate()

    def test_number_prefix(self, coaching_note_a):
        assert coaching_note_a.number.startswith("CN-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import CoachingNote
        n1 = CoachingNote.objects.create(
            tenant=tenant_a, employee=employee_a, coach=employee_a2, content="a")
        n2 = CoachingNote.objects.create(
            tenant=tenant_a, employee=employee_a, coach=employee_a2, content="b")
        assert n1.number != n2.number

    def test_unique_together_tenant_number(self, tenant_a, coaching_note_a):
        from apps.hrm.models import CoachingNote
        with pytest.raises(IntegrityError):
            CoachingNote.objects.create(
                tenant=tenant_a, number=coaching_note_a.number,
                employee=coaching_note_a.employee, coach=coaching_note_a.coach, content="dup",
            )

    def test_str_contains_number_coach_and_employee_names(self, coaching_note_a):
        s = str(coaching_note_a)
        assert coaching_note_a.number in s
        assert "Carol White" in s  # employee_a2's party name (coach)
        assert "Alice Smith" in s  # employee_a's party name (coached employee)

    def test_str_falls_back_to_unknowns(self, tenant_a):
        from apps.hrm.models import CoachingNote
        note = CoachingNote(tenant=tenant_a, number="CN-00099")
        s = str(note)
        assert "?" in s

    # -------------------------------------------------- clean(): employee != coach
    def test_clean_rejects_employee_equal_coach(self, tenant_a, employee_a):
        from apps.hrm.models import CoachingNote
        note = CoachingNote(tenant=tenant_a, employee=employee_a, coach=employee_a, content="x")
        with pytest.raises(ValidationError):
            note.clean()

    def test_clean_allows_distinct_employee_coach(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import CoachingNote
        note = CoachingNote(tenant=tenant_a, employee=employee_a, coach=employee_a2, content="x")
        note.clean()  # must not raise

    # -------------------------------------------------- FK on_delete behavior
    def test_employee_delete_protected(self, coaching_note_a, employee_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a.delete()

    def test_coach_delete_protected(self, coaching_note_a, employee_a2):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            employee_a2.delete()

    def test_related_pip_set_null_on_delete(self, tenant_a, coaching_note_a, pip_draft_a):
        coaching_note_a.related_pip = pip_draft_a
        coaching_note_a.save(update_fields=["related_pip"])
        pip_draft_a.delete()
        coaching_note_a.refresh_from_db()
        assert coaching_note_a.related_pip_id is None

    def test_ordering_is_newest_note_date_first(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import CoachingNote
        older = CoachingNote.objects.create(
            tenant=tenant_a, employee=employee_a, coach=employee_a2,
            note_date=datetime.date(2026, 1, 1), content="Older",
        )
        newer = CoachingNote.objects.create(
            tenant=tenant_a, employee=employee_a, coach=employee_a2,
            note_date=datetime.date(2026, 6, 1), content="Newer",
        )
        pks = list(CoachingNote.objects.filter(tenant=tenant_a).values_list("pk", flat=True))
        assert pks.index(newer.pk) < pks.index(older.pk)
