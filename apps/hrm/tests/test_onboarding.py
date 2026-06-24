"""Comprehensive tests for HRM 3.3 Employee Onboarding sub-module.

Covers:
  - Models: OnboardingTemplate, OnboardingTemplateTask, OnboardingProgram,
            OnboardingTask, OnboardingDocument, AssetAllocation, OrientationSession
  - Service: generate_tasks_from_template (idempotency, due-date math, no-template guard)
  - Forms: field exclusion security (esign_status, attendance_status, status), clean() guards
  - Views: CRUD 200s, workflow actions (activate/complete/cancel, task/doc/asset/session),
           delete guards, admin-only restrictions
  - Multi-tenant isolation (IDOR): cross-tenant pk access → 404 for every model
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================
# Fixtures — onboarding-specific (reuses root + hrm conftest)
# ============================================================

@pytest.fixture
def template_a(db, tenant_a):
    """A basic OnboardingTemplate for tenant_a."""
    from apps.hrm.models import OnboardingTemplate
    return OnboardingTemplate.objects.create(
        tenant=tenant_a,
        name="Standard Engineer Onboarding",
        description="Full kit for engineering hires",
        is_active=True,
    )


@pytest.fixture
def template_b(db, tenant_b):
    """An OnboardingTemplate for tenant_b (IDOR tests)."""
    from apps.hrm.models import OnboardingTemplate
    return OnboardingTemplate.objects.create(
        tenant=tenant_b,
        name="Globex Onboarding",
        is_active=True,
    )


@pytest.fixture
def template_task_a(db, tenant_a, template_a):
    """One task definition on template_a."""
    from apps.hrm.models import OnboardingTemplateTask
    return OnboardingTemplateTask.objects.create(
        tenant=tenant_a,
        template=template_a,
        title="Setup Laptop",
        task_category="it_setup",
        assignee_role="it",
        due_offset_days=0,
        phase="week_1",
        order=1,
        is_mandatory=True,
    )


@pytest.fixture
def template_task_a2(db, tenant_a, template_a):
    """A second task on template_a with a non-zero offset."""
    from apps.hrm.models import OnboardingTemplateTask
    return OnboardingTemplateTask.objects.create(
        tenant=tenant_a,
        template=template_a,
        title="Complete HR Paperwork",
        task_category="hr_admin",
        assignee_role="new_hire",
        due_offset_days=3,
        phase="week_1",
        order=2,
        is_mandatory=True,
    )


@pytest.fixture
def program_draft_a(db, tenant_a, employee_a, template_a):
    """A draft OnboardingProgram for employee_a, tenant_a — with template."""
    from apps.hrm.models import OnboardingProgram
    return OnboardingProgram.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        template=template_a,
        start_date=datetime.date(2026, 7, 1),
        status="draft",
    )


@pytest.fixture
def program_b(db, tenant_b, employee_b, template_b):
    """A draft OnboardingProgram for tenant_b (IDOR tests)."""
    from apps.hrm.models import OnboardingProgram
    return OnboardingProgram.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        template=template_b,
        start_date=datetime.date(2026, 8, 1),
        status="draft",
    )


@pytest.fixture
def program_active_a(db, tenant_a, employee_a, template_a, template_task_a, template_task_a2):
    """An active OnboardingProgram with two generated tasks."""
    from apps.hrm.models import OnboardingProgram
    from apps.hrm.services import generate_tasks_from_template
    prog = OnboardingProgram.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        template=template_a,
        start_date=datetime.date(2026, 7, 1),
        status="active",
    )
    generate_tasks_from_template(prog)
    return prog


@pytest.fixture
def onb_task_a(db, program_active_a):
    """The first OnboardingTask from program_active_a (Setup Laptop)."""
    from apps.hrm.models import OnboardingTask
    return OnboardingTask.objects.filter(
        program=program_active_a, title="Setup Laptop"
    ).first()


@pytest.fixture
def onb_task_b(db, tenant_b, program_b):
    """A manual OnboardingTask on tenant_b's program (IDOR tests)."""
    from apps.hrm.models import OnboardingTask
    return OnboardingTask.objects.create(
        tenant=tenant_b,
        program=program_b,
        title="Globex Task",
        task_category="hr_admin",
        assignee_role="hr",
        phase="week_1",
    )


@pytest.fixture
def doc_pending_a(db, tenant_a, program_active_a):
    """A document requiring e-sign (esign_status='pending') on tenant_a's program."""
    from apps.hrm.models import OnboardingDocument
    return OnboardingDocument.objects.create(
        tenant=tenant_a,
        program=program_active_a,
        document_type="employment_contract",
        title="Employment Contract",
        esign_required=True,
    )


@pytest.fixture
def doc_not_required_a(db, tenant_a, program_active_a):
    """A document that does NOT require e-sign (esign_status='not_required')."""
    from apps.hrm.models import OnboardingDocument
    return OnboardingDocument.objects.create(
        tenant=tenant_a,
        program=program_active_a,
        document_type="id_proof",
        title="ID Proof Copy",
        esign_required=False,
    )


@pytest.fixture
def doc_b(db, tenant_b, program_b):
    """An OnboardingDocument on tenant_b's program (IDOR tests)."""
    from apps.hrm.models import OnboardingDocument
    return OnboardingDocument.objects.create(
        tenant=tenant_b,
        program=program_b,
        document_type="nda",
        title="Globex NDA",
        esign_required=True,
    )


@pytest.fixture
def asset_pending_a(db, tenant_a, employee_a, program_active_a):
    """A pending asset allocation on tenant_a."""
    from apps.hrm.models import AssetAllocation
    return AssetAllocation.objects.create(
        tenant=tenant_a,
        program=program_active_a,
        employee=employee_a,
        asset_name="MacBook Pro 14",
        asset_category="laptop",
        serial_number="MBP-2026-001",
        status="pending",
    )


@pytest.fixture
def asset_issued_a(db, tenant_a, employee_a, program_active_a, admin_user):
    """An already-issued asset allocation on tenant_a."""
    from apps.hrm.models import AssetAllocation
    return AssetAllocation.objects.create(
        tenant=tenant_a,
        program=program_active_a,
        employee=employee_a,
        asset_name="iPhone 15",
        asset_category="phone",
        serial_number="IPH-2026-001",
        status="issued",
        issued_at=timezone.now(),
        issued_by=admin_user,
    )


@pytest.fixture
def asset_b(db, tenant_b, employee_b, program_b):
    """An AssetAllocation on tenant_b (IDOR tests)."""
    from apps.hrm.models import AssetAllocation
    return AssetAllocation.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        program=program_b,
        asset_name="Globex Laptop",
        asset_category="laptop",
        status="pending",
    )


@pytest.fixture
def session_a(db, tenant_a, employee_a, program_active_a):
    """A scheduled OrientationSession on tenant_a."""
    from apps.hrm.models import OrientationSession
    return OrientationSession.objects.create(
        tenant=tenant_a,
        program=program_active_a,
        employee=employee_a,
        title="Day 1 Orientation",
        session_type="orientation",
        scheduled_at=timezone.make_aware(datetime.datetime(2026, 7, 1, 9, 0)),
        attendance_status="scheduled",
    )


@pytest.fixture
def session_cancelled_a(db, tenant_a, employee_a, program_active_a):
    """A cancelled OrientationSession on tenant_a."""
    from apps.hrm.models import OrientationSession
    return OrientationSession.objects.create(
        tenant=tenant_a,
        program=program_active_a,
        employee=employee_a,
        title="Cancelled Session",
        session_type="training",
        scheduled_at=timezone.make_aware(datetime.datetime(2026, 7, 2, 10, 0)),
        attendance_status="cancelled",
    )


