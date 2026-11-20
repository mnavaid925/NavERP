"""Unit tests for Quality Management Sub-module 12.14: Management Review & Quality Planning Models.

Tests models:
- QualityObjective (QOBJ)
- ManagementReview (QMRV)
- ManagementReviewInput (QMRI)
- ManagementReviewAction (QMRA)
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.quality.models import (
    QualityObjective,
    ManagementReview,
    ManagementReviewInput,
    ManagementReviewAction,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (Must start with _managementreview_*)
# ==============================================================================

def _managementreview_create_objective(tenant, owner, **kwargs):
    """Helper to create a QualityObjective with sensible defaults."""
    defaults = {
        "title": "Default Quality Objective",
        "description": "Standard objective description for testing.",
        "category": "product_quality",
        "period_year": 2026,
        "cadence": "quarterly",
        "metric_unit": "%",
        "target_value": Decimal("100.000"),
        "target_direction": "higher_better",
        "status": "draft",
        "rag_status": "neutral",
        "owner": owner,
    }
    defaults.update(kwargs)
    return QualityObjective.objects.create(tenant=tenant, **defaults)


def _managementreview_create_review(tenant, sponsor, facilitator, **kwargs):
    """Helper to create a ManagementReview with sensible defaults."""
    today = timezone.now().date()
    defaults = {
        "title": "Quarterly QMS Management Review",
        "cadence": "quarterly",
        "period_start": today - timedelta(days=90),
        "period_end": today,
        "scheduled_date": today + timedelta(days=14),
        "executive_sponsor": sponsor,
        "lead_facilitator": facilitator,
        "status": "scheduled",
        "qms_suitability_conclusion": "pending",
    }
    defaults.update(kwargs)
    return ManagementReview.objects.create(tenant=tenant, **defaults)


# ==============================================================================
# 1. QualityObjective Tests
# ==============================================================================

def test_managementreview_quality_objective_autonumber_and_str(quality_objective_a, tenant_a):
    """Verify QualityObjective auto-number prefix QOBJ-, str representation, and defaults."""
    assert quality_objective_a.number.startswith("QOBJ-")
    assert quality_objective_a.tenant == tenant_a
    assert str(quality_objective_a) == f"{quality_objective_a.number} — {quality_objective_a.title} ({quality_objective_a.period_year})"


def test_managementreview_quality_objective_defaults_and_fields(tenant_a, admin_user):
    """Verify QualityObjective default status, rag_status, and cadence choices."""
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        title="Test Default Objective",
    )
    assert obj.status == "draft"
    assert obj.rag_status == "neutral"
    assert obj.cadence == "quarterly"
    assert obj.target_direction == "higher_better"
    assert obj.metric_unit == "%"
    assert obj.last_evaluated_date is None


def test_managementreview_quality_objective_variance_property(tenant_a, admin_user):
    """Verify variance computed property calculation and None handling."""
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        target_value=Decimal("10.000"),
        current_value=Decimal("12.500"),
    )
    assert obj.variance == Decimal("2.500")

    # None current value returns None
    obj.current_value = None
    assert obj.variance is None


def test_managementreview_quality_objective_is_achieved_higher_better(tenant_a, admin_user):
    """Verify is_achieved logic when target_direction is higher_better."""
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        target_value=Decimal("95.000"),
        current_value=Decimal("95.000"),
        target_direction="higher_better",
    )
    assert obj.is_achieved is True

    obj.current_value = Decimal("96.500")
    assert obj.is_achieved is True

    obj.current_value = Decimal("94.999")
    assert obj.is_achieved is False

    obj.current_value = None
    assert obj.is_achieved is False


def test_managementreview_quality_objective_is_achieved_lower_better(tenant_a, admin_user):
    """Verify is_achieved logic when target_direction is lower_better."""
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        target_value=Decimal("2.000"),
        current_value=Decimal("1.800"),
        target_direction="lower_better",
    )
    assert obj.is_achieved is True

    obj.current_value = Decimal("2.000")
    assert obj.is_achieved is True

    obj.current_value = Decimal("2.001")
    assert obj.is_achieved is False


def test_managementreview_quality_objective_is_achieved_exact(tenant_a, admin_user):
    """Verify is_achieved logic when target_direction is exact."""
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        target_value=Decimal("5.000"),
        current_value=Decimal("5.000"),
        target_direction="exact",
    )
    assert obj.is_achieved is True

    obj.current_value = Decimal("5.001")
    assert obj.is_achieved is False


def test_managementreview_quality_objective_evaluate_performance_higher_better(tenant_a, admin_user):
    """Verify evaluate_performance for higher_better direction (achieved, at_risk, behind)."""
    today = timezone.now().date()
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        target_value=Decimal("100.000"),
        current_value=Decimal("100.000"),
        target_direction="higher_better",
    )
    obj.evaluate_performance()
    assert obj.status == "achieved"
    assert obj.rag_status == "green"
    assert obj.last_evaluated_date == today

    # Amber / at_risk: ratio >= 0.90 (e.g. 90.0)
    obj.current_value = Decimal("90.000")
    obj.evaluate_performance()
    assert obj.status == "at_risk"
    assert obj.rag_status == "amber"

    # Red / behind: ratio < 0.90 (e.g. 89.9)
    obj.current_value = Decimal("89.900")
    obj.evaluate_performance()
    assert obj.status == "behind"
    assert obj.rag_status == "red"

    # Neutral when current_value is None
    obj.current_value = None
    obj.evaluate_performance()
    assert obj.rag_status == "neutral"


def test_managementreview_quality_objective_evaluate_performance_lower_better(tenant_a, admin_user):
    """Verify evaluate_performance for lower_better direction (achieved, at_risk, behind)."""
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        target_value=Decimal("10.000"),
        current_value=Decimal("10.000"),
        target_direction="lower_better",
    )
    obj.evaluate_performance()
    assert obj.status == "achieved"
    assert obj.rag_status == "green"

    # Amber / at_risk: target/current >= 0.90 (e.g. 10/11 = 0.909)
    obj.current_value = Decimal("11.000")
    obj.evaluate_performance()
    assert obj.status == "at_risk"
    assert obj.rag_status == "amber"

    # Red / behind: target/current < 0.90 (e.g. 10/12 = 0.833)
    obj.current_value = Decimal("12.000")
    obj.evaluate_performance()
    assert obj.status == "behind"
    assert obj.rag_status == "red"


def test_managementreview_quality_objective_evaluate_performance_exact(tenant_a, admin_user):
    """Verify evaluate_performance for exact target direction."""
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        target_value=Decimal("50.000"),
        current_value=Decimal("50.000"),
        target_direction="exact",
    )
    obj.evaluate_performance()
    assert obj.status == "achieved"
    assert obj.rag_status == "green"

    obj.current_value = Decimal("48.000")
    obj.evaluate_performance()
    assert obj.status == "behind"
    assert obj.rag_status == "red"


def test_managementreview_quality_objective_progress_percent_higher_better(tenant_a, admin_user):
    """Verify progress_percent property for higher_better with baseline and clamping."""
    # With baseline: span = 100 - 50 = 50. current = 75 -> progress = 25 -> 50%
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        baseline_value=Decimal("50.000"),
        target_value=Decimal("100.000"),
        current_value=Decimal("75.000"),
        target_direction="higher_better",
    )
    assert obj.progress_percent == 50

    # Below baseline -> clamped to 0
    obj.current_value = Decimal("40.000")
    assert obj.progress_percent == 0

    # Achieved -> clamped to 100
    obj.current_value = Decimal("120.000")
    assert obj.progress_percent == 100

    # Without baseline: current/target * 100
    obj.baseline_value = None
    obj.current_value = Decimal("60.000")
    assert obj.progress_percent == 60


def test_managementreview_quality_objective_progress_percent_lower_better(tenant_a, admin_user):
    """Verify progress_percent property for lower_better with baseline and clamping."""
    # With baseline: span = 20 - 10 = 10. current = 15 -> progress = 20 - 15 = 5 -> 50%
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        baseline_value=Decimal("20.000"),
        target_value=Decimal("10.000"),
        current_value=Decimal("15.000"),
        target_direction="lower_better",
    )
    assert obj.progress_percent == 50

    # Current worse than baseline -> clamped to 0
    obj.current_value = Decimal("25.000")
    assert obj.progress_percent == 0

    # Achieved -> 100
    obj.current_value = Decimal("8.000")
    assert obj.progress_percent == 100

    # Without baseline: target/current * 100
    obj.baseline_value = None
    obj.current_value = Decimal("20.000")
    assert obj.progress_percent == 50


def test_managementreview_quality_objective_progress_percent_exact(tenant_a, admin_user):
    """Verify progress_percent property for exact target direction."""
    obj = _managementreview_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        target_value=Decimal("100.000"),
        current_value=Decimal("90.000"),
        target_direction="exact",
    )
    assert obj.progress_percent == 90

    # Huge deviation clamped to 0
    obj.current_value = Decimal("250.000")
    assert obj.progress_percent == 0

    # None current value returns 0
    obj.current_value = None
    assert obj.progress_percent == 0


def test_managementreview_quality_objective_badges(quality_objective_a):
    """Verify badge CSS classes for category, status, and RAG status."""
    assert quality_objective_a.category_badge_class == "badge-info"
    assert quality_objective_a.status_badge_class == "badge-green"
    assert quality_objective_a.rag_badge_class == "badge-green"

    quality_objective_a.status = "at_risk"
    quality_objective_a.rag_status = "amber"
    assert quality_objective_a.status_badge_class == "badge-amber"
    assert quality_objective_a.rag_badge_class == "badge-amber"

    quality_objective_a.status = "behind"
    quality_objective_a.rag_status = "red"
    assert quality_objective_a.status_badge_class == "badge-red"
    assert quality_objective_a.rag_badge_class == "badge-red"

    quality_objective_a.status = "draft"
    quality_objective_a.rag_status = "neutral"
    assert quality_objective_a.status_badge_class == "badge-muted"
    assert quality_objective_a.rag_badge_class == "badge-muted"


# ==============================================================================
# 2. ManagementReview Tests
# ==============================================================================

def test_managementreview_review_autonumber_and_str(management_review_a, tenant_a):
    """Verify ManagementReview auto-number prefix QMRV- and string formatting."""
    assert management_review_a.number.startswith("QMRV-")
    assert management_review_a.tenant == tenant_a
    assert str(management_review_a) == f"{management_review_a.number} — {management_review_a.title} ({management_review_a.get_cadence_display()})"


def test_managementreview_review_status_and_cadence_choices(tenant_a, admin_user, staff_user):
    """Verify ManagementReview choices for cadence, status, and suitability."""
    review = _managementreview_create_review(
        tenant=tenant_a,
        sponsor=admin_user,
        facilitator=staff_user,
        cadence="annual",
        status="approved",
        qms_suitability_conclusion="suitable_effective",
    )
    assert review.cadence == "annual"
    assert review.status == "approved"
    assert review.qms_suitability_conclusion == "suitable_effective"
    assert review.get_cadence_display() == "Annual Review"
    assert review.get_status_display() == "Executive Approved / Closed"
    assert review.get_qms_suitability_conclusion_display() == "Suitable, Adequate & Fully Effective"


def test_managementreview_review_computed_counts(
    management_review_a,
    management_review_input_a,
    management_review_action_a,
    tenant_a,
    staff_user,
):
    """Verify computed properties total_inputs_count, total_actions_count, and open_actions_count."""
    assert management_review_a.total_inputs_count == 1
    assert management_review_a.total_actions_count == 1
    assert management_review_a.open_actions_count == 1

    today = timezone.now().date()
    # Add an in_progress action
    ManagementReviewAction.objects.create(
        tenant=tenant_a,
        management_review=management_review_a,
        title="Second Action In Progress",
        description="Action in progress description.",
        action_type="qms_improvement",
        priority="medium",
        assignee=staff_user,
        due_date=today + timedelta(days=20),
        status="in_progress",
    )
    # Add a completed action
    ManagementReviewAction.objects.create(
        tenant=tenant_a,
        management_review=management_review_a,
        title="Third Action Completed",
        description="Action completed description.",
        action_type="procedure_revision",
        priority="low",
        assignee=staff_user,
        due_date=today + timedelta(days=5),
        status="completed",
    )

    assert management_review_a.total_actions_count == 3
    assert management_review_a.open_actions_count == 2


def test_managementreview_review_is_overdue(management_review_a):
    """Verify ManagementReview is_overdue property calculation."""
    today = timezone.now().date()
    # Scheduled in the future -> not overdue
    management_review_a.status = "scheduled"
    management_review_a.scheduled_date = today + timedelta(days=7)
    assert management_review_a.is_overdue is False

    # Scheduled in the past -> overdue
    management_review_a.scheduled_date = today - timedelta(days=1)
    assert management_review_a.is_overdue is True

    # In progress or closed in the past -> not overdue
    management_review_a.status = "meeting_active"
    assert management_review_a.is_overdue is False

    management_review_a.status = "approved"
    assert management_review_a.is_overdue is False


def test_managementreview_review_badges(management_review_a):
    """Verify badge CSS classes for cadence, status, and suitability."""
    assert management_review_a.cadence_badge_class == "badge-info"
    assert management_review_a.status_badge_class == "badge-info"
    assert management_review_a.suitability_badge_class == "badge-muted"

    management_review_a.status = "approved"
    management_review_a.qms_suitability_conclusion = "suitable_effective"
    assert management_review_a.status_badge_class == "badge-green"
    assert management_review_a.suitability_badge_class == "badge-green"

    management_review_a.status = "cancelled"
    management_review_a.qms_suitability_conclusion = "systemic_deficiencies"
    assert management_review_a.status_badge_class == "badge-slate"
    assert management_review_a.suitability_badge_class == "badge-red"


# ==============================================================================
# 3. ManagementReviewInput Tests
# ==============================================================================

def test_managementreview_input_autonumber_and_str(management_review_input_a, management_review_a):
    """Verify ManagementReviewInput auto-number prefix QMRI- and string formatting."""
    assert management_review_input_a.number.startswith("QMRI-")
    assert management_review_input_a.management_review == management_review_a
    assert str(management_review_input_a) == f"{management_review_input_a.number} — #{management_review_input_a.agenda_order} {management_review_input_a.title}"


def test_managementreview_input_category_choices_and_agenda_ordering(management_review_a, tenant_a, admin_user):
    """Verify agenda_order ordering and category choices for review inputs."""
    input_3 = ManagementReviewInput.objects.create(
        tenant=tenant_a,
        management_review=management_review_a,
        agenda_order=3,
        title="Agenda Item 3: CAPA Trends",
        category="capa_status",
        summary_findings="Overview of open CAPAs and verification timelines.",
        presenter=admin_user,
        status="compiled",
    )
    input_2 = ManagementReviewInput.objects.create(
        tenant=tenant_a,
        management_review=management_review_a,
        agenda_order=2,
        title="Agenda Item 2: Customer Feedback",
        category="customer_feedback",
        summary_findings="Customer satisfaction index and complaint rates.",
        presenter=admin_user,
        status="draft",
    )

    inputs = list(management_review_a.inputs.all())
    agenda_orders = [item.agenda_order for item in inputs]
    assert agenda_orders == sorted(agenda_orders)
    assert input_2 in inputs
    assert input_3 in inputs


def test_managementreview_input_badges(management_review_input_a):
    """Verify badge CSS classes for input category and status."""
    assert management_review_input_a.category_badge_class == "badge-info"
    assert management_review_input_a.status_badge_class == "badge-info"

    management_review_input_a.category = "capa_status"
    management_review_input_a.status = "accepted"
    assert management_review_input_a.category_badge_class == "badge-red"
    assert management_review_input_a.status_badge_class == "badge-green"

    management_review_input_a.category = "customer_feedback"
    management_review_input_a.status = "presented"
    assert management_review_input_a.category_badge_class == "badge-amber"
    assert management_review_input_a.status_badge_class == "badge-amber"


def test_managementreview_input_linked_quality_records(
    tenant_a,
    management_review_a,
    admin_user,
    quality_audit_a,
    capa_investigation_a,
    customer_complaint_a,
    ncr_a,
):
    """Verify ManagementReviewInput foreign keys to audit, capa, complaint, and NCR."""
    item = ManagementReviewInput.objects.create(
        tenant=tenant_a,
        management_review=management_review_a,
        agenda_order=10,
        title="Comprehensive Quality Systems Performance",
        category="process_conformity",
        summary_findings="Cross-cutting metrics linking audits, CAPAs, complaints, and non-conformances.",
        presenter=admin_user,
        linked_audit=quality_audit_a,
        linked_capa=capa_investigation_a,
        linked_complaint=customer_complaint_a,
        linked_ncr=ncr_a,
        status="compiled",
    )
    assert item.linked_audit == quality_audit_a
    assert item.linked_capa == capa_investigation_a
    assert item.linked_complaint == customer_complaint_a
    assert item.linked_ncr == ncr_a
    assert item in quality_audit_a.review_inputs.all()
    assert item in capa_investigation_a.review_inputs.all()
    assert item in customer_complaint_a.review_inputs.all()
    assert item in ncr_a.review_inputs.all()


# ==============================================================================
# 4. ManagementReviewAction Tests
# ==============================================================================

def test_managementreview_action_autonumber_and_str(management_review_action_a, management_review_a):
    """Verify ManagementReviewAction auto-number prefix QMRA- and string formatting."""
    assert management_review_action_a.number.startswith("QMRA-")
    assert management_review_action_a.management_review == management_review_a
    assert str(management_review_action_a) == f"{management_review_action_a.number} — {management_review_action_a.title} ({management_review_action_a.get_priority_display()})"


def test_managementreview_action_priority_and_action_type_choices(tenant_a, management_review_a, staff_user):
    """Verify action_type and priority choices on ManagementReviewAction."""
    today = timezone.now().date()
    action = ManagementReviewAction.objects.create(
        tenant=tenant_a,
        management_review=management_review_a,
        title="Critical CAPA Initiation Action",
        description="Mandatory action following systemic audit deficiency.",
        action_type="capa_initiation",
        priority="critical",
        assignee=staff_user,
        due_date=today + timedelta(days=14),
        status="open",
        budget_allocated=Decimal("25000.00"),
    )
    assert action.action_type == "capa_initiation"
    assert action.priority == "critical"
    assert action.get_action_type_display() == "Formal CAPA Initiation"
    assert action.get_priority_display() == "Critical"
    assert action.budget_allocated == Decimal("25000.00")


def test_managementreview_action_is_overdue(management_review_action_a):
    """Verify ManagementReviewAction is_overdue property calculation."""
    today = timezone.now().date()
    # Due in future -> not overdue
    management_review_action_a.due_date = today + timedelta(days=10)
    management_review_action_a.status = "open"
    assert management_review_action_a.is_overdue is False

    # Due in past, status=open -> overdue
    management_review_action_a.due_date = today - timedelta(days=2)
    assert management_review_action_a.is_overdue is True

    # Due in past, status=in_progress -> overdue
    management_review_action_a.status = "in_progress"
    assert management_review_action_a.is_overdue is True

    # Due in past, status=pending_verification -> overdue
    management_review_action_a.status = "pending_verification"
    assert management_review_action_a.is_overdue is True

    # Due in past, status=completed -> not overdue
    management_review_action_a.status = "completed"
    assert management_review_action_a.is_overdue is False

    # Due in past, status=cancelled -> not overdue
    management_review_action_a.status = "cancelled"
    assert management_review_action_a.is_overdue is False


def test_managementreview_action_days_open_calculation_and_clamping(management_review_action_a):
    """Verify days_open property calculation and non-negative clamping."""
    today = timezone.now().date()
    # When completion_date is None, days_open computes against today
    assert management_review_action_a.days_open >= 0

    # When completion_date is 10 days after created_at
    created_date = management_review_action_a.created_at.date()
    management_review_action_a.completion_date = created_date + timedelta(days=10)
    assert management_review_action_a.days_open == 10

    # Clamping test: completion_date before created_date returns 0
    management_review_action_a.completion_date = created_date - timedelta(days=5)
    assert management_review_action_a.days_open == 0


def test_managementreview_action_badges(management_review_action_a):
    """Verify badge CSS classes for action_type, priority, and status."""
    assert management_review_action_a.action_type_badge_class == "badge-amber"
    assert management_review_action_a.priority_badge_class == "badge-amber"
    assert management_review_action_a.status_badge_class == "badge-info"

    management_review_action_a.action_type = "qms_improvement"
    management_review_action_a.priority = "critical"
    management_review_action_a.status = "completed"
    assert management_review_action_a.action_type_badge_class == "badge-green"
    assert management_review_action_a.priority_badge_class == "badge-red"
    assert management_review_action_a.status_badge_class == "badge-green"

    management_review_action_a.action_type = "procedure_revision"
    management_review_action_a.priority = "low"
    management_review_action_a.status = "cancelled"
    assert management_review_action_a.action_type_badge_class == "badge-slate"
    assert management_review_action_a.priority_badge_class == "badge-slate"
    assert management_review_action_a.status_badge_class == "badge-slate"


def test_managementreview_action_linked_capa_and_change_order(
    tenant_a,
    management_review_a,
    staff_user,
    capa_investigation_a,
    quality_dco,
):
    """Verify ManagementReviewAction foreign keys to spawned CAPA and DCO."""
    today = timezone.now().date()
    action = ManagementReviewAction.objects.create(
        tenant=tenant_a,
        management_review=management_review_a,
        title="Initiate CAPA and DCO for Inspection Defect",
        description="Formal action triggering corrective action and document update.",
        action_type="capa_initiation",
        priority="high",
        assignee=staff_user,
        due_date=today + timedelta(days=30),
        status="in_progress",
        spawned_capa=capa_investigation_a,
        spawned_change_order=quality_dco,
    )
    assert action.spawned_capa == capa_investigation_a
    assert action.spawned_change_order == quality_dco
    assert action in capa_investigation_a.spawned_management_actions.all()
    assert action in quality_dco.spawned_management_actions.all()


# ==============================================================================
# 5. Multi-Tenant Isolation & Uniqueness Constraints Tests
# ==============================================================================

def test_managementreview_multi_tenant_uniqueness_quality_objective(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    quality_objective_a,
):
    """Verify composite uniqueness constraint (tenant, number) on QualityObjective."""
    existing_number = quality_objective_a.number

    # Same tenant duplicate number -> IntegrityError
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            QualityObjective.objects.create(
                tenant=tenant_a,
                number=existing_number,
                title="Duplicate Objective",
                description="Testing duplicate constraint violation.",
                category="product_quality",
                target_value=Decimal("100.000"),
                owner=admin_user,
            )

    # Different tenant can reuse the exact same number
    tenant_b_obj = QualityObjective.objects.create(
        tenant=tenant_b,
        number=existing_number,
        title="Tenant B Objective with Same Number",
        description="Testing cross-tenant number isolation.",
        category="product_quality",
        target_value=Decimal("100.000"),
        owner=admin_b,
    )
    assert tenant_b_obj.pk is not None
    assert tenant_b_obj.number == existing_number
    assert tenant_b_obj.tenant == tenant_b


def test_managementreview_multi_tenant_uniqueness_management_review(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    staff_user,
    management_review_a,
):
    """Verify composite uniqueness constraint (tenant, number) on ManagementReview."""
    today = timezone.now().date()
    existing_number = management_review_a.number

    # Same tenant duplicate number -> IntegrityError
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            ManagementReview.objects.create(
                tenant=tenant_a,
                number=existing_number,
                title="Duplicate Review",
                cadence="quarterly",
                period_start=today - timedelta(days=90),
                period_end=today,
                scheduled_date=today + timedelta(days=14),
                executive_sponsor=admin_user,
                lead_facilitator=staff_user,
            )

    # Different tenant can reuse the exact same number
    tenant_b_rev = ManagementReview.objects.create(
        tenant=tenant_b,
        number=existing_number,
        title="Tenant B Review with Same Number",
        cadence="quarterly",
        period_start=today - timedelta(days=90),
        period_end=today,
        scheduled_date=today + timedelta(days=14),
        executive_sponsor=admin_b,
        lead_facilitator=admin_b,
    )
    assert tenant_b_rev.pk is not None
    assert tenant_b_rev.number == existing_number
    assert tenant_b_rev.tenant == tenant_b


def test_managementreview_multi_tenant_uniqueness_review_input(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    management_review_a,
    management_review_b,
    management_review_input_a,
):
    """Verify composite uniqueness constraint (tenant, number) on ManagementReviewInput."""
    existing_number = management_review_input_a.number

    # Same tenant duplicate number -> IntegrityError
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            ManagementReviewInput.objects.create(
                tenant=tenant_a,
                number=existing_number,
                management_review=management_review_a,
                agenda_order=99,
                title="Duplicate Review Input",
                category="audit_results",
                summary_findings="Testing duplicate constraint violation.",
                presenter=admin_user,
            )

    # Different tenant can reuse the exact same number
    tenant_b_input = ManagementReviewInput.objects.create(
        tenant=tenant_b,
        number=existing_number,
        management_review=management_review_b,
        agenda_order=99,
        title="Tenant B Review Input with Same Number",
        category="audit_results",
        summary_findings="Testing cross-tenant number isolation.",
        presenter=admin_b,
    )
    assert tenant_b_input.pk is not None
    assert tenant_b_input.number == existing_number
    assert tenant_b_input.tenant == tenant_b


def test_managementreview_multi_tenant_uniqueness_review_action(
    tenant_a,
    tenant_b,
    staff_user,
    admin_b,
    management_review_a,
    management_review_b,
    management_review_action_a,
):
    """Verify composite uniqueness constraint (tenant, number) on ManagementReviewAction."""
    today = timezone.now().date()
    existing_number = management_review_action_a.number

    # Same tenant duplicate number -> IntegrityError
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            ManagementReviewAction.objects.create(
                tenant=tenant_a,
                number=existing_number,
                management_review=management_review_a,
                title="Duplicate Action",
                description="Testing duplicate constraint violation.",
                action_type="qms_improvement",
                priority="high",
                assignee=staff_user,
                due_date=today + timedelta(days=30),
            )

    # Different tenant can reuse the exact same number
    tenant_b_action = ManagementReviewAction.objects.create(
        tenant=tenant_b,
        number=existing_number,
        management_review=management_review_b,
        title="Tenant B Action with Same Number",
        description="Testing cross-tenant number isolation.",
        action_type="qms_improvement",
        priority="high",
        assignee=admin_b,
        due_date=today + timedelta(days=30),
    )
    assert tenant_b_action.pk is not None
    assert tenant_b_action.number == existing_number
    assert tenant_b_action.tenant == tenant_b
