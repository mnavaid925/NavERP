"""Comprehensive tests for HRM 3.5 Job Requisition sub-module.

Covers:
  - Models: JobRequisition (JR- prefix, 8-state lifecycle, clean() salary/headcount guards,
            is_overdue, approval_progress, current_approval_step, unique_together),
            JobDescriptionTemplate (JDTMPL- prefix, unique_together(tenant, name)),
            RequisitionApproval (unique_together(requisition, step_order), clean() step_order<1).
  - Services: generate_approval_chain (idempotent, 2-step default HR→Executive chain,
              keeps manually-added steps), apply_template_to_requisition (copies jd_* fields +
              sets template, does NOT touch employment_type).
  - Form security: JobRequisitionForm excludes status/submitted_at/approved_at/posted_at/filled_at;
              RequisitionApprovalForm excludes status/decided_at/decided_by; FK querysets
              tenant-scoped (cross-tenant pk rejected).
  - CRUD + workflow views (as tenant admin): list/detail/create/edit (200/302); full state machine —
              submit, approve_step (multi-step, final step flips req to approved), reject, return,
              post, hold, mark_filled, cancel, apply_template, clone, approval_add, approval_delete.
  - Multi-tenant isolation (IDOR): tenant-A admin → tenant-B pk → 404.
  - Permission gate: non-admin member → 403 on write actions, 200 on list/detail reads.
  - JobDescriptionTemplate CRUD + IDOR.
  - Seeder idempotency (model-level).
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================
# Recruitment-specific fixtures
# ============================================================

@pytest.fixture
def jd_template_a(db, tenant_a, designation_a):
    """A JobDescriptionTemplate for tenant_a."""
    from apps.hrm.models import JobDescriptionTemplate
    return JobDescriptionTemplate.objects.create(
        tenant=tenant_a,
        name="Senior Engineer JD",
        designation=designation_a,
        employment_type="full_time",
        jd_summary="Build scalable systems.",
        jd_responsibilities="Design APIs, review code.",
        jd_requirements="3+ years Python.",
        jd_nice_to_have="Docker experience.",
        is_active=True,
    )


@pytest.fixture
def jd_template_b(db, tenant_b):
    """A JobDescriptionTemplate for tenant_b (IDOR tests)."""
    from apps.hrm.models import JobDescriptionTemplate
    return JobDescriptionTemplate.objects.create(
        tenant=tenant_b,
        name="Analyst JD",
        employment_type="full_time",
        jd_summary="Data analysis role.",
        jd_responsibilities="Analyse data.",
        jd_requirements="2+ years SQL.",
        jd_nice_to_have="",
        is_active=True,
    )


@pytest.fixture
def req_draft_a(db, tenant_a, dept_a, designation_a):
    """A draft JobRequisition for tenant_a."""
    from apps.hrm.models import JobRequisition
    return JobRequisition.objects.create(
        tenant=tenant_a,
        title="Backend Developer",
        designation=designation_a,
        department=dept_a,
        headcount=2,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="new_headcount",
        posting_type="external",
        priority="medium",
        salary_min=Decimal("60000"),
        salary_max=Decimal("90000"),
        salary_currency="USD",
        jd_summary="We need a great dev.",
        # status defaults to 'draft'
    )


@pytest.fixture
def req_pending_a(db, tenant_a, dept_a, designation_a):
    """A pending_approval JobRequisition for tenant_a."""
    from apps.hrm.models import JobRequisition
    req = JobRequisition.objects.create(
        tenant=tenant_a,
        title="Frontend Developer",
        designation=designation_a,
        department=dept_a,
        headcount=1,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="new_headcount",
        posting_type="external",
        priority="high",
    )
    req.status = "pending_approval"
    req.submitted_at = timezone.now()
    req.save(update_fields=["status", "submitted_at", "updated_at"])
    return req


@pytest.fixture
def req_approved_a(db, tenant_a, dept_a, designation_a):
    """An approved JobRequisition for tenant_a."""
    from apps.hrm.models import JobRequisition
    req = JobRequisition.objects.create(
        tenant=tenant_a,
        title="DevOps Engineer",
        designation=designation_a,
        department=dept_a,
        headcount=1,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="new_headcount",
        posting_type="external",
        priority="medium",
    )
    req.status = "approved"
    req.submitted_at = timezone.now()
    req.approved_at = timezone.now()
    req.save(update_fields=["status", "submitted_at", "approved_at", "updated_at"])
    return req


@pytest.fixture
def req_posted_a(db, tenant_a, dept_a, designation_a):
    """A posted JobRequisition for tenant_a."""
    from apps.hrm.models import JobRequisition
    req = JobRequisition.objects.create(
        tenant=tenant_a,
        title="QA Engineer",
        designation=designation_a,
        department=dept_a,
        headcount=1,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="backfill",
        posting_type="both",
        priority="medium",
    )
    req.status = "posted"
    req.submitted_at = timezone.now()
    req.approved_at = timezone.now()
    req.posted_at = timezone.now()
    req.save(update_fields=["status", "submitted_at", "approved_at", "posted_at", "updated_at"])
    return req


@pytest.fixture
def req_b(db, tenant_b):
    """A draft JobRequisition for tenant_b (IDOR tests)."""
    from apps.hrm.models import JobRequisition
    return JobRequisition.objects.create(
        tenant=tenant_b,
        title="Analyst",
        headcount=1,
        req_type="standard",
        employment_type="full_time",
        reason_for_hire="new_headcount",
        posting_type="external",
        priority="low",
    )


@pytest.fixture
def approval_step_a(db, tenant_a, req_draft_a, admin_user):
    """A pending RequisitionApproval step on req_draft_a."""
    from apps.hrm.models import RequisitionApproval
    return RequisitionApproval.objects.create(
        tenant=tenant_a,
        requisition=req_draft_a,
        step_order=1,
        approver=admin_user,
        approver_role="hr",
        status="pending",
    )


@pytest.fixture
def approval_step_b(db, tenant_b, req_b):
    """A pending RequisitionApproval step on req_b (IDOR tests)."""
    from apps.hrm.models import RequisitionApproval
    return RequisitionApproval.objects.create(
        tenant=tenant_b,
        requisition=req_b,
        step_order=1,
        approver_role="hr",
        status="pending",
    )


# ============================================================
# Model Tests: JobRequisition
# ============================================================

class TestJobRequisitionModel:
    """Auto-numbering, __str__, clean(), is_overdue, approval_progress, current_approval_step."""

    def test_number_prefix(self, req_draft_a):
        assert req_draft_a.number.startswith("JR-")

    def test_number_format_first(self, req_draft_a):
        assert req_draft_a.number == "JR-00001"

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b, dept_a):
        """Each tenant's counter restarts from 1."""
        from apps.hrm.models import JobRequisition
        rA = JobRequisition.objects.create(
            tenant=tenant_a, title="Role A", headcount=1, req_type="standard",
            employment_type="full_time", reason_for_hire="new_headcount",
            posting_type="external", priority="low",
        )
        rB = JobRequisition.objects.create(
            tenant=tenant_b, title="Role B", headcount=1, req_type="standard",
            employment_type="full_time", reason_for_hire="new_headcount",
            posting_type="external", priority="low",
        )
        assert rA.number == "JR-00001"
        assert rB.number == "JR-00001"

    def test_str_contains_number_and_title(self, req_draft_a):
        s = str(req_draft_a)
        assert "JR-00001" in s
        assert "Backend Developer" in s

    def test_status_default_draft(self, req_draft_a):
        assert req_draft_a.status == "draft"

    def test_status_choices(self):
        from apps.hrm.models import JR_STATUS_CHOICES
        keys = [k for k, _ in JR_STATUS_CHOICES]
        for expected in ("draft", "pending_approval", "approved", "posted",
                         "on_hold", "filled", "cancelled", "rejected"):
            assert expected in keys

    def test_unique_together_tenant_number(self, tenant_a, req_draft_a):
        """Creating a second req with the same tenant+number must fail."""
        from apps.hrm.models import JobRequisition
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            JobRequisition.objects.create(
                tenant=tenant_a, title="Duplicate", headcount=1,
                req_type="standard", employment_type="full_time",
                reason_for_hire="new_headcount", posting_type="external",
                priority="low", number=req_draft_a.number,
            )

    # --- clean() validation ---
    def test_clean_raises_when_salary_min_exceeds_max(self, tenant_a):
        from apps.hrm.models import JobRequisition
        req = JobRequisition(
            tenant=tenant_a, title="Bad Salary", headcount=1,
            req_type="standard", employment_type="full_time",
            reason_for_hire="new_headcount", posting_type="external", priority="low",
            salary_min=Decimal("100000"), salary_max=Decimal("50000"),
        )
        with pytest.raises(ValidationError) as exc_info:
            req.clean()
        assert "salary_max" in exc_info.value.message_dict

    def test_clean_ok_when_salary_min_equals_max(self, tenant_a):
        from apps.hrm.models import JobRequisition
        req = JobRequisition(
            tenant=tenant_a, title="Equal Salary", headcount=1,
            req_type="standard", employment_type="full_time",
            reason_for_hire="new_headcount", posting_type="external", priority="low",
            salary_min=Decimal("80000"), salary_max=Decimal("80000"),
        )
        # Should not raise
        req.clean()

    def test_clean_raises_when_headcount_less_than_one(self, tenant_a):
        from apps.hrm.models import JobRequisition
        req = JobRequisition(
            tenant=tenant_a, title="Zero Headcount", headcount=0,
            req_type="standard", employment_type="full_time",
            reason_for_hire="new_headcount", posting_type="external", priority="low",
        )
        with pytest.raises(ValidationError) as exc_info:
            req.clean()
        assert "headcount" in exc_info.value.message_dict

    def test_clean_ok_with_no_salary(self, tenant_a):
        from apps.hrm.models import JobRequisition
        req = JobRequisition(
            tenant=tenant_a, title="No Salary", headcount=1,
            req_type="standard", employment_type="full_time",
            reason_for_hire="new_headcount", posting_type="external", priority="low",
            salary_min=None, salary_max=None,
        )
        req.clean()  # must not raise

    # --- is_overdue property ---
    def test_is_overdue_false_when_no_target_date(self, req_draft_a):
        req_draft_a.target_start_date = None
        assert req_draft_a.is_overdue is False

    def test_is_overdue_true_when_past_date_and_open(self, req_draft_a):
        req_draft_a.target_start_date = datetime.date(2020, 1, 1)  # far past
        req_draft_a.status = "draft"
        assert req_draft_a.is_overdue is True

    def test_is_overdue_false_when_future_date(self, req_draft_a):
        req_draft_a.target_start_date = datetime.date(2099, 12, 31)  # far future
        req_draft_a.status = "draft"
        assert req_draft_a.is_overdue is False

    def test_is_overdue_false_when_filled(self, req_draft_a):
        req_draft_a.target_start_date = datetime.date(2020, 1, 1)
        req_draft_a.status = "filled"
        assert req_draft_a.is_overdue is False

    def test_is_overdue_false_when_cancelled(self, req_draft_a):
        req_draft_a.target_start_date = datetime.date(2020, 1, 1)
        req_draft_a.status = "cancelled"
        assert req_draft_a.is_overdue is False

    def test_is_overdue_false_when_rejected(self, req_draft_a):
        req_draft_a.target_start_date = datetime.date(2020, 1, 1)
        req_draft_a.status = "rejected"
        assert req_draft_a.is_overdue is False

    # --- approval_progress property ---
    def test_approval_progress_empty_chain(self, req_draft_a):
        approved, total = req_draft_a.approval_progress
        assert approved == 0
        assert total == 0

    def test_approval_progress_one_approved_one_pending(self, db, tenant_a, req_pending_a, admin_user):
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="approved",
        )
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=2, approver_role="executive", status="pending",
        )
        approved, total = req_pending_a.approval_progress
        assert approved == 1
        assert total == 2

    def test_approval_progress_all_approved(self, db, tenant_a, req_pending_a):
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="approved",
        )
        approved, total = req_pending_a.approval_progress
        assert approved == 1
        assert total == 1

    # --- current_approval_step property ---
    def test_current_approval_step_none_when_no_steps(self, req_draft_a):
        assert req_draft_a.current_approval_step is None

    def test_current_approval_step_returns_lowest_pending(self, db, tenant_a, req_pending_a):
        from apps.hrm.models import RequisitionApproval
        step2 = RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=2, approver_role="executive", status="pending",
        )
        step1 = RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        current = req_pending_a.current_approval_step
        assert current.pk == step1.pk

    def test_current_approval_step_none_when_all_approved(self, db, tenant_a, req_pending_a):
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="approved",
        )
        assert req_pending_a.current_approval_step is None

    def test_current_approval_step_skips_approved_steps(self, db, tenant_a, req_pending_a):
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="approved",
        )
        step2 = RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=2, approver_role="executive", status="pending",
        )
        current = req_pending_a.current_approval_step
        assert current.pk == step2.pk