@pytest.fixture
def session_b(db, tenant_b, employee_b, program_b):
    """An OrientationSession on tenant_b (IDOR tests)."""
    from apps.hrm.models import OrientationSession
    return OrientationSession.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        title="Globex Session",
        session_type="orientation",
        scheduled_at=timezone.make_aware(datetime.datetime(2026, 8, 1, 9, 0)),
        attendance_status="scheduled",
    )


@pytest.fixture
def template_task_b(db, tenant_b, template_b):
    """An OnboardingTemplateTask on tenant_b (IDOR tests)."""
    from apps.hrm.models import OnboardingTemplateTask
    return OnboardingTemplateTask.objects.create(
        tenant=tenant_b,
        template=template_b,
        title="Globex Setup",
        task_category="it_setup",
        assignee_role="it",
        due_offset_days=0,
        phase="week_1",
    )


# ============================================================
# Model Tests
# ============================================================

class TestOnboardingTemplateModel:
    """Auto-numbering, __str__, unique_together."""

    def test_number_prefix(self, template_a):
        assert template_a.number.startswith("ONBT-")

    def test_number_format(self, template_a):
        assert template_a.number == "ONBT-00001"

    def test_str_includes_number_and_name(self, template_a):
        s = str(template_a)
        assert "ONBT-00001" in s
        assert "Standard Engineer Onboarding" in s

    def test_sequential_numbers_per_tenant(self, tenant_a, designation_a):
        from apps.hrm.models import OnboardingTemplate
        t1 = OnboardingTemplate.objects.create(tenant=tenant_a, name="First")
        t2 = OnboardingTemplate.objects.create(tenant=tenant_a, name="Second")
        assert t1.number == "ONBT-00001"
        assert t2.number == "ONBT-00002"

    def test_numbers_isolated_per_tenant(self, tenant_a, tenant_b):
        from apps.hrm.models import OnboardingTemplate
        ta = OnboardingTemplate.objects.create(tenant=tenant_a, name="A Template")
        tb = OnboardingTemplate.objects.create(tenant=tenant_b, name="B Template")
        assert ta.number == "ONBT-00001"
        assert tb.number == "ONBT-00001"

    def test_unique_together_tenant_name(self, tenant_a, template_a):
        from apps.hrm.models import OnboardingTemplate
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            OnboardingTemplate.objects.create(
                tenant=tenant_a, name="Standard Engineer Onboarding"
            )

    def test_number_not_reassigned_on_resave(self, template_a):
        original = template_a.number
        template_a.description = "updated"
        template_a.save()
        template_a.refresh_from_db()
        assert template_a.number == original

    def test_is_active_default_true(self, tenant_a):
        from apps.hrm.models import OnboardingTemplate
        t = OnboardingTemplate.objects.create(tenant=tenant_a, name="ActiveByDefault")
        assert t.is_active is True


class TestOnboardingTemplateTaskModel:
    """Choices, __str__, unique_together."""

    def test_str(self, template_task_a):
        s = str(template_task_a)
        assert "Setup Laptop" in s

    def test_due_offset_days_default_zero(self, tenant_a, template_a):
        from apps.hrm.models import OnboardingTemplateTask
        tt = OnboardingTemplateTask.objects.create(
            tenant=tenant_a, template=template_a, title="Zero Offset Task",
            task_category="hr_admin", assignee_role="hr", phase="week_1"
        )
        assert tt.due_offset_days == 0

    def test_negative_due_offset_allowed(self, tenant_a, template_a):
        from apps.hrm.models import OnboardingTemplateTask
        tt = OnboardingTemplateTask.objects.create(
            tenant=tenant_a, template=template_a, title="Preboarding Task",
            due_offset_days=-5, phase="preboarding", task_category="hr_admin", assignee_role="hr"
        )
        assert tt.due_offset_days == -5

    def test_unique_together_tenant_template_title(self, tenant_a, template_a, template_task_a):
        from apps.hrm.models import OnboardingTemplateTask
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            OnboardingTemplateTask.objects.create(
                tenant=tenant_a, template=template_a, title="Setup Laptop",
                task_category="it_setup", assignee_role="it", phase="week_1"
            )

    def test_task_category_choices(self):
        from apps.hrm.models import TASK_CATEGORY_CHOICES
        keys = [k for k, _ in TASK_CATEGORY_CHOICES]
        for expected in ("hr_admin", "it_setup", "manager_action", "document_sign", "training", "custom"):
            assert expected in keys

    def test_phase_choices(self):
        from apps.hrm.models import PHASE_CHOICES
        keys = [k for k, _ in PHASE_CHOICES]
        for expected in ("preboarding", "week_1", "month_1", "month_2", "month_3", "ongoing"):
            assert expected in keys


class TestOnboardingProgramModel:
    """Auto-numbering, __str__, progress property."""

    def test_number_prefix(self, program_draft_a):
        assert program_draft_a.number.startswith("ONB-")

    def test_number_format_first(self, program_draft_a):
        assert program_draft_a.number == "ONB-00001"

    def test_str(self, program_draft_a):
        s = str(program_draft_a)
        assert "ONB-00001" in s

    def test_status_default_draft(self, tenant_a, employee_a):
        from apps.hrm.models import OnboardingProgram
        prog = OnboardingProgram.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            start_date=datetime.date(2026, 9, 1),
        )
        assert prog.status == "draft"

    def test_progress_zero_no_tasks(self, program_draft_a):
        assert program_draft_a.progress == 0

    def test_progress_zero_all_pending(self, program_active_a, onb_task_a):
        # Invalidate the memoised cache and recount
        prog = type(program_active_a).objects.get(pk=program_active_a.pk)
        assert prog.progress == 0

    def test_progress_correct_mixed(self, program_active_a):
        """Mark one of two tasks complete — progress = 50%."""
        from apps.hrm.models import OnboardingTask
        tasks = list(OnboardingTask.objects.filter(program=program_active_a))
        assert len(tasks) == 2
        tasks[0].status = "completed"
        tasks[0].save(update_fields=["status", "updated_at"])
        prog = type(program_active_a).objects.get(pk=program_active_a.pk)
        assert prog.progress == 50

    def test_progress_skipped_counts_as_done(self, program_active_a):
        """Skipped tasks count as resolved → all-skipped = 100%."""
        from apps.hrm.models import OnboardingTask
        OnboardingTask.objects.filter(program=program_active_a).update(status="skipped")
        prog = type(program_active_a).objects.get(pk=program_active_a.pk)
        assert prog.progress == 100

    def test_progress_100_all_done(self, program_active_a):
        from apps.hrm.models import OnboardingTask
        OnboardingTask.objects.filter(program=program_active_a).update(status="completed")
        prog = type(program_active_a).objects.get(pk=program_active_a.pk)
        assert prog.progress == 100

    def test_status_choices(self):
        from apps.hrm.models import OnboardingProgram
        keys = [k for k, _ in OnboardingProgram.STATUS_CHOICES]
        assert set(keys) == {"draft", "active", "completed", "cancelled"}

    def test_completed_at_none_on_create(self, program_draft_a):
        assert program_draft_a.completed_at is None

    def test_numbers_isolated_per_tenant(self, tenant_a, tenant_b, employee_a, employee_b):
        from apps.hrm.models import OnboardingProgram
        pA = OnboardingProgram.objects.create(
            tenant=tenant_a, employee=employee_a, start_date=datetime.date(2026, 7, 1)
        )
        pB = OnboardingProgram.objects.create(
            tenant=tenant_b, employee=employee_b, start_date=datetime.date(2026, 7, 1)
        )
        assert pA.number == "ONB-00001"
        assert pB.number == "ONB-00001"


class TestOnboardingTaskModel:
    """Status choices, is_overdue(), __str__."""

    def test_status_choices(self):
        from apps.hrm.models import OnboardingTask
        keys = [k for k, _ in OnboardingTask.STATUS_CHOICES]
        assert set(keys) == {"pending", "in_progress", "completed", "skipped"}

    def test_str(self, onb_task_a):
        s = str(onb_task_a)
        assert "Setup Laptop" in s

    def test_is_overdue_false_when_no_due_date(self, onb_task_a):
        onb_task_a.due_date = None
        assert onb_task_a.is_overdue() is False

    def test_is_overdue_true_past_due(self, onb_task_a):
        onb_task_a.due_date = datetime.date(2020, 1, 1)
        onb_task_a.status = "pending"
        assert onb_task_a.is_overdue() is True

    def test_is_overdue_false_future_due(self, onb_task_a):
        onb_task_a.due_date = datetime.date(2099, 12, 31)
        onb_task_a.status = "pending"
        assert onb_task_a.is_overdue() is False

    def test_is_overdue_false_when_completed(self, onb_task_a):
        onb_task_a.due_date = datetime.date(2020, 1, 1)
        onb_task_a.status = "completed"
        assert onb_task_a.is_overdue() is False

    def test_completed_at_completed_by_null_on_create(self, onb_task_a):
        assert onb_task_a.completed_at is None
        assert onb_task_a.completed_by_id is None


class TestOnboardingDocumentModel:
    """esign_status derivation in save(), __str__."""

    def test_esign_required_true_yields_pending(self, doc_pending_a):
        assert doc_pending_a.esign_status == "pending"

    def test_esign_required_false_yields_not_required(self, doc_not_required_a):
        assert doc_not_required_a.esign_status == "not_required"

    def test_resave_preserves_signed(self, doc_pending_a):
        """Once signed, a re-save must NOT revert to 'pending'."""
        doc_pending_a.esign_status = "signed"
        doc_pending_a.save()
        doc_pending_a.refresh_from_db()
        assert doc_pending_a.esign_status == "signed"

    def test_resave_preserves_declined(self, doc_pending_a):
        doc_pending_a.esign_status = "declined"
        doc_pending_a.save()
        doc_pending_a.refresh_from_db()
        assert doc_pending_a.esign_status == "declined"

    def test_resave_preserves_sent(self, doc_pending_a):
        doc_pending_a.esign_status = "sent"
        doc_pending_a.save()
        doc_pending_a.refresh_from_db()
        assert doc_pending_a.esign_status == "sent"

    def test_str(self, doc_pending_a):
        s = str(doc_pending_a)
        assert "Employment Contract" in s

    def test_esign_status_choices(self):
        from apps.hrm.models import OnboardingDocument
        keys = [k for k, _ in OnboardingDocument.ESIGN_STATUS_CHOICES]
        for expected in ("not_required", "pending", "sent", "viewed", "signed", "declined"):
            assert expected in keys

    def test_document_type_choices(self):
        from apps.hrm.models import OnboardingDocument
        keys = [k for k, _ in OnboardingDocument.DOCUMENT_TYPE_CHOICES]
        for expected in ("employment_contract", "nda", "offer_letter", "id_proof", "policy_acknowledgment"):
            assert expected in keys


class TestAssetAllocationModel:
    """Auto-numbering, __str__, status choices."""

    def test_number_prefix(self, asset_pending_a):
        assert asset_pending_a.number.startswith("AST-")

    def test_number_format_first(self, asset_pending_a):
        assert asset_pending_a.number == "AST-00001"

    def test_str(self, asset_pending_a):
        s = str(asset_pending_a)
        assert "MacBook Pro 14" in s

    def test_status_choices(self):
        from apps.hrm.models import AssetAllocation
        keys = [k for k, _ in AssetAllocation.STATUS_CHOICES]
        assert set(keys) == {"pending", "issued", "returned", "lost", "damaged"}

    def test_returned_at_null_on_create(self, asset_pending_a):
        assert asset_pending_a.returned_at is None

    def test_numbers_isolated_per_tenant(self, tenant_a, tenant_b, employee_a, employee_b):
        from apps.hrm.models import AssetAllocation
        aA = AssetAllocation.objects.create(
            tenant=tenant_a, employee=employee_a, asset_name="Laptop A", asset_category="laptop"
        )
        aB = AssetAllocation.objects.create(
            tenant=tenant_b, employee=employee_b, asset_name="Laptop B", asset_category="laptop"
        )
        assert aA.number == "AST-00001"
        assert aB.number == "AST-00001"


class TestOrientationSessionModel:
    """clean() validation, __str__, attendance status choices."""

    def test_str_with_scheduled_at(self, session_a):
        s = str(session_a)
        assert "Day 1 Orientation" in s
        assert "2026" in s

    def test_attendance_status_default_scheduled(self, session_a):
        assert session_a.attendance_status == "scheduled"

    def test_attendance_status_choices(self):
        from apps.hrm.models import OrientationSession
        keys = [k for k, _ in OrientationSession.ATTENDANCE_STATUS_CHOICES]
        assert set(keys) == {"scheduled", "attended", "missed", "rescheduled", "cancelled"}

    def test_clean_rejects_session_before_program_start(self, program_active_a, employee_a, tenant_a):
        """clean() must raise if scheduled_at.date() < program.start_date (2026-07-01)."""
        from apps.hrm.models import OrientationSession
        session = OrientationSession(
            tenant=tenant_a,
            program=program_active_a,
            employee=employee_a,
            title="Early Session",
            session_type="orientation",
            scheduled_at=timezone.make_aware(datetime.datetime(2026, 6, 30, 10, 0)),  # before 2026-07-01
        )
        with pytest.raises(ValidationError) as exc_info:
            session.clean()
        assert "scheduled_at" in exc_info.value.message_dict

    def test_clean_accepts_same_day_as_program_start(self, program_active_a, employee_a, tenant_a):
        from apps.hrm.models import OrientationSession
        session = OrientationSession(
            tenant=tenant_a,
            program=program_active_a,
            employee=employee_a,
            title="Day One Session",
            session_type="orientation",
            scheduled_at=timezone.make_aware(datetime.datetime(2026, 7, 1, 9, 0)),  # exact start date
        )
        session.clean()  # should not raise

    def test_clean_passes_with_no_program(self, employee_a, tenant_a):
        from apps.hrm.models import OrientationSession
        session = OrientationSession(
            tenant=tenant_a,
            employee=employee_a,
            title="Ad-hoc Session",
            session_type="training",
            scheduled_at=timezone.make_aware(datetime.datetime(2026, 6, 1, 10, 0)),
        )
        session.clean()  # no program → no constraint

    def test_str_without_scheduled_at(self, tenant_a, employee_a):
        from apps.hrm.models import OrientationSession
        session = OrientationSession.objects.create(
            tenant=tenant_a, employee=employee_a,
            title="No-date Session", session_type="orientation"
        )
        assert str(session) == "No-date Session"