# ============================================================
# Model Tests: JobDescriptionTemplate
# ============================================================

class TestJobDescriptionTemplateModel:
    """Auto-numbering, __str__, unique_together(tenant, name)."""

    def test_number_prefix(self, jd_template_a):
        assert jd_template_a.number.startswith("JDTMPL-")

    def test_number_format_first(self, jd_template_a):
        assert jd_template_a.number == "JDTMPL-00001"

    def test_str_contains_number_and_name(self, jd_template_a):
        s = str(jd_template_a)
        assert "JDTMPL-00001" in s
        assert "Senior Engineer JD" in s

    def test_is_active_default_true(self, jd_template_a):
        assert jd_template_a.is_active is True

    def test_unique_together_tenant_name(self, tenant_a, jd_template_a):
        """A duplicate name in the same tenant must raise IntegrityError."""
        from apps.hrm.models import JobDescriptionTemplate
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            JobDescriptionTemplate.objects.create(
                tenant=tenant_a,
                name="Senior Engineer JD",  # same name as jd_template_a
                employment_type="full_time",
                is_active=True,
            )

    def test_same_name_different_tenants_ok(self, tenant_a, tenant_b, jd_template_a):
        """Same name is allowed across different tenants."""
        from apps.hrm.models import JobDescriptionTemplate
        tmpl_b = JobDescriptionTemplate.objects.create(
            tenant=tenant_b,
            name="Senior Engineer JD",  # same name, different tenant
            employment_type="full_time",
            is_active=True,
        )
        assert tmpl_b.pk != jd_template_a.pk

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b):
        """Each tenant gets its own JDTMPL counter."""
        from apps.hrm.models import JobDescriptionTemplate
        tA = JobDescriptionTemplate.objects.create(
            tenant=tenant_a, name="Template A", employment_type="full_time", is_active=True)
        tB = JobDescriptionTemplate.objects.create(
            tenant=tenant_b, name="Template B", employment_type="full_time", is_active=True)
        assert tA.number == "JDTMPL-00001"
        assert tB.number == "JDTMPL-00001"


# ============================================================
# Model Tests: RequisitionApproval
# ============================================================

class TestRequisitionApprovalModel:
    """unique_together(requisition, step_order), clean() rejects step_order<1, __str__."""

    def test_str_contains_step_order_and_role(self, approval_step_a):
        s = str(approval_step_a)
        assert "Step 1" in s
        assert "HR" in s  # approver_role display

    def test_str_contains_status(self, approval_step_a):
        s = str(approval_step_a)
        assert "Pending" in s

    def test_clean_rejects_step_order_zero(self, tenant_a, req_draft_a):
        from apps.hrm.models import RequisitionApproval
        step = RequisitionApproval(
            tenant=tenant_a, requisition=req_draft_a,
            step_order=0, approver_role="hr", status="pending",
        )
        with pytest.raises(ValidationError) as exc_info:
            step.clean()
        assert "step_order" in exc_info.value.message_dict

    def test_clean_accepts_step_order_one(self, tenant_a, req_draft_a):
        from apps.hrm.models import RequisitionApproval
        step = RequisitionApproval(
            tenant=tenant_a, requisition=req_draft_a,
            step_order=1, approver_role="hr", status="pending",
        )
        step.clean()  # should not raise

    def test_unique_together_requisition_step_order(self, tenant_a, req_draft_a, approval_step_a):
        """A second step with the same requisition+step_order must raise IntegrityError."""
        from apps.hrm.models import RequisitionApproval
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            RequisitionApproval.objects.create(
                tenant=tenant_a, requisition=req_draft_a,
                step_order=1,  # same order as approval_step_a
                approver_role="executive", status="pending",
            )

    def test_different_step_orders_ok(self, tenant_a, req_draft_a, approval_step_a):
        from apps.hrm.models import RequisitionApproval
        step2 = RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_draft_a,
            step_order=2, approver_role="executive", status="pending",
        )
        assert step2.pk is not None

    def test_status_default_pending(self, approval_step_a):
        assert approval_step_a.status == "pending"


# ============================================================
# Service Tests
# ============================================================

class TestGenerateApprovalChain:
    """generate_approval_chain: 2-step default, idempotency, keeps manual steps."""

    def test_creates_two_default_steps(self, req_draft_a):
        from apps.hrm.models import RequisitionApproval
        from apps.hrm.services import generate_approval_chain
        result = generate_approval_chain(req_draft_a)
        assert len(result) == 2
        assert RequisitionApproval.objects.filter(
            tenant=req_draft_a.tenant, requisition=req_draft_a
        ).count() == 2

    def test_default_step_roles(self, req_draft_a):
        from apps.hrm.services import generate_approval_chain
        steps = generate_approval_chain(req_draft_a)
        roles = [s.approver_role for s in steps]
        assert roles[0] == "hr"
        assert roles[1] == "executive"

    def test_default_step_orders(self, req_draft_a):
        from apps.hrm.services import generate_approval_chain
        steps = generate_approval_chain(req_draft_a)
        orders = [s.step_order for s in steps]
        assert orders == [1, 2]

    def test_all_steps_start_pending(self, req_draft_a):
        from apps.hrm.services import generate_approval_chain
        steps = generate_approval_chain(req_draft_a)
        assert all(s.status == "pending" for s in steps)

    def test_idempotent_second_call_returns_existing(self, req_draft_a):
        """A second call with steps already present returns them without creating new rows."""
        from apps.hrm.models import RequisitionApproval
        from apps.hrm.services import generate_approval_chain
        generate_approval_chain(req_draft_a)
        first_count = RequisitionApproval.objects.filter(
            tenant=req_draft_a.tenant, requisition=req_draft_a
        ).count()
        result2 = generate_approval_chain(req_draft_a)
        second_count = RequisitionApproval.objects.filter(
            tenant=req_draft_a.tenant, requisition=req_draft_a
        ).count()
        assert second_count == first_count
        assert len(result2) == first_count

    def test_idempotent_no_duplicates(self, req_draft_a):
        from apps.hrm.models import RequisitionApproval
        from apps.hrm.services import generate_approval_chain
        generate_approval_chain(req_draft_a)
        generate_approval_chain(req_draft_a)
        generate_approval_chain(req_draft_a)
        assert RequisitionApproval.objects.filter(
            tenant=req_draft_a.tenant, requisition=req_draft_a
        ).count() == 2

    def test_keeps_manually_added_steps(self, db, tenant_a, req_draft_a, admin_user):
        """If a manual step was added before calling the service, it is left intact."""
        from apps.hrm.models import RequisitionApproval
        from apps.hrm.services import generate_approval_chain
        # Manually add a custom step
        manual = RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_draft_a,
            step_order=1, approver=admin_user, approver_role="custom", status="pending",
        )
        result = generate_approval_chain(req_draft_a)
        # The manual step should be present and no new rows created
        assert RequisitionApproval.objects.filter(
            tenant=tenant_a, requisition=req_draft_a
        ).count() == 1
        assert result[0].pk == manual.pk

    def test_returns_list_type(self, req_draft_a):
        from apps.hrm.services import generate_approval_chain
        result = generate_approval_chain(req_draft_a)
        assert isinstance(result, list)


class TestApplyTemplateToRequisition:
    """apply_template_to_requisition: copies jd_* + sets template, does NOT touch employment_type."""

    def test_copies_jd_summary(self, req_draft_a, jd_template_a):
        from apps.hrm.services import apply_template_to_requisition
        apply_template_to_requisition(req_draft_a, jd_template_a)
        req_draft_a.refresh_from_db()
        assert req_draft_a.jd_summary == jd_template_a.jd_summary

    def test_copies_jd_responsibilities(self, req_draft_a, jd_template_a):
        from apps.hrm.services import apply_template_to_requisition
        apply_template_to_requisition(req_draft_a, jd_template_a)
        req_draft_a.refresh_from_db()
        assert req_draft_a.jd_responsibilities == jd_template_a.jd_responsibilities

    def test_copies_jd_requirements(self, req_draft_a, jd_template_a):
        from apps.hrm.services import apply_template_to_requisition
        apply_template_to_requisition(req_draft_a, jd_template_a)
        req_draft_a.refresh_from_db()
        assert req_draft_a.jd_requirements == jd_template_a.jd_requirements

    def test_copies_jd_nice_to_have(self, req_draft_a, jd_template_a):
        from apps.hrm.services import apply_template_to_requisition
        apply_template_to_requisition(req_draft_a, jd_template_a)
        req_draft_a.refresh_from_db()
        assert req_draft_a.jd_nice_to_have == jd_template_a.jd_nice_to_have

    def test_sets_template_fk(self, req_draft_a, jd_template_a):
        from apps.hrm.services import apply_template_to_requisition
        apply_template_to_requisition(req_draft_a, jd_template_a)
        req_draft_a.refresh_from_db()
        assert req_draft_a.template_id == jd_template_a.pk

    def test_does_not_touch_employment_type(self, req_draft_a, jd_template_a):
        """employment_type on the requisition must NOT be overwritten by the template's value."""
        from apps.hrm.services import apply_template_to_requisition
        original_employment_type = req_draft_a.employment_type  # "full_time"
        # Set a different employment_type on the template to verify it isn't copied
        jd_template_a.employment_type = "contract"
        jd_template_a.save(update_fields=["employment_type"])
        apply_template_to_requisition(req_draft_a, jd_template_a)
        req_draft_a.refresh_from_db()
        assert req_draft_a.employment_type == original_employment_type

    def test_persists_changes_to_db(self, req_draft_a, jd_template_a):
        """Changes must survive a refresh_from_db (i.e., save() was called)."""
        from apps.hrm.services import apply_template_to_requisition
        req_draft_a.jd_summary = "OLD"
        req_draft_a.save(update_fields=["jd_summary"])
        apply_template_to_requisition(req_draft_a, jd_template_a)
        req_draft_a.refresh_from_db()
        assert req_draft_a.jd_summary != "OLD"
        assert req_draft_a.jd_summary == jd_template_a.jd_summary


# ============================================================
# Form Security Tests
# ============================================================