# ============================================================
# Service Tests: generate_tasks_from_template
# ============================================================

class TestGenerateTasksFromTemplate:
    """Unit tests for the service function."""

    def test_creates_tasks_for_each_template_task(
        self, program_draft_a, template_task_a, template_task_a2
    ):
        from apps.hrm.services import generate_tasks_from_template
        created = generate_tasks_from_template(program_draft_a)
        assert created == 2

    def test_due_date_equals_start_plus_offset(
        self, program_draft_a, template_task_a, template_task_a2
    ):
        from apps.hrm.services import generate_tasks_from_template
        from apps.hrm.models import OnboardingTask
        generate_tasks_from_template(program_draft_a)

        t0 = OnboardingTask.objects.get(program=program_draft_a, title="Setup Laptop")
        t3 = OnboardingTask.objects.get(program=program_draft_a, title="Complete HR Paperwork")

        # offset=0 → 2026-07-01; offset=3 → 2026-07-04
        assert t0.due_date == datetime.date(2026, 7, 1)
        assert t3.due_date == datetime.date(2026, 7, 4)

    def test_is_idempotent_second_call_returns_zero(
        self, program_draft_a, template_task_a, template_task_a2
    ):
        from apps.hrm.services import generate_tasks_from_template
        generate_tasks_from_template(program_draft_a)
        second = generate_tasks_from_template(program_draft_a)
        assert second == 0

    def test_is_idempotent_no_duplicate_tasks(
        self, program_draft_a, template_task_a, template_task_a2
    ):
        from apps.hrm.services import generate_tasks_from_template
        from apps.hrm.models import OnboardingTask
        generate_tasks_from_template(program_draft_a)
        generate_tasks_from_template(program_draft_a)
        count = OnboardingTask.objects.filter(program=program_draft_a).count()
        assert count == 2

    def test_returns_zero_when_no_template(self, tenant_a, employee_a):
        from apps.hrm.models import OnboardingProgram
        from apps.hrm.services import generate_tasks_from_template
        prog = OnboardingProgram.objects.create(
            tenant=tenant_a, employee=employee_a,
            start_date=datetime.date(2026, 9, 1), status="draft"
        )
        assert generate_tasks_from_template(prog) == 0

    def test_returns_zero_when_template_has_no_tasks(self, tenant_a, employee_a, template_a):
        """Template with zero task lines → 0 tasks created."""
        from apps.hrm.models import OnboardingProgram
        from apps.hrm.services import generate_tasks_from_template
        prog = OnboardingProgram.objects.create(
            tenant=tenant_a, employee=employee_a,
            template=template_a,
            start_date=datetime.date(2026, 9, 1), status="draft"
        )
        # template_a has no task fixtures attached here → 0
        assert generate_tasks_from_template(prog) == 0

    def test_task_inherits_category_and_role(
        self, program_draft_a, template_task_a
    ):
        from apps.hrm.services import generate_tasks_from_template
        from apps.hrm.models import OnboardingTask
        generate_tasks_from_template(program_draft_a)
        task = OnboardingTask.objects.get(program=program_draft_a, title="Setup Laptop")
        assert task.task_category == "it_setup"
        assert task.assignee_role == "it"

    def test_task_tenant_matches_program_tenant(
        self, program_draft_a, template_task_a, tenant_a
    ):
        from apps.hrm.services import generate_tasks_from_template
        from apps.hrm.models import OnboardingTask
        generate_tasks_from_template(program_draft_a)
        tasks = OnboardingTask.objects.filter(program=program_draft_a)
        for t in tasks:
            assert t.tenant_id == tenant_a.pk

    def test_new_template_task_added_after_first_run(
        self, program_draft_a, template_task_a, template_task_a2, tenant_a, template_a
    ):
        """A third template task added after initial generation is picked up on next call."""
        from apps.hrm.models import OnboardingTemplateTask
        from apps.hrm.services import generate_tasks_from_template
        generate_tasks_from_template(program_draft_a)
        # Add a new template task
        OnboardingTemplateTask.objects.create(
            tenant=tenant_a, template=template_a,
            title="Manager Check-in",
            task_category="manager_action", assignee_role="manager",
            due_offset_days=7, phase="week_1"
        )
        third = generate_tasks_from_template(program_draft_a)
        assert third == 1


# ============================================================
# Form Security Tests
# ============================================================