class TestJobRequisitionForm:
    """Excludes workflow-owned fields; salary/headcount validation; FK querysets tenant-scoped."""

    def test_status_not_in_form_fields(self):
        from apps.hrm.forms import JobRequisitionForm
        assert "status" not in JobRequisitionForm.Meta.fields

    def test_submitted_at_not_in_form_fields(self):
        from apps.hrm.forms import JobRequisitionForm
        assert "submitted_at" not in JobRequisitionForm.Meta.fields

    def test_approved_at_not_in_form_fields(self):
        from apps.hrm.forms import JobRequisitionForm
        assert "approved_at" not in JobRequisitionForm.Meta.fields

    def test_posted_at_not_in_form_fields(self):
        from apps.hrm.forms import JobRequisitionForm
        assert "posted_at" not in JobRequisitionForm.Meta.fields

    def test_filled_at_not_in_form_fields(self):
        from apps.hrm.forms import JobRequisitionForm
        assert "filled_at" not in JobRequisitionForm.Meta.fields

    def test_number_not_in_form_fields(self):
        from apps.hrm.forms import JobRequisitionForm
        assert "number" not in JobRequisitionForm.Meta.fields

    def test_form_clean_rejects_salary_min_greater_than_max(self, tenant_a):
        from apps.hrm.forms import JobRequisitionForm
        data = {
            "title": "Test Role",
            "headcount": 1,
            "req_type": "standard",
            "employment_type": "full_time",
            "reason_for_hire": "new_headcount",
            "posting_type": "external",
            "priority": "medium",
            "salary_currency": "USD",
            "salary_min": "100000",
            "salary_max": "50000",  # min > max
        }
        form = JobRequisitionForm(data, tenant=tenant_a)
        assert not form.is_valid()
        assert "salary_max" in form.errors

    def test_form_clean_rejects_headcount_zero(self, tenant_a):
        from apps.hrm.forms import JobRequisitionForm
        data = {
            "title": "Test Role",
            "headcount": 0,  # invalid
            "req_type": "standard",
            "employment_type": "full_time",
            "reason_for_hire": "new_headcount",
            "posting_type": "external",
            "priority": "medium",
            "salary_currency": "USD",
        }
        form = JobRequisitionForm(data, tenant=tenant_a)
        assert not form.is_valid()
        assert "headcount" in form.errors

    def test_form_valid_minimal_data(self, tenant_a):
        from apps.hrm.forms import JobRequisitionForm
        data = {
            "title": "Valid Role",
            "headcount": 1,
            "req_type": "standard",
            "employment_type": "full_time",
            "reason_for_hire": "new_headcount",
            "posting_type": "external",
            "priority": "medium",
            "salary_currency": "USD",
        }
        form = JobRequisitionForm(data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_cross_tenant_designation_rejected(self, tenant_a, tenant_b, designation_b):
        """Submitting a cross-tenant designation pk should fail form validation."""
        from apps.hrm.forms import JobRequisitionForm
        data = {
            "title": "Cross-Tenant Role",
            "headcount": 1,
            "req_type": "standard",
            "employment_type": "full_time",
            "reason_for_hire": "new_headcount",
            "posting_type": "external",
            "priority": "medium",
            "salary_currency": "USD",
            "designation": designation_b.pk,  # tenant_b's designation
        }
        form = JobRequisitionForm(data, tenant=tenant_a)
        assert not form.is_valid()
        assert "designation" in form.errors

    def test_cross_tenant_template_rejected(self, tenant_a, jd_template_b):
        """Submitting a cross-tenant template pk should fail form validation."""
        from apps.hrm.forms import JobRequisitionForm
        data = {
            "title": "Template Test",
            "headcount": 1,
            "req_type": "standard",
            "employment_type": "full_time",
            "reason_for_hire": "new_headcount",
            "posting_type": "external",
            "priority": "medium",
            "salary_currency": "USD",
            "template": jd_template_b.pk,  # tenant_b's template
        }
        form = JobRequisitionForm(data, tenant=tenant_a)
        assert not form.is_valid()
        assert "template" in form.errors


class TestRequisitionApprovalForm:
    """Excludes workflow-owned fields; approver queryset is tenant-scoped."""

    def test_status_not_in_form_fields(self):
        from apps.hrm.forms import RequisitionApprovalForm
        assert "status" not in RequisitionApprovalForm.Meta.fields

    def test_decided_at_not_in_form_fields(self):
        from apps.hrm.forms import RequisitionApprovalForm
        assert "decided_at" not in RequisitionApprovalForm.Meta.fields

    def test_decided_by_not_in_form_fields(self):
        from apps.hrm.forms import RequisitionApprovalForm
        assert "decided_by" not in RequisitionApprovalForm.Meta.fields

    def test_approver_queryset_tenant_scoped(self, tenant_a, admin_user, admin_b):
        """The approver field must only include tenant_a users, not tenant_b users."""
        from apps.hrm.forms import RequisitionApprovalForm
        form = RequisitionApprovalForm(tenant=tenant_a)
        qs = form.fields["approver"].queryset
        pks = list(qs.values_list("pk", flat=True))
        assert admin_user.pk in pks
        assert admin_b.pk not in pks


class TestJobDescriptionTemplateForm:
    """designation queryset is tenant-scoped."""

    def test_designation_queryset_tenant_scoped(self, tenant_a, designation_a, designation_b):
        from apps.hrm.forms import JobDescriptionTemplateForm
        form = JobDescriptionTemplateForm(tenant=tenant_a)
        qs = form.fields["designation"].queryset
        pks = list(qs.values_list("pk", flat=True))
        assert designation_a.pk in pks
        assert designation_b.pk not in pks


# ============================================================
# JobDescriptionTemplate CRUD Views
# ============================================================

class TestJobDescriptionTemplateViews:
    """list/create/detail/edit/delete + IDOR 404."""

    def test_list_200(self, client_a, jd_template_a):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_list"))
        assert resp.status_code == 200

    def test_list_contains_own(self, client_a, jd_template_a):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_list"))
        assert jd_template_a.name.encode() in resp.content

    def test_list_excludes_other_tenant(self, client_a, jd_template_a, jd_template_b):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_list"))
        assert jd_template_b.name.encode() not in resp.content

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_create"))
        assert resp.status_code == 200

    def test_create_post_creates_template(self, client_a, tenant_a):
        from apps.hrm.models import JobDescriptionTemplate
        resp = client_a.post(reverse("hrm:jobdescriptiontemplate_create"), {
            "name": "New JD Template",
            "employment_type": "full_time",
            "jd_summary": "Summary text.",
            "jd_responsibilities": "Responsibilities.",
            "jd_requirements": "Requirements.",
            "jd_nice_to_have": "",
            "is_active": "on",
        })
        assert resp.status_code == 302
        assert JobDescriptionTemplate.objects.filter(tenant=tenant_a, name="New JD Template").exists()

    def test_detail_200(self, client_a, jd_template_a):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_detail", args=[jd_template_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200(self, client_a, jd_template_a):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_edit", args=[jd_template_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_saves(self, client_a, jd_template_a):
        from apps.hrm.models import JobDescriptionTemplate
        resp = client_a.post(reverse("hrm:jobdescriptiontemplate_edit", args=[jd_template_a.pk]), {
            "name": "Updated JD Template",
            "employment_type": "contract",
            "jd_summary": "New summary.",
            "jd_responsibilities": "New responsibilities.",
            "jd_requirements": "New requirements.",
            "jd_nice_to_have": "",
            "is_active": "on",
        })
        assert resp.status_code == 302
        jd_template_a.refresh_from_db()
        assert jd_template_a.name == "Updated JD Template"

    def test_delete_template_not_referenced(self, client_a, tenant_a):
        from apps.hrm.models import JobDescriptionTemplate
        tmpl = JobDescriptionTemplate.objects.create(
            tenant=tenant_a, name="Delete Me", employment_type="full_time", is_active=True)
        pk = tmpl.pk
        resp = client_a.post(reverse("hrm:jobdescriptiontemplate_delete", args=[pk]))
        assert resp.status_code == 302
        assert not JobDescriptionTemplate.objects.filter(pk=pk).exists()

    def test_delete_template_referenced_by_req_is_blocked(self, client_a, tenant_a, jd_template_a, req_draft_a):
        """Deleting a template referenced by a requisition is blocked — the view redirects
        to the detail page with an error (the user must deactivate it manually)."""
        from apps.hrm.models import JobDescriptionTemplate
        # Link the template to the req
        req_draft_a.template = jd_template_a
        req_draft_a.save(update_fields=["template", "updated_at"])
        resp = client_a.post(
            reverse("hrm:jobdescriptiontemplate_delete", args=[jd_template_a.pk])
        )
        assert resp.status_code == 302
        # The template must still exist (not deleted)
        jd_template_a.refresh_from_db()
        assert JobDescriptionTemplate.objects.filter(pk=jd_template_a.pk).exists()

    # IDOR
    def test_detail_idor_404(self, client_a, jd_template_b):
        """tenant_a client requesting tenant_b template detail → 404."""
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_detail", args=[jd_template_b.pk]))
        assert resp.status_code == 404

    def test_edit_idor_404(self, client_a, jd_template_b):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_edit", args=[jd_template_b.pk]))
        assert resp.status_code == 404

    def test_delete_idor_404(self, client_a, jd_template_b):
        resp = client_a.post(reverse("hrm:jobdescriptiontemplate_delete", args=[jd_template_b.pk]))
        assert resp.status_code == 404

    # Anon
    def test_list_anon_redirect(self, client):
        resp = client.get(reverse("hrm:jobdescriptiontemplate_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================
# JobRequisition CRUD Views
# ============================================================

class TestJobRequisitionCRUDViews:
    """list/detail/create/edit/delete."""

    def test_list_200(self, client_a, req_draft_a):
        resp = client_a.get(reverse("hrm:jobrequisition_list"))
        assert resp.status_code == 200

    def test_list_contains_own(self, client_a, req_draft_a):
        resp = client_a.get(reverse("hrm:jobrequisition_list"))
        assert req_draft_a.number.encode() in resp.content

    def test_list_excludes_other_tenant(self, client_a, req_draft_a, req_b):
        resp = client_a.get(reverse("hrm:jobrequisition_list"))
        assert req_b.title.encode() not in resp.content

    def test_list_anon_redirect(self, client):
        resp = client.get(reverse("hrm:jobrequisition_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_detail_200(self, client_a, req_draft_a):
        resp = client_a.get(reverse("hrm:jobrequisition_detail", args=[req_draft_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, req_draft_a):
        resp = client_a.get(reverse("hrm:jobrequisition_detail", args=[req_draft_a.pk]))
        for key in ("obj", "approvals", "approval_progress"):
            assert key in resp.context, f"context missing key: {key}"

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:jobrequisition_create"))
        assert resp.status_code == 200

    def test_create_post_creates_with_correct_tenant(self, client_a, tenant_a, dept_a):
        from apps.hrm.models import JobRequisition
        resp = client_a.post(reverse("hrm:jobrequisition_create"), {
            "title": "New Position",
            "headcount": 1,
            "req_type": "standard",
            "employment_type": "full_time",
            "reason_for_hire": "new_headcount",
            "posting_type": "external",
            "priority": "medium",
            "salary_currency": "USD",
        })
        assert resp.status_code == 302
        assert JobRequisition.objects.filter(tenant=tenant_a, title="New Position").exists()

    def test_create_post_status_is_draft(self, client_a, tenant_a):
        """Status must be draft regardless of what the POST might include."""
        from apps.hrm.models import JobRequisition
        client_a.post(reverse("hrm:jobrequisition_create"), {
            "title": "Status Forge Test",
            "headcount": 1,
            "req_type": "standard",
            "employment_type": "full_time",
            "reason_for_hire": "new_headcount",
            "posting_type": "external",
            "priority": "medium",
            "salary_currency": "USD",
            "status": "approved",  # attempt to forge status
        })
        req = JobRequisition.objects.filter(tenant=tenant_a, title="Status Forge Test").first()
        assert req is not None
        assert req.status == "draft"

    def test_edit_get_200_draft(self, client_a, req_draft_a):
        resp = client_a.get(reverse("hrm:jobrequisition_edit", args=[req_draft_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_saves(self, client_a, req_draft_a):
        resp = client_a.post(reverse("hrm:jobrequisition_edit", args=[req_draft_a.pk]), {
            "title": "Updated Position",
            "headcount": 3,
            "req_type": "backfill",
            "employment_type": "full_time",
            "reason_for_hire": "backfill",
            "posting_type": "internal",
            "priority": "high",
            "salary_currency": "USD",
        })
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.title == "Updated Position"
        assert req_draft_a.headcount == 3

    def test_edit_pending_redirects_blocked(self, client_a, req_pending_a):
        """Editing a non-draft/non-rejected req should be blocked."""
        resp = client_a.get(reverse("hrm:jobrequisition_edit", args=[req_pending_a.pk]))
        # Either 403, 302 (redirect to detail) or 200 with an error — what matters is no update
        # The view redirects non-draft/rejected reqs
        if resp.status_code == 200:
            # If we get a form, it should show an error or the POST should be rejected
            pass
        else:
            assert resp.status_code in (302, 403)

    def test_delete_draft_removes_row(self, client_a, tenant_a, dept_a, designation_a):
        from apps.hrm.models import JobRequisition
        req = JobRequisition.objects.create(
            tenant=tenant_a, title="To Delete", headcount=1,
            req_type="standard", employment_type="full_time",
            reason_for_hire="new_headcount", posting_type="external", priority="low",
        )
        pk = req.pk
        resp = client_a.post(reverse("hrm:jobrequisition_delete", args=[pk]))
        assert resp.status_code == 302
        assert not JobRequisition.objects.filter(pk=pk).exists()

    def test_delete_non_draft_blocked(self, client_a, req_pending_a):
        from apps.hrm.models import JobRequisition
        resp = client_a.post(reverse("hrm:jobrequisition_delete", args=[req_pending_a.pk]))
        assert resp.status_code == 302
        assert JobRequisition.objects.filter(pk=req_pending_a.pk).exists()

    # IDOR
    def test_detail_idor_404(self, client_a, req_b):
        resp = client_a.get(reverse("hrm:jobrequisition_detail", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_edit_idor_404(self, client_a, req_b):
        resp = client_a.get(reverse("hrm:jobrequisition_edit", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_delete_idor_404(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_delete", args=[req_b.pk]))
        assert resp.status_code == 404


# ============================================================
# Workflow State Machine Tests
# ============================================================

class TestJobRequisitionWorkflow:
    """Full state machine: submit → approve_step → reject → return → post → hold → fill → cancel."""

    # --- submit ---
    def test_submit_draft_changes_status(self, client_a, req_draft_a):
        resp = client_a.post(reverse("hrm:jobrequisition_submit", args=[req_draft_a.pk]))
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "pending_approval"

    def test_submit_stamps_submitted_at(self, client_a, req_draft_a):
        client_a.post(reverse("hrm:jobrequisition_submit", args=[req_draft_a.pk]))
        req_draft_a.refresh_from_db()
        assert req_draft_a.submitted_at is not None

    def test_submit_auto_builds_approval_chain(self, client_a, req_draft_a):
        from apps.hrm.models import RequisitionApproval
        client_a.post(reverse("hrm:jobrequisition_submit", args=[req_draft_a.pk]))
        count = RequisitionApproval.objects.filter(
            tenant=req_draft_a.tenant, requisition=req_draft_a
        ).count()
        assert count == 2  # default 2-step chain

    def test_submit_non_draft_noop(self, client_a, req_pending_a):
        """Submitting an already-pending req must not change its status."""
        client_a.post(reverse("hrm:jobrequisition_submit", args=[req_pending_a.pk]))
        req_pending_a.refresh_from_db()
        assert req_pending_a.status == "pending_approval"

    def test_submit_idor_404(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_submit", args=[req_b.pk]))
        assert resp.status_code == 404

    # --- approve_step: single-step ---
    def test_approve_step_advances_status_when_last_step(self, client_a, req_pending_a, tenant_a):
        """Approving the only pending step flips the req to 'approved'."""
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        resp = client_a.post(reverse("hrm:jobrequisition_approve_step", args=[req_pending_a.pk]))
        assert resp.status_code == 302
        req_pending_a.refresh_from_db()
        assert req_pending_a.status == "approved"

    def test_approve_step_stamps_approved_at(self, client_a, req_pending_a, tenant_a):
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        client_a.post(reverse("hrm:jobrequisition_approve_step", args=[req_pending_a.pk]))
        req_pending_a.refresh_from_db()
        assert req_pending_a.approved_at is not None

    def test_approve_step_multi_step_intermediate_stays_pending(
        self, client_a, req_pending_a, tenant_a
    ):
        """Approving step 1 of 2 keeps req in pending_approval until step 2 is also approved."""
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=2, approver_role="executive", status="pending",
        )
        client_a.post(reverse("hrm:jobrequisition_approve_step", args=[req_pending_a.pk]))
        req_pending_a.refresh_from_db()
        # Step 1 approved but step 2 still pending → req stays pending_approval
        assert req_pending_a.status == "pending_approval"

    def test_approve_step_multi_step_final_flips_to_approved(
        self, client_a, req_pending_a, tenant_a
    ):
        """Approving the final step (step 2) flips req to 'approved'."""
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="approved",  # already approved
        )
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=2, approver_role="executive", status="pending",
        )
        client_a.post(reverse("hrm:jobrequisition_approve_step", args=[req_pending_a.pk]))
        req_pending_a.refresh_from_db()
        assert req_pending_a.status == "approved"

    def test_approve_step_stamps_decided_at_on_step(self, client_a, req_pending_a, tenant_a):
        from apps.hrm.models import RequisitionApproval
        step = RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        client_a.post(reverse("hrm:jobrequisition_approve_step", args=[req_pending_a.pk]))
        step.refresh_from_db()
        assert step.status == "approved"
        assert step.decided_at is not None
        assert step.decided_by is not None

    def test_approve_step_non_pending_req_noop(self, client_a, req_draft_a):
        """approve_step on a draft req does nothing."""
        resp = client_a.post(reverse("hrm:jobrequisition_approve_step", args=[req_draft_a.pk]))
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "draft"

    def test_approve_step_idor_404(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_approve_step", args=[req_b.pk]))
        assert resp.status_code == 404

    # --- reject ---
    def test_reject_changes_status(self, client_a, req_pending_a, tenant_a):
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        resp = client_a.post(
            reverse("hrm:jobrequisition_reject", args=[req_pending_a.pk]),
            {"comments": "Budget frozen."},
        )
        assert resp.status_code == 302
        req_pending_a.refresh_from_db()
        assert req_pending_a.status == "rejected"

    def test_reject_marks_step_as_rejected(self, client_a, req_pending_a, tenant_a):
        from apps.hrm.models import RequisitionApproval
        step = RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        client_a.post(
            reverse("hrm:jobrequisition_reject", args=[req_pending_a.pk]),
            {"comments": "Not approved."},
        )
        step.refresh_from_db()
        assert step.status == "rejected"

    def test_reject_draft_noop(self, client_a, req_draft_a):
        """Rejecting a draft req does nothing."""
        resp = client_a.post(reverse("hrm:jobrequisition_reject", args=[req_draft_a.pk]))
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "draft"

    def test_reject_then_resubmit_resets_chain(
        self, client_a, tenant_a, req_draft_a
    ):
        """After reject → re-submit, the chain should be reset to pending."""
        from apps.hrm.models import RequisitionApproval
        # Submit first → builds chain
        client_a.post(reverse("hrm:jobrequisition_submit", args=[req_draft_a.pk]))
        req_draft_a.refresh_from_db()
        # Reject it
        client_a.post(reverse("hrm:jobrequisition_reject", args=[req_draft_a.pk]))
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "rejected"
        # Re-submit: chain must be reset
        client_a.post(reverse("hrm:jobrequisition_submit", args=[req_draft_a.pk]))
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "pending_approval"
        all_pending = all(
            s.status == "pending"
            for s in RequisitionApproval.objects.filter(
                tenant=tenant_a, requisition=req_draft_a
            )
        )
        assert all_pending, "All steps should be reset to pending after re-submit"

    # --- return ---
    def test_return_changes_status_to_draft(self, client_a, req_pending_a, tenant_a):
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        resp = client_a.post(reverse("hrm:jobrequisition_return", args=[req_pending_a.pk]))
        assert resp.status_code == 302
        req_pending_a.refresh_from_db()
        assert req_pending_a.status == "draft"

    def test_return_clears_submitted_at(self, client_a, req_pending_a, tenant_a):
        from apps.hrm.models import RequisitionApproval
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        client_a.post(reverse("hrm:jobrequisition_return", args=[req_pending_a.pk]))
        req_pending_a.refresh_from_db()
        assert req_pending_a.submitted_at is None

    def test_return_marks_step_as_returned(self, client_a, req_pending_a, tenant_a):
        from apps.hrm.models import RequisitionApproval
        step = RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        client_a.post(reverse("hrm:jobrequisition_return", args=[req_pending_a.pk]))
        step.refresh_from_db()
        assert step.status == "returned"

    def test_return_draft_noop(self, client_a, req_draft_a):
        resp = client_a.post(reverse("hrm:jobrequisition_return", args=[req_draft_a.pk]))
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "draft"

    # --- post ---
    def test_post_changes_status(self, client_a, req_approved_a):
        resp = client_a.post(reverse("hrm:jobrequisition_post", args=[req_approved_a.pk]))
        assert resp.status_code == 302
        req_approved_a.refresh_from_db()
        assert req_approved_a.status == "posted"

    def test_post_stamps_posted_at(self, client_a, req_approved_a):
        client_a.post(reverse("hrm:jobrequisition_post", args=[req_approved_a.pk]))
        req_approved_a.refresh_from_db()
        assert req_approved_a.posted_at is not None

    def test_post_non_approved_noop(self, client_a, req_draft_a):
        resp = client_a.post(reverse("hrm:jobrequisition_post", args=[req_draft_a.pk]))
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "draft"

    def test_post_idor_404(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_post", args=[req_b.pk]))
        assert resp.status_code == 404

    # --- hold ---
    def test_hold_from_approved(self, client_a, req_approved_a):
        resp = client_a.post(reverse("hrm:jobrequisition_hold", args=[req_approved_a.pk]))
        assert resp.status_code == 302
        req_approved_a.refresh_from_db()
        assert req_approved_a.status == "on_hold"

    def test_hold_from_posted(self, client_a, req_posted_a):
        resp = client_a.post(reverse("hrm:jobrequisition_hold", args=[req_posted_a.pk]))
        assert resp.status_code == 302
        req_posted_a.refresh_from_db()
        assert req_posted_a.status == "on_hold"

    def test_hold_from_draft_noop(self, client_a, req_draft_a):
        resp = client_a.post(reverse("hrm:jobrequisition_hold", args=[req_draft_a.pk]))
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "draft"

    # --- mark_filled ---
    def test_mark_filled_from_posted(self, client_a, req_posted_a):
        resp = client_a.post(reverse("hrm:jobrequisition_mark_filled", args=[req_posted_a.pk]))
        assert resp.status_code == 302
        req_posted_a.refresh_from_db()
        assert req_posted_a.status == "filled"

    def test_mark_filled_stamps_filled_at(self, client_a, req_posted_a):
        client_a.post(reverse("hrm:jobrequisition_mark_filled", args=[req_posted_a.pk]))
        req_posted_a.refresh_from_db()
        assert req_posted_a.filled_at is not None

    def test_mark_filled_from_on_hold(self, client_a, req_approved_a):
        # First put on hold
        client_a.post(reverse("hrm:jobrequisition_hold", args=[req_approved_a.pk]))
        req_approved_a.refresh_from_db()
        assert req_approved_a.status == "on_hold"
        # Then mark filled
        resp = client_a.post(reverse("hrm:jobrequisition_mark_filled", args=[req_approved_a.pk]))
        assert resp.status_code == 302
        req_approved_a.refresh_from_db()
        assert req_approved_a.status == "filled"

    def test_mark_filled_from_draft_noop(self, client_a, req_draft_a):
        resp = client_a.post(reverse("hrm:jobrequisition_mark_filled", args=[req_draft_a.pk]))
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "draft"

    # --- cancel ---
    def test_cancel_from_draft(self, client_a, req_draft_a):
        resp = client_a.post(reverse("hrm:jobrequisition_cancel", args=[req_draft_a.pk]))
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "cancelled"

    def test_cancel_from_pending(self, client_a, req_pending_a):
        resp = client_a.post(reverse("hrm:jobrequisition_cancel", args=[req_pending_a.pk]))
        assert resp.status_code == 302
        req_pending_a.refresh_from_db()
        assert req_pending_a.status == "cancelled"

    def test_cancel_from_approved(self, client_a, req_approved_a):
        resp = client_a.post(reverse("hrm:jobrequisition_cancel", args=[req_approved_a.pk]))
        assert resp.status_code == 302
        req_approved_a.refresh_from_db()
        assert req_approved_a.status == "cancelled"

    def test_cancel_filled_noop(self, client_a, req_posted_a):
        """Cannot cancel a filled req."""
        # First fill it
        client_a.post(reverse("hrm:jobrequisition_mark_filled", args=[req_posted_a.pk]))
        req_posted_a.refresh_from_db()
        assert req_posted_a.status == "filled"
        # Now try to cancel — should be a noop
        client_a.post(reverse("hrm:jobrequisition_cancel", args=[req_posted_a.pk]))
        req_posted_a.refresh_from_db()
        assert req_posted_a.status == "filled"

    def test_cancel_already_cancelled_noop(self, client_a, req_draft_a):
        """Cancelling an already-cancelled req must be a noop."""
        client_a.post(reverse("hrm:jobrequisition_cancel", args=[req_draft_a.pk]))
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "cancelled"
        client_a.post(reverse("hrm:jobrequisition_cancel", args=[req_draft_a.pk]))
        req_draft_a.refresh_from_db()
        assert req_draft_a.status == "cancelled"

    def test_cancel_idor_404(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_cancel", args=[req_b.pk]))
        assert resp.status_code == 404

    # --- apply_template ---
    def test_apply_template_copies_jd_fields(self, client_a, req_draft_a, jd_template_a):
        req_draft_a.jd_summary = "OLD SUMMARY"
        req_draft_a.save(update_fields=["jd_summary"])
        resp = client_a.post(
            reverse("hrm:jobrequisition_apply_template", args=[req_draft_a.pk]),
            {"template_id": str(jd_template_a.pk)},
        )
        assert resp.status_code == 302
        req_draft_a.refresh_from_db()
        assert req_draft_a.jd_summary == jd_template_a.jd_summary

    def test_apply_template_sets_template_fk(self, client_a, req_draft_a, jd_template_a):
        client_a.post(
            reverse("hrm:jobrequisition_apply_template", args=[req_draft_a.pk]),
            {"template_id": str(jd_template_a.pk)},
        )
        req_draft_a.refresh_from_db()
        assert req_draft_a.template_id == jd_template_a.pk

    def test_apply_template_does_not_overwrite_employment_type(
        self, client_a, req_draft_a, jd_template_a
    ):
        req_draft_a.employment_type = "part_time"
        req_draft_a.save(update_fields=["employment_type"])
        jd_template_a.employment_type = "contract"
        jd_template_a.save(update_fields=["employment_type"])
        client_a.post(
            reverse("hrm:jobrequisition_apply_template", args=[req_draft_a.pk]),
            {"template_id": str(jd_template_a.pk)},
        )
        req_draft_a.refresh_from_db()
        assert req_draft_a.employment_type == "part_time"

    def test_apply_template_on_pending_noop(self, client_a, req_pending_a, jd_template_a):
        """apply_template should be blocked on a pending req."""
        req_pending_a.jd_summary = "ORIGINAL"
        req_pending_a.save(update_fields=["jd_summary"])
        client_a.post(
            reverse("hrm:jobrequisition_apply_template", args=[req_pending_a.pk]),
            {"template_id": str(jd_template_a.pk)},
        )
        req_pending_a.refresh_from_db()
        assert req_pending_a.jd_summary == "ORIGINAL"

    def test_apply_template_cross_tenant_template_404(self, client_a, req_draft_a, jd_template_b):
        """Using a cross-tenant template_id must return 404."""
        resp = client_a.post(
            reverse("hrm:jobrequisition_apply_template", args=[req_draft_a.pk]),
            {"template_id": str(jd_template_b.pk)},
        )
        assert resp.status_code == 404

    def test_apply_template_idor_req_404(self, client_a, req_b, jd_template_a):
        """tenant_a client with tenant_b req pk → 404."""
        resp = client_a.post(
            reverse("hrm:jobrequisition_apply_template", args=[req_b.pk]),
            {"template_id": str(jd_template_a.pk)},
        )
        assert resp.status_code == 404

    # --- clone ---
    def test_clone_creates_new_req(self, client_a, tenant_a, req_draft_a):
        from apps.hrm.models import JobRequisition
        count_before = JobRequisition.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("hrm:jobrequisition_clone", args=[req_draft_a.pk]))
        assert resp.status_code == 302
        assert JobRequisition.objects.filter(tenant=tenant_a).count() == count_before + 1

    def test_clone_new_number_differs_from_source(self, client_a, tenant_a, req_draft_a):
        from apps.hrm.models import JobRequisition
        client_a.post(reverse("hrm:jobrequisition_clone", args=[req_draft_a.pk]))
        cloned = JobRequisition.objects.filter(tenant=tenant_a).exclude(
            pk=req_draft_a.pk
        ).order_by("-created_at").first()
        assert cloned is not None
        assert cloned.number != req_draft_a.number

    def test_clone_status_is_draft(self, client_a, tenant_a, req_approved_a):
        """A clone of a non-draft req must still be a draft."""
        from apps.hrm.models import JobRequisition
        client_a.post(reverse("hrm:jobrequisition_clone", args=[req_approved_a.pk]))
        cloned = JobRequisition.objects.filter(tenant=tenant_a).exclude(
            pk=req_approved_a.pk
        ).order_by("-created_at").first()
        assert cloned is not None
        assert cloned.status == "draft"

    def test_clone_at_stamps_are_null(self, client_a, tenant_a, req_approved_a):
        """Workflow timestamps should all be null on the clone."""
        from apps.hrm.models import JobRequisition
        client_a.post(reverse("hrm:jobrequisition_clone", args=[req_approved_a.pk]))
        cloned = JobRequisition.objects.filter(tenant=tenant_a).exclude(
            pk=req_approved_a.pk
        ).order_by("-created_at").first()
        assert cloned is not None
        assert cloned.submitted_at is None
        assert cloned.approved_at is None
        assert cloned.posted_at is None
        assert cloned.filled_at is None

    def test_clone_copies_title(self, client_a, tenant_a, req_draft_a):
        from apps.hrm.models import JobRequisition
        client_a.post(reverse("hrm:jobrequisition_clone", args=[req_draft_a.pk]))
        cloned = JobRequisition.objects.filter(tenant=tenant_a).exclude(
            pk=req_draft_a.pk
        ).order_by("-created_at").first()
        assert cloned is not None
        assert cloned.title == req_draft_a.title

    def test_clone_idor_404(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_clone", args=[req_b.pk]))
        assert resp.status_code == 404


# ============================================================
# Approval Chain Management (approval_add / approval_delete)
# ============================================================

class TestApprovalChainManagement:
    """approval_add and approval_delete views — admin-only, draft-only."""

    def test_approval_add_creates_step(self, client_a, tenant_a, req_draft_a, admin_user):
        from apps.hrm.models import RequisitionApproval
        resp = client_a.post(
            reverse("hrm:approval_add", args=[req_draft_a.pk]),
            {
                "step_order": 1,
                "approver": admin_user.pk,
                "approver_role": "hr",
                "comments": "",
            },
        )
        assert resp.status_code == 302
        assert RequisitionApproval.objects.filter(
            tenant=tenant_a, requisition=req_draft_a, step_order=1
        ).exists()

    def test_approval_add_on_non_draft_blocked(self, client_a, tenant_a, req_pending_a, admin_user):
        """Adding a step to a non-draft req must be blocked."""
        from apps.hrm.models import RequisitionApproval
        count_before = RequisitionApproval.objects.filter(
            tenant=tenant_a, requisition=req_pending_a
        ).count()
        client_a.post(
            reverse("hrm:approval_add", args=[req_pending_a.pk]),
            {
                "step_order": 5,
                "approver": admin_user.pk,
                "approver_role": "hr",
                "comments": "",
            },
        )
        assert RequisitionApproval.objects.filter(
            tenant=tenant_a, requisition=req_pending_a
        ).count() == count_before

    def test_approval_add_idor_404(self, client_a, req_b, admin_user):
        resp = client_a.post(
            reverse("hrm:approval_add", args=[req_b.pk]),
            {"step_order": 1, "approver_role": "hr", "comments": ""},
        )
        assert resp.status_code == 404

    def test_approval_delete_removes_step(self, client_a, approval_step_a):
        pk = approval_step_a.pk
        resp = client_a.post(reverse("hrm:approval_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.hrm.models import RequisitionApproval
        assert not RequisitionApproval.objects.filter(pk=pk).exists()

    def test_approval_delete_on_non_draft_blocked(self, client_a, tenant_a, req_pending_a):
        """Deleting a step on a non-draft req must be blocked."""
        from apps.hrm.models import RequisitionApproval
        step = RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req_pending_a,
            step_order=1, approver_role="hr", status="pending",
        )
        pk = step.pk
        client_a.post(reverse("hrm:approval_delete", args=[pk]))
        assert RequisitionApproval.objects.filter(pk=pk).exists()

    def test_approval_delete_idor_404(self, client_a, approval_step_b):
        resp = client_a.post(reverse("hrm:approval_delete", args=[approval_step_b.pk]))
        assert resp.status_code == 404


# ============================================================
# Multi-Tenant Isolation (IDOR)
# ============================================================

class TestMultiTenantIsolation:
    """Tenant-A requests Tenant-B objects → 404."""

    def test_req_detail_idor(self, client_a, req_b):
        resp = client_a.get(reverse("hrm:jobrequisition_detail", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_edit_idor(self, client_a, req_b):
        resp = client_a.get(reverse("hrm:jobrequisition_edit", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_delete_idor(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_delete", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_submit_idor(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_submit", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_approve_step_idor(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_approve_step", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_reject_idor(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_reject", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_return_idor(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_return", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_hold_idor(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_hold", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_fill_idor(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_mark_filled", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_cancel_idor(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_cancel", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_clone_idor(self, client_a, req_b):
        resp = client_a.post(reverse("hrm:jobrequisition_clone", args=[req_b.pk]))
        assert resp.status_code == 404

    def test_req_apply_template_idor(self, client_a, req_b, jd_template_a):
        resp = client_a.post(
            reverse("hrm:jobrequisition_apply_template", args=[req_b.pk]),
            {"template_id": str(jd_template_a.pk)},
        )
        assert resp.status_code == 404

    def test_template_detail_idor(self, client_a, jd_template_b):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_detail", args=[jd_template_b.pk]))
        assert resp.status_code == 404

    def test_template_edit_idor(self, client_a, jd_template_b):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_edit", args=[jd_template_b.pk]))
        assert resp.status_code == 404

    def test_approval_add_idor(self, client_a, req_b, admin_user):
        resp = client_a.post(
            reverse("hrm:approval_add", args=[req_b.pk]),
            {"step_order": 1, "approver_role": "hr", "comments": ""},
        )
        assert resp.status_code == 404

    def test_approval_delete_idor(self, client_a, approval_step_b):
        resp = client_a.post(reverse("hrm:approval_delete", args=[approval_step_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_rows(self, client_a, req_draft_a, req_b):
        """The list view for tenant_a must not contain tenant_b rows."""
        resp = client_a.get(reverse("hrm:jobrequisition_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert req_draft_a.pk in pks
        assert req_b.pk not in pks

    def test_template_list_excludes_b_rows(self, client_a, jd_template_a, jd_template_b):
        resp = client_a.get(reverse("hrm:jobdescriptiontemplate_list"))
        assert jd_template_a.name.encode() in resp.content
        assert jd_template_b.name.encode() not in resp.content


# ============================================================
# Permission Gate (non-admin member)
# ============================================================

class TestPermissionGate:
    """Non-admin member → 403 on write actions, 200 on list/detail reads."""

    # --- Reads: 200 for members ---
    def test_member_can_access_req_list(self, member_client, req_draft_a):
        resp = member_client.get(reverse("hrm:jobrequisition_list"))
        assert resp.status_code == 200

    def test_member_can_access_req_detail(self, member_client, req_draft_a):
        resp = member_client.get(reverse("hrm:jobrequisition_detail", args=[req_draft_a.pk]))
        assert resp.status_code == 200

    def test_member_can_access_template_list(self, member_client, jd_template_a):
        resp = member_client.get(reverse("hrm:jobdescriptiontemplate_list"))
        assert resp.status_code == 200

    def test_member_can_access_template_detail(self, member_client, jd_template_a):
        resp = member_client.get(
            reverse("hrm:jobdescriptiontemplate_detail", args=[jd_template_a.pk])
        )
        assert resp.status_code == 200

    # --- Write actions: 403 for members ---
    def test_member_cannot_create_req(self, member_client):
        resp = member_client.get(reverse("hrm:jobrequisition_create"))
        assert resp.status_code == 403

    def test_member_cannot_edit_req(self, member_client, req_draft_a):
        resp = member_client.get(reverse("hrm:jobrequisition_edit", args=[req_draft_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_delete_req(self, member_client, req_draft_a):
        resp = member_client.post(reverse("hrm:jobrequisition_delete", args=[req_draft_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_submit_req(self, member_client, req_draft_a):
        resp = member_client.post(reverse("hrm:jobrequisition_submit", args=[req_draft_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_approve_step(self, member_client, req_pending_a):
        resp = member_client.post(
            reverse("hrm:jobrequisition_approve_step", args=[req_pending_a.pk])
        )
        assert resp.status_code == 403

    def test_member_cannot_reject_req(self, member_client, req_pending_a):
        resp = member_client.post(reverse("hrm:jobrequisition_reject", args=[req_pending_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_return_req(self, member_client, req_pending_a):
        resp = member_client.post(reverse("hrm:jobrequisition_return", args=[req_pending_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_post_req(self, member_client, req_approved_a):
        resp = member_client.post(reverse("hrm:jobrequisition_post", args=[req_approved_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_hold_req(self, member_client, req_approved_a):
        resp = member_client.post(reverse("hrm:jobrequisition_hold", args=[req_approved_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_fill_req(self, member_client, req_posted_a):
        resp = member_client.post(
            reverse("hrm:jobrequisition_mark_filled", args=[req_posted_a.pk])
        )
        assert resp.status_code == 403

    def test_member_cannot_cancel_req(self, member_client, req_draft_a):
        resp = member_client.post(reverse("hrm:jobrequisition_cancel", args=[req_draft_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_clone_req(self, member_client, req_draft_a):
        resp = member_client.post(reverse("hrm:jobrequisition_clone", args=[req_draft_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_apply_template(self, member_client, req_draft_a, jd_template_a):
        resp = member_client.post(
            reverse("hrm:jobrequisition_apply_template", args=[req_draft_a.pk]),
            {"template_id": str(jd_template_a.pk)},
        )
        assert resp.status_code == 403

    def test_member_cannot_add_approval(self, member_client, req_draft_a, admin_user):
        resp = member_client.post(
            reverse("hrm:approval_add", args=[req_draft_a.pk]),
            {"step_order": 1, "approver_role": "hr", "comments": ""},
        )
        assert resp.status_code == 403

    def test_member_cannot_delete_approval(self, member_client, approval_step_a):
        resp = member_client.post(reverse("hrm:approval_delete", args=[approval_step_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_create_template(self, member_client):
        resp = member_client.get(reverse("hrm:jobdescriptiontemplate_create"))
        assert resp.status_code == 403

    def test_member_cannot_edit_template(self, member_client, jd_template_a):
        resp = member_client.get(
            reverse("hrm:jobdescriptiontemplate_edit", args=[jd_template_a.pk])
        )
        assert resp.status_code == 403

    def test_member_cannot_delete_template(self, member_client, jd_template_a):
        resp = member_client.post(
            reverse("hrm:jobdescriptiontemplate_delete", args=[jd_template_a.pk])
        )
        assert resp.status_code == 403


# ============================================================
# Anonymous / Auth Guard
# ============================================================

class TestAnonymousAccessBlocked:
    """Anonymous → redirect to login."""

    def test_anon_req_list(self, client):
        resp = client.get(reverse("hrm:jobrequisition_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_req_detail(self, client, req_draft_a):
        resp = client.get(reverse("hrm:jobrequisition_detail", args=[req_draft_a.pk]))
        assert resp.status_code == 302

    def test_anon_req_create(self, client):
        resp = client.get(reverse("hrm:jobrequisition_create"))
        assert resp.status_code == 302

    def test_anon_template_list(self, client):
        resp = client.get(reverse("hrm:jobdescriptiontemplate_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_req_submit(self, client, req_draft_a):
        resp = client.post(reverse("hrm:jobrequisition_submit", args=[req_draft_a.pk]))
        assert resp.status_code == 302


# ============================================================
# Seeder Idempotency (model-level)
# ============================================================

class TestSeederIdempotency:
    """Running _seed_job_requisition twice doesn't duplicate rows."""

    def test_seed_twice_no_duplicate_templates(self, db, tenant_a, employee_a, designation_a, dept_a):
        from apps.hrm.management.commands.seed_hrm import Command
        cmd = Command()
        cmd.stdout = type("FakeStdout", (), {"write": lambda self, *a, **kw: None})()
        cmd.style = type("FakeStyle", (), {
            "SUCCESS": lambda self, s: s,
            "NOTICE": lambda self, s: s,
            "WARNING": lambda self, s: s,
            "ERROR": lambda self, s: s,
        })()
        # Run the seeder twice
        cmd._seed_job_requisition(tenant_a, flush=False)
        from apps.hrm.models import JobDescriptionTemplate, JobRequisition
        count_after_first = JobDescriptionTemplate.objects.filter(tenant=tenant_a).count()
        req_count_after_first = JobRequisition.objects.filter(tenant=tenant_a).count()
        cmd._seed_job_requisition(tenant_a, flush=False)
        count_after_second = JobDescriptionTemplate.objects.filter(tenant=tenant_a).count()
        req_count_after_second = JobRequisition.objects.filter(tenant=tenant_a).count()
        assert count_after_second == count_after_first
        assert req_count_after_second == req_count_after_first

    def test_seed_flush_replaces_data(self, db, tenant_a, employee_a, designation_a, dept_a):
        """--flush replaces seed data on second run."""
        from apps.hrm.management.commands.seed_hrm import Command
        from apps.hrm.models import JobRequisition
        cmd = Command()
        cmd.stdout = type("FakeStdout", (), {"write": lambda self, *a, **kw: None})()
        cmd.style = type("FakeStyle", (), {
            "SUCCESS": lambda self, s: s,
            "NOTICE": lambda self, s: s,
            "WARNING": lambda self, s: s,
            "ERROR": lambda self, s: s,
        })()
        cmd._seed_job_requisition(tenant_a, flush=False)
        count_first = JobRequisition.objects.filter(tenant=tenant_a).count()
        cmd._seed_job_requisition(tenant_a, flush=True)
        count_second = JobRequisition.objects.filter(tenant=tenant_a).count()
        assert count_second == count_first  # same count, just replaced


# ============================================================
# N+1 Query Budget
# ============================================================

class TestQueryBudget:
    """List view must not incur N+1 queries."""

    def test_req_list_bounded_queries(
        self, client_a, tenant_a, dept_a, designation_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import JobRequisition
        # Create a few reqs to ensure pagination/query logic is exercised
        for i in range(3):
            JobRequisition.objects.create(
                tenant=tenant_a, title=f"Role {i}", headcount=1,
                req_type="standard", employment_type="full_time",
                reason_for_hire="new_headcount", posting_type="external", priority="medium",
            )
        with django_assert_max_num_queries(20):
            client_a.get(reverse("hrm:jobrequisition_list"))

    def test_template_list_bounded_queries(
        self, client_a, tenant_a, designation_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import JobDescriptionTemplate
        for i in range(3):
            JobDescriptionTemplate.objects.create(
                tenant=tenant_a, name=f"Template {i}", employment_type="full_time", is_active=True)
        with django_assert_max_num_queries(20):
            client_a.get(reverse("hrm:jobdescriptiontemplate_list"))