class TestOnboardingDocumentFormSecurity:
    """esign_status cannot be set by form POST; save() always derives it."""

    def test_esign_status_not_a_form_field(self):
        from apps.hrm.forms import OnboardingDocumentForm
        assert "esign_status" not in OnboardingDocumentForm().fields

    def test_signed_at_not_a_form_field(self):
        from apps.hrm.forms import OnboardingDocumentForm
        assert "signed_at" not in OnboardingDocumentForm().fields

    def test_crafted_esign_status_signed_yields_pending(
        self, tenant_a, program_active_a, admin_user
    ):
        """A POST injecting esign_status='signed' must still result in esign_status='pending'."""
        from apps.hrm.forms import OnboardingDocumentForm
        form = OnboardingDocumentForm(
            data={
                "program": program_active_a.pk,
                "document_type": "employment_contract",
                "title": "Crafted Doc",
                "description": "",
                "esign_required": True,
                "esign_status": "signed",  # injection attempt
                "due_date": "",
                "external_ref": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors
        # Manually set tenant like the view does
        instance = form.save(commit=False)
        instance.tenant = tenant_a
        instance.save()
        assert instance.esign_status == "pending"

    def test_crafted_esign_status_not_required_yields_not_required_when_not_required(
        self, tenant_a, program_active_a
    ):
        from apps.hrm.forms import OnboardingDocumentForm
        form = OnboardingDocumentForm(
            data={
                "program": program_active_a.pk,
                "document_type": "id_proof",
                "title": "Crafted Not Required",
                "description": "",
                "esign_required": False,
                "esign_status": "signed",  # injection attempt on a not-required doc
                "due_date": "",
                "external_ref": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors
        instance = form.save(commit=False)
        instance.tenant = tenant_a
        instance.save()
        assert instance.esign_status == "not_required"

    def test_clean_file_rejects_exe(self, tenant_a, program_active_a):
        from apps.hrm.forms import OnboardingDocumentForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_exe = SimpleUploadedFile("virus.exe", b"MZ\x90\x00", content_type="application/octet-stream")
        form = OnboardingDocumentForm(
            data={
                "program": program_active_a.pk,
                "document_type": "custom",
                "title": "Bad File",
                "description": "",
                "esign_required": False,
                "due_date": "",
                "external_ref": "",
            },
            files={"file": fake_exe},
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "file" in form.errors

    def test_clean_file_rejects_oversized(self, tenant_a, program_active_a):
        from apps.hrm.forms import OnboardingDocumentForm, MAX_ONBOARDING_DOC_BYTES
        from django.core.files.uploadedfile import SimpleUploadedFile
        big_file = SimpleUploadedFile("big.pdf", b"A" * (MAX_ONBOARDING_DOC_BYTES + 1), content_type="application/pdf")
        form = OnboardingDocumentForm(
            data={
                "program": program_active_a.pk,
                "document_type": "custom",
                "title": "Big File",
                "description": "",
                "esign_required": False,
                "due_date": "",
                "external_ref": "",
            },
            files={"file": big_file},
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "file" in form.errors

    def test_clean_file_accepts_small_pdf(self, tenant_a, program_active_a):
        from apps.hrm.forms import OnboardingDocumentForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        ok_pdf = SimpleUploadedFile("contract.pdf", b"%PDF-1.4 sample content", content_type="application/pdf")
        form = OnboardingDocumentForm(
            data={
                "program": program_active_a.pk,
                "document_type": "employment_contract",
                "title": "Contract",
                "description": "",
                "esign_required": True,
                "due_date": "",
                "external_ref": "",
            },
            files={"file": ok_pdf},
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors


class TestOrientationSessionFormSecurity:
    """attendance_status cannot be set by form POST."""

    def test_attendance_status_not_a_form_field(self):
        from apps.hrm.forms import OrientationSessionForm
        assert "attendance_status" not in OrientationSessionForm().fields

    def test_crafted_attendance_status_yields_scheduled(
        self, tenant_a, employee_a, program_active_a
    ):
        """A POST injecting attendance_status='attended' must result in 'scheduled'."""
        from apps.hrm.forms import OrientationSessionForm
        # Use a naive datetime string — Django form DateTimeField accepts it; the RuntimeWarning
        # is suppressed below since we are testing form security, not tz handling.
        form = OrientationSessionForm(
            data={
                "program": program_active_a.pk,
                "employee": employee_a.pk,
                "title": "Injected Session",
                "session_type": "orientation",
                "facilitator": "",
                "facilitator_name": "",
                "scheduled_at": "2026-07-05 09:00:00",
                "duration_minutes": "",
                "location": "",
                "meeting_url": "",
                "notes": "",
                "attendance_status": "attended",  # injection attempt
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors
        instance = form.save(commit=False)
        instance.tenant = tenant_a
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            instance.save()
        assert instance.attendance_status == "scheduled"


class TestOnboardingProgramFormSecurity:
    """status cannot be set by form POST; buddy-equals-employee rejected; one-program-per-employee."""

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import OnboardingProgramForm
        assert "status" not in OnboardingProgramForm().fields

    def test_completed_at_not_a_form_field(self):
        from apps.hrm.forms import OnboardingProgramForm
        assert "completed_at" not in OnboardingProgramForm().fields

    def test_clean_rejects_buddy_equals_employee(
        self, tenant_a, employee_a, template_a
    ):
        from apps.hrm.forms import OnboardingProgramForm
        form = OnboardingProgramForm(
            data={
                "employee": employee_a.pk,
                "template": template_a.pk,
                "start_date": "2026-07-01",
                "buddy": employee_a.pk,  # same as employee — invalid
                "welcome_message": "",
                "welcome_video_url": "",
                "first_day_notes": "",
                "notes": "",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "buddy" in form.errors

    def test_clean_rejects_duplicate_program_for_employee(
        self, tenant_a, employee_a, template_a, program_draft_a
    ):
        """A second program for the same employee in the same tenant should fail."""
        from apps.hrm.forms import OnboardingProgramForm
        form = OnboardingProgramForm(
            data={
                "employee": employee_a.pk,
                "template": template_a.pk,
                "start_date": "2026-08-01",
                "buddy": "",
                "welcome_message": "",
                "welcome_video_url": "",
                "first_day_notes": "",
                "notes": "",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "employee" in form.errors

    def test_clean_accepts_different_employee(
        self, tenant_a, template_a, program_draft_a, person_a2
    ):
        """A second program for a DIFFERENT employee is valid."""
        from apps.core.models import Party
        from apps.hrm.models import EmployeeProfile
        from apps.hrm.forms import OnboardingProgramForm
        emp2 = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a2, employee_type="full_time"
        )
        form = OnboardingProgramForm(
            data={
                "employee": emp2.pk,
                "template": template_a.pk,
                "start_date": "2026-08-01",
                "buddy": "",
                "welcome_message": "",
                "welcome_video_url": "",
                "first_day_notes": "",
                "notes": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors


class TestOnboardingTaskFormSecurity:
    """status/completed_at/completed_by are NOT form fields."""

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import OnboardingTaskForm
        assert "status" not in OnboardingTaskForm().fields

    def test_completed_at_not_a_form_field(self):
        from apps.hrm.forms import OnboardingTaskForm
        assert "completed_at" not in OnboardingTaskForm().fields

    def test_completed_by_not_a_form_field(self):
        from apps.hrm.forms import OnboardingTaskForm
        assert "completed_by" not in OnboardingTaskForm().fields


# ============================================================
# View / CRUD Tests
# ============================================================

class TestOnboardingTemplateViews:
    def test_list_200(self, client_a, template_a):
        resp = client_a.get(reverse("hrm:onboardingtemplate_list"))
        assert resp.status_code == 200

    def test_list_contains_own_template(self, client_a, template_a):
        resp = client_a.get(reverse("hrm:onboardingtemplate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert template_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, template_a, template_b):
        resp = client_a.get(reverse("hrm:onboardingtemplate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert template_b.pk not in pks

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:onboardingtemplate_create"))
        assert resp.status_code == 200

    def test_create_post_creates_with_tenant(self, client_a, tenant_a):
        from apps.hrm.models import OnboardingTemplate
        resp = client_a.post(reverse("hrm:onboardingtemplate_create"), {
            "name": "New Template",
            "description": "Test",
            "is_active": "on",
        })
        assert resp.status_code == 302
        assert OnboardingTemplate.objects.filter(tenant=tenant_a, name="New Template").exists()

    def test_detail_200(self, client_a, template_a):
        resp = client_a.get(reverse("hrm:onboardingtemplate_detail", args=[template_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj_context(self, client_a, template_a):
        resp = client_a.get(reverse("hrm:onboardingtemplate_detail", args=[template_a.pk]))
        assert resp.context["obj"].pk == template_a.pk

    def test_edit_get_200(self, client_a, template_a):
        resp = client_a.get(reverse("hrm:onboardingtemplate_edit", args=[template_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_saves(self, client_a, template_a):
        from apps.hrm.models import OnboardingTemplate
        resp = client_a.post(reverse("hrm:onboardingtemplate_edit", args=[template_a.pk]), {
            "name": "Updated Template",
            "description": "Updated",
            "is_active": "on",
        })
        assert resp.status_code == 302
        template_a.refresh_from_db()
        assert template_a.name == "Updated Template"

    def test_delete_removes_row(self, client_a, tenant_a):
        from apps.hrm.models import OnboardingTemplate
        t = OnboardingTemplate.objects.create(tenant=tenant_a, name="Deletable Template")
        pk = t.pk
        resp = client_a.post(reverse("hrm:onboardingtemplate_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OnboardingTemplate.objects.filter(pk=pk).exists()

    def test_anon_redirect_list(self, client):
        resp = client.get(reverse("hrm:onboardingtemplate_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestOnboardingTemplateDeleteGuard:
    """Template in use by a program cannot be deleted."""

    def test_delete_blocked_when_program_exists(self, client_a, template_a, program_draft_a):
        resp = client_a.post(reverse("hrm:onboardingtemplate_delete", args=[template_a.pk]))
        # Redirects to detail (not list) because guard fires
        assert resp.status_code == 302
        from apps.hrm.models import OnboardingTemplate
        assert OnboardingTemplate.objects.filter(pk=template_a.pk).exists()


class TestOnboardingProgramViews:
    def test_list_200(self, client_a, program_draft_a):
        resp = client_a.get(reverse("hrm:onboardingprogram_list"))
        assert resp.status_code == 200

    def test_list_contains_own(self, client_a, program_draft_a):
        resp = client_a.get(reverse("hrm:onboardingprogram_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert program_draft_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, program_draft_a, program_b):
        resp = client_a.get(reverse("hrm:onboardingprogram_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert program_b.pk not in pks

    def test_detail_200(self, client_a, program_draft_a):
        resp = client_a.get(reverse("hrm:onboardingprogram_detail", args=[program_draft_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj(self, client_a, program_draft_a):
        resp = client_a.get(reverse("hrm:onboardingprogram_detail", args=[program_draft_a.pk]))
        assert resp.context["obj"].pk == program_draft_a.pk

    def test_detail_has_progress(self, client_a, program_draft_a):
        resp = client_a.get(reverse("hrm:onboardingprogram_detail", args=[program_draft_a.pk]))
        assert "progress" in resp.context

    def test_edit_get_200(self, client_a, program_draft_a):
        resp = client_a.get(reverse("hrm:onboardingprogram_edit", args=[program_draft_a.pk]))
        assert resp.status_code == 200

    def test_delete_draft_removes_row(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import OnboardingProgram
        prog = OnboardingProgram.objects.create(
            tenant=tenant_a, employee=employee_a,
            start_date=datetime.date(2026, 9, 1), status="draft"
        )
        pk = prog.pk
        resp = client_a.post(reverse("hrm:onboardingprogram_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OnboardingProgram.objects.filter(pk=pk).exists()

    def test_delete_active_blocked(self, client_a, program_active_a):
        from apps.hrm.models import OnboardingProgram
        resp = client_a.post(reverse("hrm:onboardingprogram_delete", args=[program_active_a.pk]))
        assert resp.status_code == 302
        assert OnboardingProgram.objects.filter(pk=program_active_a.pk).exists()


class TestOnboardingProgramWorkflow:
    """Activate / generate-tasks / complete / cancel transitions."""

    def test_activate_changes_status_to_active(self, client_a, program_draft_a, template_task_a):
        from apps.hrm.models import OnboardingProgram
        resp = client_a.post(reverse("hrm:onboardingprogram_activate", args=[program_draft_a.pk]))
        assert resp.status_code == 302
        program_draft_a.refresh_from_db()
        assert program_draft_a.status == "active"

    def test_activate_generates_tasks(self, client_a, program_draft_a, template_task_a, template_task_a2):
        from apps.hrm.models import OnboardingTask
        client_a.post(reverse("hrm:onboardingprogram_activate", args=[program_draft_a.pk]))
        count = OnboardingTask.objects.filter(program=program_draft_a).count()
        assert count == 2

    def test_generate_tasks_idempotent_via_view(self, client_a, program_active_a):
        from apps.hrm.models import OnboardingTask
        # Already has tasks from fixture; generate again
        client_a.post(reverse("hrm:onboardingprogram_generate_tasks", args=[program_active_a.pk]))
        count = OnboardingTask.objects.filter(program=program_active_a).count()
        assert count == 2  # no duplicates

    def test_complete_changes_status(self, client_a, program_active_a):
        resp = client_a.post(reverse("hrm:onboardingprogram_complete", args=[program_active_a.pk]))
        assert resp.status_code == 302
        program_active_a.refresh_from_db()
        assert program_active_a.status == "completed"

    def test_complete_stamps_completed_at(self, client_a, program_active_a):
        client_a.post(reverse("hrm:onboardingprogram_complete", args=[program_active_a.pk]))
        program_active_a.refresh_from_db()
        assert program_active_a.completed_at is not None

    def test_cancel_changes_status(self, client_a, program_active_a):
        resp = client_a.post(reverse("hrm:onboardingprogram_cancel", args=[program_active_a.pk]))
        assert resp.status_code == 302
        program_active_a.refresh_from_db()
        assert program_active_a.status == "cancelled"

    def test_complete_requires_admin(self, member_client, program_active_a):
        """A non-admin member should be redirected/403 and status should stay 'active'."""
        resp = member_client.post(reverse("hrm:onboardingprogram_complete", args=[program_active_a.pk]))
        # @tenant_admin_required redirects to login or 403
        assert resp.status_code in (302, 403)
        program_active_a.refresh_from_db()
        assert program_active_a.status == "active"

    def test_cancel_requires_admin(self, member_client, program_active_a):
        resp = member_client.post(reverse("hrm:onboardingprogram_cancel", args=[program_active_a.pk]))
        assert resp.status_code in (302, 403)
        program_active_a.refresh_from_db()
        assert program_active_a.status == "active"

    def test_activate_no_template_still_activates(self, client_a, tenant_a, employee_a):
        """A program with no template can still be activated (gets an empty task list)."""
        from apps.hrm.models import OnboardingProgram
        prog = OnboardingProgram.objects.create(
            tenant=tenant_a, employee=employee_a,
            start_date=datetime.date(2026, 9, 1), status="draft"
        )
        client_a.post(reverse("hrm:onboardingprogram_activate", args=[prog.pk]))
        prog.refresh_from_db()
        assert prog.status == "active"


class TestOnboardingTaskWorkflow:
    """complete → reopen → skip transitions; completed_by/at stamping."""

    def test_complete_stamps_completed_at_and_by(self, client_a, onb_task_a, admin_user):
        resp = client_a.post(reverse("hrm:onboardingtask_complete", args=[onb_task_a.pk]))
        assert resp.status_code == 302
        onb_task_a.refresh_from_db()
        assert onb_task_a.status == "completed"
        assert onb_task_a.completed_at is not None
        assert onb_task_a.completed_by_id == admin_user.pk

    def test_reopen_clears_completed_at_and_by(self, client_a, onb_task_a):
        # First complete it
        client_a.post(reverse("hrm:onboardingtask_complete", args=[onb_task_a.pk]))
        # Now reopen
        resp = client_a.post(reverse("hrm:onboardingtask_reopen", args=[onb_task_a.pk]))
        assert resp.status_code == 302
        onb_task_a.refresh_from_db()
        assert onb_task_a.status == "pending"
        assert onb_task_a.completed_at is None
        assert onb_task_a.completed_by_id is None

    def test_skip_changes_status(self, client_a, onb_task_a):
        resp = client_a.post(reverse("hrm:onboardingtask_skip", args=[onb_task_a.pk]))
        assert resp.status_code == 302
        onb_task_a.refresh_from_db()
        assert onb_task_a.status == "skipped"

    def test_skip_counts_as_progress(self, client_a, program_active_a, onb_task_a):
        from apps.hrm.models import OnboardingTask
        # Skip all tasks
        for task in OnboardingTask.objects.filter(program=program_active_a):
            client_a.post(reverse("hrm:onboardingtask_skip", args=[task.pk]))
        prog = type(program_active_a).objects.get(pk=program_active_a.pk)
        assert prog.progress == 100

    def test_list_200(self, client_a, onb_task_a):
        resp = client_a.get(reverse("hrm:onboardingtask_list"))
        assert resp.status_code == 200

    def test_detail_200(self, client_a, onb_task_a):
        resp = client_a.get(reverse("hrm:onboardingtask_detail", args=[onb_task_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_row(self, client_a, tenant_a, program_active_a):
        from apps.hrm.models import OnboardingTask
        task = OnboardingTask.objects.create(
            tenant=tenant_a, program=program_active_a,
            title="Disposable Task", task_category="custom", assignee_role="hr", phase="week_1"
        )
        pk = task.pk
        resp = client_a.post(reverse("hrm:onboardingtask_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OnboardingTask.objects.filter(pk=pk).exists()


class TestOnboardingDocumentWorkflow:
    """mark-signed: pending→signed; not_required → error."""

    def test_mark_signed_pending_to_signed(self, client_a, doc_pending_a):
        resp = client_a.post(reverse("hrm:onboardingdocument_mark_signed", args=[doc_pending_a.pk]))
        assert resp.status_code == 302
        doc_pending_a.refresh_from_db()
        assert doc_pending_a.esign_status == "signed"
        assert doc_pending_a.signed_at is not None

    def test_mark_signed_rejected_on_not_required(self, client_a, doc_not_required_a):
        resp = client_a.post(reverse("hrm:onboardingdocument_mark_signed", args=[doc_not_required_a.pk]))
        assert resp.status_code == 302  # redirects to detail with error message
        doc_not_required_a.refresh_from_db()
        # Status must NOT have changed to signed
        assert doc_not_required_a.esign_status == "not_required"

    def test_list_200(self, client_a, doc_pending_a):
        resp = client_a.get(reverse("hrm:onboardingdocument_list"))
        assert resp.status_code == 200

    def test_detail_200(self, client_a, doc_pending_a):
        resp = client_a.get(reverse("hrm:onboardingdocument_detail", args=[doc_pending_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_row(self, client_a, tenant_a, program_active_a):
        from apps.hrm.models import OnboardingDocument
        doc = OnboardingDocument.objects.create(
            tenant=tenant_a, program=program_active_a,
            document_type="custom", title="Disposable Doc", esign_required=False
        )
        pk = doc.pk
        resp = client_a.post(reverse("hrm:onboardingdocument_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OnboardingDocument.objects.filter(pk=pk).exists()


class TestAssetAllocationWorkflow:
    """issue (pending→issued + timestamps), return (issued→returned)."""

    def test_issue_changes_status(self, client_a, asset_pending_a):
        resp = client_a.post(reverse("hrm:assetallocation_issue", args=[asset_pending_a.pk]))
        assert resp.status_code == 302
        asset_pending_a.refresh_from_db()
        assert asset_pending_a.status == "issued"

    def test_issue_stamps_issued_at_and_issued_by(self, client_a, asset_pending_a, admin_user):
        client_a.post(reverse("hrm:assetallocation_issue", args=[asset_pending_a.pk]))
        asset_pending_a.refresh_from_db()
        assert asset_pending_a.issued_at is not None
        assert asset_pending_a.issued_by_id == admin_user.pk

    def test_return_changes_status(self, client_a, asset_issued_a):
        resp = client_a.post(reverse("hrm:assetallocation_return", args=[asset_issued_a.pk]))
        assert resp.status_code == 302
        asset_issued_a.refresh_from_db()
        assert asset_issued_a.status == "returned"

    def test_return_stamps_returned_at(self, client_a, asset_issued_a):
        client_a.post(reverse("hrm:assetallocation_return", args=[asset_issued_a.pk]))
        asset_issued_a.refresh_from_db()
        assert asset_issued_a.returned_at is not None

    def test_delete_blocked_when_issued(self, client_a, asset_issued_a):
        from apps.hrm.models import AssetAllocation
        resp = client_a.post(reverse("hrm:assetallocation_delete", args=[asset_issued_a.pk]))
        assert resp.status_code == 302
        assert AssetAllocation.objects.filter(pk=asset_issued_a.pk).exists()

    def test_delete_allowed_when_pending(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import AssetAllocation
        asset = AssetAllocation.objects.create(
            tenant=tenant_a, employee=employee_a,
            asset_name="Disposable Asset", asset_category="other", status="pending"
        )
        pk = asset.pk
        resp = client_a.post(reverse("hrm:assetallocation_delete", args=[pk]))
        assert resp.status_code == 302
        assert not AssetAllocation.objects.filter(pk=pk).exists()

    def test_list_200(self, client_a, asset_pending_a):
        resp = client_a.get(reverse("hrm:assetallocation_list"))
        assert resp.status_code == 200

    def test_detail_200(self, client_a, asset_pending_a):
        resp = client_a.get(reverse("hrm:assetallocation_detail", args=[asset_pending_a.pk]))
        assert resp.status_code == 200


class TestOrientationSessionWorkflow:
    """mark-attended / mark-missed; cancelled session is immutable."""

    def test_mark_attended(self, client_a, session_a):
        resp = client_a.post(reverse("hrm:orientationsession_mark_attended", args=[session_a.pk]))
        assert resp.status_code == 302
        session_a.refresh_from_db()
        assert session_a.attendance_status == "attended"

    def test_mark_missed(self, client_a, session_a):
        resp = client_a.post(reverse("hrm:orientationsession_mark_missed", args=[session_a.pk]))
        assert resp.status_code == 302
        session_a.refresh_from_db()
        assert session_a.attendance_status == "missed"

    def test_mark_attended_rejected_on_cancelled(self, client_a, session_cancelled_a):
        resp = client_a.post(
            reverse("hrm:orientationsession_mark_attended", args=[session_cancelled_a.pk])
        )
        assert resp.status_code == 302
        session_cancelled_a.refresh_from_db()
        assert session_cancelled_a.attendance_status == "cancelled"

    def test_mark_missed_rejected_on_cancelled(self, client_a, session_cancelled_a):
        resp = client_a.post(
            reverse("hrm:orientationsession_mark_missed", args=[session_cancelled_a.pk])
        )
        assert resp.status_code == 302
        session_cancelled_a.refresh_from_db()
        assert session_cancelled_a.attendance_status == "cancelled"

    def test_list_200(self, client_a, session_a):
        resp = client_a.get(reverse("hrm:orientationsession_list"))
        assert resp.status_code == 200

    def test_detail_200(self, client_a, session_a):
        resp = client_a.get(reverse("hrm:orientationsession_detail", args=[session_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_row(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import OrientationSession
        session = OrientationSession.objects.create(
            tenant=tenant_a, employee=employee_a,
            title="Disposable", session_type="orientation"
        )
        pk = session.pk
        resp = client_a.post(reverse("hrm:orientationsession_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OrientationSession.objects.filter(pk=pk).exists()


class TestOnboardingTemplateTaskViews:
    def test_list_200(self, client_a, template_task_a):
        resp = client_a.get(reverse("hrm:onboardingtemplatetask_list"))
        assert resp.status_code == 200

    def test_detail_200(self, client_a, template_task_a):
        resp = client_a.get(reverse("hrm:onboardingtemplatetask_detail", args=[template_task_a.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:onboardingtemplatetask_create"))
        assert resp.status_code == 200

    def test_create_post_creates(self, client_a, tenant_a, template_a):
        from apps.hrm.models import OnboardingTemplateTask
        resp = client_a.post(reverse("hrm:onboardingtemplatetask_create"), {
            "template": template_a.pk,
            "title": "New Template Task",
            "description": "",
            "task_category": "hr_admin",
            "assignee_role": "hr",
            "due_offset_days": 0,
            "phase": "week_1",
            "order": 1,
            "is_mandatory": "on",
        })
        assert resp.status_code == 302
        assert OnboardingTemplateTask.objects.filter(tenant=tenant_a, title="New Template Task").exists()

    def test_delete_removes_row(self, client_a, tenant_a, template_a):
        from apps.hrm.models import OnboardingTemplateTask
        tt = OnboardingTemplateTask.objects.create(
            tenant=tenant_a, template=template_a, title="Deletable Task",
            task_category="custom", assignee_role="hr", phase="week_1"
        )
        pk = tt.pk
        resp = client_a.post(reverse("hrm:onboardingtemplatetask_delete", args=[pk]))
        assert resp.status_code == 302
        assert not OnboardingTemplateTask.objects.filter(pk=pk).exists()


# ============================================================
# Multi-Tenant IDOR Tests
# ============================================================

class TestOnboardingTemplateIDOR:
    def test_detail_cross_tenant_404(self, client_a, template_b):
        resp = client_a.get(reverse("hrm:onboardingtemplate_detail", args=[template_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, template_b):
        resp = client_a.get(reverse("hrm:onboardingtemplate_edit", args=[template_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, template_b):
        resp = client_a.post(reverse("hrm:onboardingtemplate_delete", args=[template_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_templates(self, client_a, template_a, template_b):
        resp = client_a.get(reverse("hrm:onboardingtemplate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert template_a.pk in pks
        assert template_b.pk not in pks


class TestOnboardingProgramIDOR:
    def test_detail_cross_tenant_404(self, client_a, program_b):
        resp = client_a.get(reverse("hrm:onboardingprogram_detail", args=[program_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, program_b):
        resp = client_a.get(reverse("hrm:onboardingprogram_edit", args=[program_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, program_b):
        resp = client_a.post(reverse("hrm:onboardingprogram_delete", args=[program_b.pk]))
        assert resp.status_code == 404

    def test_activate_cross_tenant_404(self, client_a, program_b):
        resp = client_a.post(reverse("hrm:onboardingprogram_activate", args=[program_b.pk]))
        assert resp.status_code == 404

    def test_complete_cross_tenant_404(self, client_a, program_b):
        resp = client_a.post(reverse("hrm:onboardingprogram_complete", args=[program_b.pk]))
        assert resp.status_code == 404

    def test_cancel_cross_tenant_404(self, client_a, program_b):
        resp = client_a.post(reverse("hrm:onboardingprogram_cancel", args=[program_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_programs(self, client_a, program_draft_a, program_b):
        resp = client_a.get(reverse("hrm:onboardingprogram_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert program_draft_a.pk in pks
        assert program_b.pk not in pks


class TestOnboardingTaskIDOR:
    def test_detail_cross_tenant_404(self, client_a, onb_task_b):
        resp = client_a.get(reverse("hrm:onboardingtask_detail", args=[onb_task_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, onb_task_b):
        resp = client_a.get(reverse("hrm:onboardingtask_edit", args=[onb_task_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, onb_task_b):
        resp = client_a.post(reverse("hrm:onboardingtask_delete", args=[onb_task_b.pk]))
        assert resp.status_code == 404

    def test_complete_cross_tenant_404(self, client_a, onb_task_b):
        resp = client_a.post(reverse("hrm:onboardingtask_complete", args=[onb_task_b.pk]))
        assert resp.status_code == 404

    def test_reopen_cross_tenant_404(self, client_a, onb_task_b):
        resp = client_a.post(reverse("hrm:onboardingtask_reopen", args=[onb_task_b.pk]))
        assert resp.status_code == 404

    def test_skip_cross_tenant_404(self, client_a, onb_task_b):
        resp = client_a.post(reverse("hrm:onboardingtask_skip", args=[onb_task_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_tasks(self, client_a, onb_task_a, onb_task_b):
        resp = client_a.get(reverse("hrm:onboardingtask_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert onb_task_a.pk in pks
        assert onb_task_b.pk not in pks


class TestOnboardingDocumentIDOR:
    def test_detail_cross_tenant_404(self, client_a, doc_b):
        resp = client_a.get(reverse("hrm:onboardingdocument_detail", args=[doc_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, doc_b):
        resp = client_a.get(reverse("hrm:onboardingdocument_edit", args=[doc_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, doc_b):
        resp = client_a.post(reverse("hrm:onboardingdocument_delete", args=[doc_b.pk]))
        assert resp.status_code == 404

    def test_mark_signed_cross_tenant_404(self, client_a, doc_b):
        resp = client_a.post(reverse("hrm:onboardingdocument_mark_signed", args=[doc_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_docs(self, client_a, doc_pending_a, doc_b):
        resp = client_a.get(reverse("hrm:onboardingdocument_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert doc_pending_a.pk in pks
        assert doc_b.pk not in pks


class TestAssetAllocationIDOR:
    def test_detail_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.get(reverse("hrm:assetallocation_detail", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.get(reverse("hrm:assetallocation_edit", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.post(reverse("hrm:assetallocation_delete", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_issue_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.post(reverse("hrm:assetallocation_issue", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_return_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.post(reverse("hrm:assetallocation_return", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_assets(self, client_a, asset_pending_a, asset_b):
        resp = client_a.get(reverse("hrm:assetallocation_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert asset_pending_a.pk in pks
        assert asset_b.pk not in pks


class TestOrientationSessionIDOR:
    def test_detail_cross_tenant_404(self, client_a, session_b):
        resp = client_a.get(reverse("hrm:orientationsession_detail", args=[session_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, session_b):
        resp = client_a.get(reverse("hrm:orientationsession_edit", args=[session_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, session_b):
        resp = client_a.post(reverse("hrm:orientationsession_delete", args=[session_b.pk]))
        assert resp.status_code == 404

    def test_mark_attended_cross_tenant_404(self, client_a, session_b):
        resp = client_a.post(reverse("hrm:orientationsession_mark_attended", args=[session_b.pk]))
        assert resp.status_code == 404

    def test_mark_missed_cross_tenant_404(self, client_a, session_b):
        resp = client_a.post(reverse("hrm:orientationsession_mark_missed", args=[session_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_sessions(self, client_a, session_a, session_b):
        resp = client_a.get(reverse("hrm:orientationsession_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert session_a.pk in pks
        assert session_b.pk not in pks


class TestOnboardingTemplateTaskIDOR:
    def test_detail_cross_tenant_404(self, client_a, template_task_b):
        resp = client_a.get(reverse("hrm:onboardingtemplatetask_detail", args=[template_task_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, template_task_b):
        resp = client_a.get(reverse("hrm:onboardingtemplatetask_edit", args=[template_task_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, template_task_b):
        resp = client_a.post(reverse("hrm:onboardingtemplatetask_delete", args=[template_task_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_tasks(self, client_a, template_task_a, template_task_b):
        resp = client_a.get(reverse("hrm:onboardingtemplatetask_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert template_task_a.pk in pks
        assert template_task_b.pk not in pks


# ============================================================
# Auth / Anonymous Redirect Tests
# ============================================================

class TestOnboardingAnonymousRedirects:
    URLS = [
        "hrm:onboardingtemplate_list",
        "hrm:onboardingtemplate_create",
        "hrm:onboardingprogram_list",
        "hrm:onboardingprogram_create",
        "hrm:onboardingtask_list",
        "hrm:onboardingtask_create",
        "hrm:onboardingdocument_list",
        "hrm:onboardingdocument_create",
        "hrm:assetallocation_list",
        "hrm:assetallocation_create",
        "hrm:orientationsession_list",
        "hrm:orientationsession_create",
        "hrm:onboardingtemplatetask_list",
        "hrm:onboardingtemplatetask_create",
    ]

    @pytest.mark.parametrize("url_name", URLS)
    def test_anon_redirected_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]
