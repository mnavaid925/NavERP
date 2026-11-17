"""
Unit tests for apps/quality models (Sub-module 12.4: CAPA - Corrective & Preventive Action).

Covers:
- CapaInvestigation [QCAP-]: auto-numbering, action types (corrective/preventive),
  source types, risk priority tiers, lifecycle status transitions, containment measures,
  properties (days_open, is_overdue, actions_count, pending_actions_count, rca_count),
  __str__ formatting, compound indexes, unique constraints, tenant isolation.
- RootCauseAnalysis [QRCA-]: auto-numbering, 5 Whys ladder, Ishikawa 6M fishbone analysis,
  escape point barrier analysis, methodology choices and CSS badges, root cause categories,
  verification metadata and property, __str__ (with and without capa_id), cascade deletion.
- CapaAction [QACT-]: auto-numbering, action types (containment, corrective, preventive),
  status workflows and badges, due date and overdue check, independent quality verification,
  cross-module links (ControlledDocument, DocumentChangeOrder, DesignProject), __str__.
- CapaEffectivenessReview [QEFF-]: auto-numbering, verification methods, outcome determinations,
  scheduled date tracking, recurrence observed logic, 21 CFR Part 11 e-signature linking,
  is_effective property, __str__ (with and without capa_id).
- Multi-tenant isolation across all 4 models and ForeignKey delete protection / cascade rules.
"""

from datetime import timedelta
import re
import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.quality.models import (
    CapaAction,
    CapaEffectivenessReview,
    CapaInvestigation,
    ControlledDocument,
    DesignProject,
    DocumentChangeOrder,
    ElectronicSignatureRecord,
    RiskAssessment,
    RootCauseAnalysis,
)

pytestmark = pytest.mark.django_db

_CAPAMANAGEMENT_VALID_BADGE_CLASSES = {
    "badge-slate",
    "badge-info",
    "badge-green",
    "badge-amber",
    "badge-red",
    "badge-muted",
}


# =====================================================================
# Fixture Overrides & Safe Fallbacks (Prefix: _capamanagement_*)
# =====================================================================

@pytest.fixture
def capa_investigation_a(db, tenant_a, admin_user, quality_department):
    """Local fixture override ensuring correct model field names."""
    return CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Optical Fiber Connector Cracking Under Mechanical Stress",
        action_type="corrective",
        source_type="complaint",
        risk_priority="high",
        status="under_investigation",
        department=quality_department,
        lead_investigator=admin_user,
        quality_owner=admin_user,
        issue_summary="Connector ferrules fracture when subjected to 15N bending load during clinical use.",
        containment_actions="Quarantine lot OF-2026-088; notify distribution centers.",
        target_closure_date=timezone.now().date() + timedelta(days=30),
    )


@pytest.fixture
def capa_investigation_b(db, tenant_b, admin_b, quality_department_b):
    """Local fixture override for Tenant B investigation."""
    return CapaInvestigation.objects.create(
        tenant=tenant_b,
        title="Globex Power Converter Thermal Excursion",
        action_type="corrective",
        source_type="internal_audit",
        risk_priority="critical",
        status="under_investigation",
        department=quality_department_b,
        lead_investigator=admin_b,
        quality_owner=admin_b,
        issue_summary="Heatsink paste drying causes overheating in laser power supply unit.",
        containment_actions="Halt production line 3; verify incoming thermal compound.",
        target_closure_date=timezone.now().date() + timedelta(days=20),
    )


@pytest.fixture
def root_cause_analysis_a(db, tenant_a, admin_user, capa_investigation_a):
    """Local fixture override for RootCauseAnalysis in Tenant A."""
    return RootCauseAnalysis.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        rca_method="5_whys",
        problem_statement="Connector ferrules crack under 15N load instead of rated 30N specification.",
        why_1="Ferrule molded wall thickness was below 0.8mm nominal.",
        why_2="Injection molding tooling core pin experienced wear after 50,000 cycles.",
        why_3="Preventive maintenance schedule did not include core pin dimensional CMM inspection.",
        why_4="Tool maintenance SOP lacked critical dimension inspection checklist for optical cores.",
        why_5="No periodic design verification for tooling wear-out limits was established.",
        root_cause_summary="Lack of tool wear CMM measurement verification in preventive maintenance procedure.",
        root_cause_category="equipment",
        lead_investigator=admin_user,
        status="in_progress",
    )


@pytest.fixture
def root_cause_analysis_b(db, tenant_b, admin_b, capa_investigation_b):
    """Local fixture override for RootCauseAnalysis in Tenant B."""
    return RootCauseAnalysis.objects.create(
        tenant=tenant_b,
        capa=capa_investigation_b,
        rca_method="5_whys",
        problem_statement="Thermal paste dries out under operating temperature.",
        why_1="Thermal resistance increased above 0.5 C/W.",
        why_2="Paste viscosity decreased due to solvent evaporation.",
        why_3="Supplier changed formulation without notification.",
        why_4="Incoming inspection did not test volatile organic content.",
        why_5="Supplier quality agreement did not list thermal compound as critical material.",
        root_cause_summary="Supplier material formulation change without prior supplier quality agreement gate.",
        root_cause_category="supplier",
        lead_investigator=admin_b,
        status="in_progress",
    )


@pytest.fixture
def capa_action_a(db, tenant_a, admin_user, quality_department, capa_investigation_a, root_cause_analysis_a):
    """Local fixture override for CapaAction in Tenant A."""
    return CapaAction.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        root_cause=root_cause_analysis_a,
        action_type="corrective",
        title="Update Tooling PM SOP to require CMM Core Pin Metrology",
        description="Revise SOP-MNT-042 to mandate CMM measurement of core pins every 10,000 cycles.",
        assigned_to=admin_user,
        department=quality_department,
        due_date=timezone.now().date() + timedelta(days=14),
        status="pending",
    )


@pytest.fixture
def capa_action_b(db, tenant_b, admin_b, quality_department_b, capa_investigation_b, root_cause_analysis_b):
    """Local fixture override for CapaAction in Tenant B."""
    return CapaAction.objects.create(
        tenant=tenant_b,
        capa=capa_investigation_b,
        root_cause=root_cause_analysis_b,
        action_type="corrective",
        title="Institute Incoming VOC Testing for Thermal Paste",
        description="Establish gas chromatography inspection for incoming compound barrels.",
        assigned_to=admin_b,
        department=quality_department_b,
        due_date=timezone.now().date() + timedelta(days=10),
        status="pending",
    )


@pytest.fixture
def capa_effectiveness_review_a(db, tenant_a, admin_user, capa_investigation_a):
    """Local fixture override for CapaEffectivenessReview in Tenant A."""
    return CapaEffectivenessReview.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        review_criteria="Zero ferrule cracking across 5 consecutive lots (Cpk >= 1.33).",
        verification_method="statistical_sample",
        planned_review_date=timezone.now().date() + timedelta(days=30),
        evaluator=admin_user,
        status="scheduled",
    )


@pytest.fixture
def capa_effectiveness_review_b(db, tenant_b, admin_b, capa_investigation_b):
    """Local fixture override for CapaEffectivenessReview in Tenant B."""
    return CapaEffectivenessReview.objects.create(
        tenant=tenant_b,
        capa=capa_investigation_b,
        review_criteria="Thermal resistance remains below 0.3 C/W over 1,000 burn-in hours.",
        verification_method="trend_analysis",
        planned_review_date=timezone.now().date() + timedelta(days=60),
        evaluator=admin_b,
        status="scheduled",
    )


# =====================================================================
# Helper Factories (Prefix: _capamanagement_*)
# =====================================================================

def _capamanagement_create_investigation(tenant, lead_investigator, quality_owner, **kwargs):
    """Helper creating a CapaInvestigation with default parameters."""
    data = {
        "tenant": tenant,
        "title": "Default Investigation Test Case",
        "issue_summary": "Issue summary detailing defect condition and observation parameters.",
        "action_type": "corrective",
        "source_type": "ncr",
        "risk_priority": "medium",
        "status": "draft",
        "lead_investigator": lead_investigator,
        "quality_owner": quality_owner,
    }
    data.update(kwargs)
    return CapaInvestigation.objects.create(**data)


def _capamanagement_create_rca(tenant, capa, lead_investigator, **kwargs):
    """Helper creating a RootCauseAnalysis with default parameters."""
    data = {
        "tenant": tenant,
        "capa": capa,
        "rca_method": "5_whys",
        "problem_statement": "Default problem statement describing the investigated failure.",
        "root_cause_summary": "Default root cause summary describing the verified causal mechanism.",
        "root_cause_category": "process",
        "status": "draft",
        "lead_investigator": lead_investigator,
    }
    data.update(kwargs)
    return RootCauseAnalysis.objects.create(**data)


def _capamanagement_create_action(tenant, capa, assigned_to, **kwargs):
    """Helper creating a CapaAction with default parameters."""
    data = {
        "tenant": tenant,
        "capa": capa,
        "action_type": "corrective",
        "title": "Default Remediation Action",
        "description": "Step-by-step remediation procedure and deliverable verification protocol.",
        "assigned_to": assigned_to,
        "due_date": timezone.now().date() + timedelta(days=14),
        "status": "pending",
    }
    data.update(kwargs)
    return CapaAction.objects.create(**data)


def _capamanagement_create_review(tenant, capa, evaluator, **kwargs):
    """Helper creating a CapaEffectivenessReview with default parameters."""
    data = {
        "tenant": tenant,
        "capa": capa,
        "review_criteria": "Default acceptance criteria requiring zero defect recurrence.",
        "verification_method": "zero_recurrence_window",
        "planned_review_date": timezone.now().date() + timedelta(days=60),
        "evaluator": evaluator,
        "status": "scheduled",
    }
    data.update(kwargs)
    return CapaEffectivenessReview.objects.create(**data)


# =====================================================================
# 1. CapaInvestigation Tests
# =====================================================================

def test_capamanagement_investigation_auto_number_format(tenant_a, admin_user):
    """Auto-numbering must follow QCAP-##### format."""
    inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user)
    assert inv.number.startswith("QCAP-")
    assert re.match(r"^QCAP-\d{5}$", inv.number) is not None


def test_capamanagement_investigation_sequential_continuity_per_tenant(tenant_a, admin_user):
    """Sequential auto-numbering must increment monotonically per tenant."""
    inv1 = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, title="Investigation 1")
    inv2 = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, title="Investigation 2")
    inv3 = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, title="Investigation 3")

    num1 = int(inv1.number.split("-")[1])
    num2 = int(inv2.number.split("-")[1])
    num3 = int(inv3.number.split("-")[1])
    assert num2 == num1 + 1
    assert num3 == num2 + 1


def test_capamanagement_investigation_multi_tenant_isolation(tenant_a, tenant_b, admin_user, admin_b):
    """Tenant B sequence must be isolated from Tenant A without collisions."""
    inv_a = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, title="Acme Investigation")
    inv_b = _capamanagement_create_investigation(tenant_b, admin_b, admin_b, title="Globex Investigation")

    assert inv_a.tenant != inv_b.tenant
    assert inv_a.number.startswith("QCAP-")
    assert inv_b.number.startswith("QCAP-")
    assert CapaInvestigation.objects.filter(tenant=tenant_a).count() >= 1
    assert CapaInvestigation.objects.filter(tenant=tenant_b).count() >= 1


def test_capamanagement_investigation_str_representation(tenant_a, admin_user):
    """__str__ must return '{number}: {title}'."""
    inv = _capamanagement_create_investigation(
        tenant_a, admin_user, admin_user, title="Laser Power Supply Diode Failure"
    )
    expected = f"{inv.number}: Laser Power Supply Diode Failure"
    assert str(inv) == expected


def test_capamanagement_investigation_default_values(tenant_a, admin_user):
    """Verify standard CAPA regulatory default field values."""
    inv = CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Default Check Investigation",
        issue_summary="Summary of initial problem observations.",
        lead_investigator=admin_user,
        quality_owner=admin_user,
    )
    assert inv.action_type == "corrective"
    assert inv.source_type == "ncr"
    assert inv.risk_priority == "medium"
    assert inv.status == "draft"
    assert inv.containment_actions == ""
    assert inv.containment_implemented is False
    assert inv.containment_verified_by is None
    assert inv.containment_date is None
    assert inv.affected_item_code == ""
    assert inv.affected_item_name == ""
    assert inv.affected_lot_numbers == ""
    assert inv.department is None
    assert inv.design_project is None
    assert inv.risk_assessment is None
    assert inv.target_investigation_date is None
    assert inv.target_closure_date is None
    assert inv.is_escalated is False
    assert inv.escalation_reason == ""
    assert inv.escalated_at is None
    assert inv.closure_summary == ""
    assert inv.closed_at is None
    assert inv.closure_approved_by is None
    assert inv.formal_closure_signature is None


def test_capamanagement_investigation_action_type_choices_and_badges(tenant_a, admin_user):
    """Verify action type choices and valid CSS badge mappings."""
    types = [c[0] for c in CapaInvestigation.ACTION_TYPE_CHOICES]
    assert "corrective" in types
    assert "preventive" in types

    for act_type in ["corrective", "preventive"]:
        inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, action_type=act_type)
        assert inv.action_type_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = CapaInvestigation(action_type="unknown_type")
    assert unmapped.action_type_badge == "badge-slate"


def test_capamanagement_investigation_source_type_choices_and_badges(tenant_a, admin_user):
    """Verify source type choices and CSS badges."""
    sources = [c[0] for c in CapaInvestigation.SOURCE_TYPE_CHOICES]
    expected_sources = [
        "ncr", "complaint", "internal_audit", "external_audit",
        "deviation", "risk_assessment", "management_review", "other",
    ]
    for src in expected_sources:
        assert src in sources
        inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, source_type=src)
        assert inv.source_type_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = CapaInvestigation(source_type="unknown_source")
    assert unmapped.source_type_badge == "badge-slate"


def test_capamanagement_investigation_risk_priority_choices_and_badges(tenant_a, admin_user):
    """Verify risk priority choices and CSS badges."""
    priorities = [c[0] for c in CapaInvestigation.RISK_PRIORITY_CHOICES]
    expected_priorities = ["low", "medium", "high", "critical"]
    for prio in expected_priorities:
        assert prio in priorities
        inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, risk_priority=prio)
        assert inv.risk_priority_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = CapaInvestigation(risk_priority="unknown_priority")
    assert unmapped.risk_priority_badge == "badge-slate"


def test_capamanagement_investigation_status_choices_and_badges(tenant_a, admin_user):
    """Verify lifecycle status choices and CSS badges."""
    statuses = [c[0] for c in CapaInvestigation.STATUS_CHOICES]
    expected_statuses = [
        "draft", "under_investigation", "rca_in_progress", "action_plan_dev",
        "action_implementation", "effectiveness_review", "closed", "voided",
    ]
    for st in expected_statuses:
        assert st in statuses
        inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, status=st)
        assert inv.status_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = CapaInvestigation(status="unknown_status")
    assert unmapped.status_badge == "badge-slate"


def test_capamanagement_investigation_days_open_property(tenant_a, admin_user):
    """Verify days_open calculation for active, closed, and unpersisted investigations."""
    # Unpersisted object without created_at returns 0
    unpersisted = CapaInvestigation()
    assert unpersisted.days_open == 0

    # Active investigation open since today
    inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user)
    assert inv.days_open >= 0

    # Investigation with past created_at date
    past_date = timezone.now() - timedelta(days=15)
    CapaInvestigation.objects.filter(pk=inv.pk).update(created_at=past_date)
    inv.refresh_from_db()
    assert inv.days_open == 15

    # Closed investigation uses closed_at instead of today
    closure_date = past_date + timedelta(days=10)
    inv.closed_at = closure_date
    inv.status = "closed"
    inv.save(update_fields=["closed_at", "status"])
    assert inv.days_open == 10


def test_capamanagement_investigation_is_overdue_property(tenant_a, admin_user):
    """is_overdue returns True only when target_closure_date is past and status is not closed/voided."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    # Active status with past due date -> Overdue
    inv_overdue = _capamanagement_create_investigation(
        tenant_a, admin_user, admin_user, status="under_investigation", target_closure_date=yesterday
    )
    assert inv_overdue.is_overdue is True

    # Active status with future due date -> Not overdue
    inv_future = _capamanagement_create_investigation(
        tenant_a, admin_user, admin_user, status="under_investigation", target_closure_date=tomorrow
    )
    assert inv_future.is_overdue is False

    # Closed status with past due date -> Not overdue
    inv_closed = _capamanagement_create_investigation(
        tenant_a, admin_user, admin_user, status="closed", target_closure_date=yesterday
    )
    assert inv_closed.is_overdue is False

    # Voided status with past due date -> Not overdue
    inv_voided = _capamanagement_create_investigation(
        tenant_a, admin_user, admin_user, status="voided", target_closure_date=yesterday
    )
    assert inv_voided.is_overdue is False

    # No target closure date set -> Not overdue
    inv_nodate = _capamanagement_create_investigation(
        tenant_a, admin_user, admin_user, status="under_investigation", target_closure_date=None
    )
    assert inv_nodate.is_overdue is False


def test_capamanagement_investigation_actions_count_property(tenant_a, admin_user, quality_department):
    """Verify actions_count calculates dynamically and respects queryset annotation in __dict__."""
    inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user)
    assert inv.actions_count == 0

    _capamanagement_create_action(tenant_a, inv, admin_user, title="Action 1")
    _capamanagement_create_action(tenant_a, inv, admin_user, title="Action 2")
    assert inv.actions_count == 2

    # Verify queryset annotation override in __dict__
    inv.__dict__["actions_count"] = 99
    assert inv.actions_count == 99


def test_capamanagement_investigation_pending_actions_count_property(tenant_a, admin_user, quality_department):
    """Verify pending_actions_count excludes implemented, verified, and cancelled actions."""
    inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user)

    _capamanagement_create_action(tenant_a, inv, admin_user, status="pending")
    _capamanagement_create_action(tenant_a, inv, admin_user, status="in_progress")
    _capamanagement_create_action(tenant_a, inv, admin_user, status="implemented")
    _capamanagement_create_action(tenant_a, inv, admin_user, status="verified")
    _capamanagement_create_action(tenant_a, inv, admin_user, status="cancelled")

    # Only pending and in_progress count
    assert inv.pending_actions_count == 2

    # Verify annotation override
    inv.__dict__["pending_actions_count"] = 42
    assert inv.pending_actions_count == 42


def test_capamanagement_investigation_rca_count_property(tenant_a, admin_user):
    """Verify rca_count returns the number of linked RootCauseAnalysis records."""
    inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user)
    assert inv.rca_count == 0

    _capamanagement_create_rca(tenant_a, inv, admin_user, problem_statement="Problem 1")
    _capamanagement_create_rca(tenant_a, inv, admin_user, problem_statement="Problem 2")
    assert inv.rca_count == 2


def test_capamanagement_investigation_status_workflow(tenant_a, admin_user):
    """Verify progressive lifecycle status progression through closure."""
    inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, status="draft")
    assert inv.status == "draft"

    inv.status = "under_investigation"
    inv.save(update_fields=["status"])
    assert inv.status == "under_investigation"

    inv.status = "rca_in_progress"
    inv.save(update_fields=["status"])
    assert inv.status == "rca_in_progress"

    inv.status = "action_plan_dev"
    inv.save(update_fields=["status"])
    assert inv.status == "action_plan_dev"

    inv.status = "action_implementation"
    inv.save(update_fields=["status"])
    assert inv.status == "action_implementation"

    inv.status = "effectiveness_review"
    inv.save(update_fields=["status"])
    assert inv.status == "effectiveness_review"

    inv.status = "closed"
    inv.closed_at = timezone.now()
    inv.closure_summary = "All CAPA corrective actions fully implemented and verified effective."
    inv.closure_approved_by = admin_user
    inv.save()
    assert inv.status == "closed"
    assert inv.closure_approved_by == admin_user
    assert inv.closure_summary != ""


def test_capamanagement_investigation_containment_execution(tenant_a, admin_user):
    """Verify recording of immediate stop-gap containment actions."""
    today = timezone.now().date()
    inv = _capamanagement_create_investigation(
        tenant_a,
        admin_user,
        admin_user,
        containment_actions="Quarantine lots 101 and 102; halt cleanroom sealing line B.",
        containment_implemented=True,
        containment_verified_by=admin_user,
        containment_date=today,
    )
    assert inv.containment_implemented is True
    assert inv.containment_verified_by == admin_user
    assert inv.containment_date == today


def test_capamanagement_investigation_escalation_protocol(tenant_a, admin_user):
    """Verify executive quality management escalation trigger fields."""
    now = timezone.now()
    inv = _capamanagement_create_investigation(
        tenant_a,
        admin_user,
        admin_user,
        is_escalated=True,
        escalation_reason="Critical patient safety risk: class I potential defect identified during root cause.",
        escalated_at=now,
    )
    assert inv.is_escalated is True
    assert "class I" in inv.escalation_reason
    assert inv.escalated_at == now


def test_capamanagement_investigation_indexes_and_constraints(tenant_a, admin_user):
    """Verify model indexes and unique constraints configuration."""
    indexes = [idx.name for idx in CapaInvestigation._meta.indexes]
    expected_indexes = [
        "idx_qcap_ten_status",
        "idx_qcap_ten_act_type",
        "idx_qcap_ten_dept",
        "idx_qcap_ten_src_type",
        "idx_qcap_ten_risk_pri",
        "idx_qcap_ten_tgt_date",
        "idx_qcap_ten_created",
    ]
    for idx_name in expected_indexes:
        assert idx_name in indexes

    constraints = [c.name for c in CapaInvestigation._meta.constraints]
    assert "quality_qcap_ten_num_uniq" in constraints

    # Duplicate tenant + number integrity violation
    inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user)
    dup = CapaInvestigation(
        tenant=tenant_a,
        number=inv.number,
        title="Duplicate Number",
        issue_summary="Test summary",
        lead_investigator=admin_user,
        quality_owner=admin_user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup.save()


def test_capamanagement_investigation_protected_fk_relations(tenant_a, admin_user):
    """Protected ForeignKey fields (lead_investigator, quality_owner) reject deletion of User."""
    lead = User.objects.create_user(username="lead_qa", email="lead@example.com", password="pwd")
    owner = User.objects.create_user(username="owner_qa", email="owner@example.com", password="pwd")

    inv = _capamanagement_create_investigation(tenant_a, lead, owner)

    with pytest.raises(ProtectedError):
        lead.delete()

    with pytest.raises(ProtectedError):
        owner.delete()

    assert CapaInvestigation.objects.filter(pk=inv.pk).exists()


# =====================================================================
# 2. RootCauseAnalysis Tests
# =====================================================================

def test_capamanagement_rca_auto_number_format(tenant_a, admin_user, capa_investigation_a):
    """Auto-numbering must follow QRCA-##### format."""
    rca = _capamanagement_create_rca(tenant_a, capa_investigation_a, admin_user)
    assert rca.number.startswith("QRCA-")
    assert re.match(r"^QRCA-\d{5}$", rca.number) is not None


def test_capamanagement_rca_sequential_continuity_per_tenant(tenant_a, admin_user, capa_investigation_a):
    """RCA auto-numbering increments sequentially per tenant."""
    r1 = _capamanagement_create_rca(tenant_a, capa_investigation_a, admin_user, problem_statement="RCA 1")
    r2 = _capamanagement_create_rca(tenant_a, capa_investigation_a, admin_user, problem_statement="RCA 2")

    num1 = int(r1.number.split("-")[1])
    num2 = int(r2.number.split("-")[1])
    assert num2 == num1 + 1


def test_capamanagement_rca_str_representation_with_and_without_capa(tenant_a, admin_user, capa_investigation_a):
    """__str__ must format as '{number}: {rca_method_display} ({capa_num or Unassigned})'."""
    rca = _capamanagement_create_rca(
        tenant_a, capa_investigation_a, admin_user, rca_method="5_whys"
    )
    expected = f"{rca.number}: 5 Whys Root Cause Ladder ({capa_investigation_a.number})"
    assert str(rca) == expected

    # Without capa (unassigned / in-memory without capa_id)
    unassigned_rca = RootCauseAnalysis(
        tenant=tenant_a,
        rca_method="fishbone_ishikawa",
        problem_statement="Unassigned test",
    )
    expected_unassigned = "New: Ishikawa 6M Fishbone Diagram (Unassigned)"
    assert str(unassigned_rca) == expected_unassigned


def test_capamanagement_rca_five_whys_ladder(tenant_a, admin_user, capa_investigation_a):
    """Verify 5 Whys causal chain fields and why_levels_count property."""
    rca = _capamanagement_create_rca(
        tenant_a,
        capa_investigation_a,
        admin_user,
        rca_method="5_whys",
        why_1="Ferrule wall thickness was below nominal tolerance.",
        why_2="Core pin experienced wear past limit.",
        why_3="Preventive maintenance schedule lacked metrology check.",
    )
    assert rca.why_levels_count == 3

    # Add why_4 and why_5
    rca.why_4 = "Maintenance SOP omitted critical core dimension."
    rca.why_5 = "No periodic verification protocol was established."
    rca.save()
    assert rca.why_levels_count == 5

    # Completely blank whys
    blank_rca = RootCauseAnalysis(rca_method="5_whys")
    assert blank_rca.why_levels_count == 0


def test_capamanagement_rca_ishikawa_6m_categories(tenant_a, admin_user, capa_investigation_a):
    """Verify Ishikawa fishbone 6M defect categorization fields and escape point analysis."""
    rca = _capamanagement_create_rca(
        tenant_a,
        capa_investigation_a,
        admin_user,
        rca_method="fishbone_ishikawa",
        fishbone_manpower="Operator fatigue during night shift led to skipped manual check.",
        fishbone_machine="Injection mold heater band temperature fluctuated by 12C.",
        fishbone_material="Resin batch moisture level was 0.08% instead of <= 0.02%.",
        fishbone_method="Cooling cycle time reduced from 25s to 18s in recipe rev B.",
        fishbone_measurement="Caliper gauge calibration was expired by 3 weeks.",
        fishbone_environment="Cleanroom relative humidity dropped to 22% causing static.",
        escape_point_gap="Incoming visual inspection does not inspect wall thickness.",
    )
    assert "fatigue" in rca.fishbone_manpower
    assert "heater band" in rca.fishbone_machine
    assert "moisture" in rca.fishbone_material
    assert "Cooling cycle" in rca.fishbone_method
    assert "Caliper gauge" in rca.fishbone_measurement
    assert "humidity" in rca.fishbone_environment
    assert "visual inspection" in rca.escape_point_gap


def test_capamanagement_rca_choices_and_badges(tenant_a, admin_user, capa_investigation_a):
    """Verify RCA methodology, root cause category, and status choices with valid CSS badges."""
    methods = [c[0] for c in RootCauseAnalysis.RCA_METHOD_CHOICES]
    expected_methods = ["5_whys", "fishbone_ishikawa", "8d", "fault_tree", "barrier_analysis", "other"]
    for m in expected_methods:
        assert m in methods
        rca = _capamanagement_create_rca(tenant_a, capa_investigation_a, admin_user, rca_method=m)
        assert rca.method_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    categories = [c[0] for c in RootCauseAnalysis.ROOT_CAUSE_CATEGORY_CHOICES]
    expected_cats = [
        "design", "process", "supplier", "equipment", "human_error",
        "documentation", "training", "environmental", "software", "other",
    ]
    for cat in expected_cats:
        assert cat in categories
        rca = _capamanagement_create_rca(tenant_a, capa_investigation_a, admin_user, root_cause_category=cat)
        assert rca.category_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    statuses = [c[0] for c in RootCauseAnalysis.STATUS_CHOICES]
    expected_statuses = ["draft", "in_progress", "completed", "verified", "rejected"]
    for st in expected_statuses:
        assert st in statuses
        rca = _capamanagement_create_rca(tenant_a, capa_investigation_a, admin_user, status=st)
        assert rca.status_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = RootCauseAnalysis(rca_method="unknown", root_cause_category="unknown", status="unknown")
    assert unmapped.method_badge == "badge-slate"
    assert unmapped.category_badge == "badge-slate"
    assert unmapped.status_badge == "badge-slate"


def test_capamanagement_rca_verification_metadata_and_property(tenant_a, admin_user, capa_investigation_a):
    """is_verified property requires both status == 'verified' and verified_by is not None."""
    rca = _capamanagement_create_rca(tenant_a, capa_investigation_a, admin_user, status="completed")
    assert rca.is_verified is False

    # Status verified but verified_by is None -> False
    rca.status = "verified"
    assert rca.is_verified is False

    # Status verified and verified_by is populated -> True
    rca.verified_by = admin_user
    rca.verified_date = timezone.now().date()
    rca.verification_notes = "Independent engineering verification confirms tooling wear as definitive root cause."
    rca.save()
    assert rca.is_verified is True

    # Status reverted to in_progress with verified_by set -> False
    rca.status = "in_progress"
    assert rca.is_verified is False


def test_capamanagement_rca_cascade_on_investigation_deletion(tenant_a, admin_user, quality_department):
    """Deleting parent CapaInvestigation cascades to delete all linked RootCauseAnalysis rows."""
    inv = _capamanagement_create_investigation(tenant_a, admin_user, admin_user)
    rca1 = _capamanagement_create_rca(tenant_a, inv, admin_user, problem_statement="RCA 1")
    rca2 = _capamanagement_create_rca(tenant_a, inv, admin_user, problem_statement="RCA 2")

    rca1_pk = rca1.pk
    rca2_pk = rca2.pk

    inv.delete()
    assert not RootCauseAnalysis.objects.filter(pk__in=[rca1_pk, rca2_pk]).exists()


def test_capamanagement_rca_indexes_and_constraints(tenant_a, admin_user, capa_investigation_a):
    """Verify RCA compound indexes and tenant unique constraint."""
    indexes = [idx.name for idx in RootCauseAnalysis._meta.indexes]
    expected_indexes = [
        "idx_qrca_ten_capa",
        "idx_qrca_ten_method",
        "idx_qrca_ten_rc_cat",
        "idx_qrca_ten_status",
        "idx_qrca_ten_created",
    ]
    for idx_name in expected_indexes:
        assert idx_name in indexes

    constraints = [c.name for c in RootCauseAnalysis._meta.constraints]
    assert "quality_qrca_ten_num_uniq" in constraints


# =====================================================================
# 3. CapaAction Tests
# =====================================================================

def test_capamanagement_action_auto_number_format(tenant_a, admin_user, capa_investigation_a):
    """Auto-numbering must follow QACT-##### format."""
    act = _capamanagement_create_action(tenant_a, capa_investigation_a, admin_user)
    assert act.number.startswith("QACT-")
    assert re.match(r"^QACT-\d{5}$", act.number) is not None


def test_capamanagement_action_action_types_and_badges(tenant_a, admin_user, capa_investigation_a):
    """Verify action type choices and valid CSS badge mappings."""
    action_types = [c[0] for c in CapaAction.ACTION_TYPE_CHOICES]
    expected_types = ["containment", "corrective", "preventive"]
    for t in expected_types:
        assert t in action_types
        act = _capamanagement_create_action(tenant_a, capa_investigation_a, admin_user, action_type=t)
        assert act.action_type_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = CapaAction(action_type="unknown_type")
    assert unmapped.action_type_badge == "badge-slate"


def test_capamanagement_action_status_choices_and_badges(tenant_a, admin_user, capa_investigation_a):
    """Verify action status choices and valid CSS badge mappings."""
    statuses = [c[0] for c in CapaAction.STATUS_CHOICES]
    expected_statuses = ["pending", "in_progress", "implemented", "verified", "cancelled"]
    for st in expected_statuses:
        assert st in statuses
        act = _capamanagement_create_action(tenant_a, capa_investigation_a, admin_user, status=st)
        assert act.status_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = CapaAction(status="unknown_status")
    assert unmapped.status_badge == "badge-slate"


def test_capamanagement_action_str_representation_with_and_without_capa(tenant_a, admin_user, capa_investigation_a):
    """__str__ must format as '{number}: {title} ({capa_num or Unassigned})'."""
    act = _capamanagement_create_action(
        tenant_a, capa_investigation_a, admin_user, title="Mandate Dual-Signoff SOP"
    )
    expected = f"{act.number}: Mandate Dual-Signoff SOP ({capa_investigation_a.number})"
    assert str(act) == expected

    unassigned_act = CapaAction(title="Unassigned Task Action")
    expected_unassigned = "New: Unassigned Task Action (Unassigned)"
    assert str(unassigned_act) == expected_unassigned


def test_capamanagement_action_is_overdue_property(tenant_a, admin_user, capa_investigation_a):
    """is_overdue returns True when due_date is past and status is pending or in_progress."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    # Pending with past due date -> Overdue
    act_overdue = _capamanagement_create_action(
        tenant_a, capa_investigation_a, admin_user, status="pending", due_date=yesterday
    )
    assert act_overdue.is_overdue is True

    # In progress with past due date -> Overdue
    act_inp = _capamanagement_create_action(
        tenant_a, capa_investigation_a, admin_user, status="in_progress", due_date=yesterday
    )
    assert act_inp.is_overdue is True

    # Pending with future due date -> Not overdue
    act_future = _capamanagement_create_action(
        tenant_a, capa_investigation_a, admin_user, status="pending", due_date=tomorrow
    )
    assert act_future.is_overdue is False

    # Implemented with past due date -> Not overdue
    act_impl = _capamanagement_create_action(
        tenant_a, capa_investigation_a, admin_user, status="implemented", due_date=yesterday
    )
    assert act_impl.is_overdue is False

    # Verified with past due date -> Not overdue
    act_ver = _capamanagement_create_action(
        tenant_a, capa_investigation_a, admin_user, status="verified", due_date=yesterday
    )
    assert act_ver.is_overdue is False

    # Cancelled with past due date -> Not overdue
    act_canc = _capamanagement_create_action(
        tenant_a, capa_investigation_a, admin_user, status="cancelled", due_date=yesterday
    )
    assert act_canc.is_overdue is False


def test_capamanagement_action_verification_metadata_and_property(tenant_a, admin_user, capa_investigation_a):
    """is_verified requires status == 'verified' and verified_by is not None."""
    act = _capamanagement_create_action(tenant_a, capa_investigation_a, admin_user, status="implemented")
    act.completion_date = timezone.now().date()
    act.implementation_notes = "Training completed for 24 technicians across 3 production shifts."
    act.save()
    assert act.is_verified is False

    # Move to verified
    act.status = "verified"
    act.verified_by = admin_user
    act.verified_on = timezone.now().date()
    act.verification_evidence = "Audited training sign-in sheets and verified revised tooling metrology records."
    act.save()
    assert act.is_verified is True


def test_capamanagement_action_cross_module_spine_links(
    tenant_a, admin_user, capa_investigation_a, root_cause_analysis_a,
    quality_doc_draft, quality_dco, design_project_a
):
    """Verify integration ForeignKeys linking QMS Document Control and Design Controls."""
    act = _capamanagement_create_action(
        tenant_a,
        capa_investigation_a,
        admin_user,
        root_cause=root_cause_analysis_a,
        controlled_document=quality_doc_draft,
        change_order=quality_dco,
        design_project=design_project_a,
    )
    assert act.root_cause == root_cause_analysis_a
    assert act.controlled_document == quality_doc_draft
    assert act.change_order == quality_dco
    assert act.design_project == design_project_a


def test_capamanagement_action_cascade_and_set_null_rules(
    tenant_a, admin_user, capa_investigation_a, root_cause_analysis_a
):
    """Deleting parent investigation cascades; deleting root_cause sets null."""
    act = _capamanagement_create_action(
        tenant_a, capa_investigation_a, admin_user, root_cause=root_cause_analysis_a
    )
    act_pk = act.pk

    # Deleting root_cause does NOT delete action, but nulls root_cause
    root_cause_analysis_a.delete()
    act.refresh_from_db()
    assert act.root_cause is None

    # Deleting capa cascades to delete action
    capa_investigation_a.delete()
    assert not CapaAction.objects.filter(pk=act_pk).exists()


def test_capamanagement_action_indexes_and_constraints(tenant_a, admin_user, capa_investigation_a):
    """Verify CapaAction indexes and tenant unique constraint."""
    indexes = [idx.name for idx in CapaAction._meta.indexes]
    expected_indexes = [
        "idx_qact_ten_capa",
        "idx_qact_ten_act_type",
        "idx_qact_ten_dept",
        "idx_qact_ten_status",
        "idx_qact_ten_due_date",
        "idx_qact_ten_created",
    ]
    for idx_name in expected_indexes:
        assert idx_name in indexes

    constraints = [c.name for c in CapaAction._meta.constraints]
    assert "quality_qact_ten_num_uniq" in constraints


# =====================================================================
# 4. CapaEffectivenessReview Tests
# =====================================================================

def test_capamanagement_review_auto_number_format(tenant_a, admin_user, capa_investigation_a):
    """Auto-numbering must follow QEFF-##### format."""
    rev = _capamanagement_create_review(tenant_a, capa_investigation_a, admin_user)
    assert rev.number.startswith("QEFF-")
    assert re.match(r"^QEFF-\d{5}$", rev.number) is not None


def test_capamanagement_review_verification_methods_and_badges(tenant_a, admin_user, capa_investigation_a):
    """Verify verification methodology choices and CSS badges."""
    methods = [c[0] for c in CapaEffectivenessReview.METHOD_CHOICES]
    expected_methods = [
        "statistical_sample", "trend_analysis", "audit_recheck",
        "process_capability", "zero_recurrence_window",
    ]
    for m in expected_methods:
        assert m in methods
        rev = _capamanagement_create_review(tenant_a, capa_investigation_a, admin_user, verification_method=m)
        assert rev.method_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = CapaEffectivenessReview(verification_method="unknown_method")
    assert unmapped.method_badge == "badge-slate"


def test_capamanagement_review_outcomes_and_badges(tenant_a, admin_user, capa_investigation_a):
    """Verify outcome determination choices and CSS badges."""
    outcomes = [c[0] for c in CapaEffectivenessReview.OUTCOME_CHOICES]
    expected_outcomes = ["pending", "effective", "ineffective", "inconclusive"]
    for out in expected_outcomes:
        assert out in outcomes
        rev = _capamanagement_create_review(tenant_a, capa_investigation_a, admin_user, outcome=out)
        assert rev.outcome_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = CapaEffectivenessReview(outcome="unknown_outcome")
    assert unmapped.outcome_badge == "badge-slate"


def test_capamanagement_review_statuses_and_badges(tenant_a, admin_user, capa_investigation_a):
    """Verify review status choices and CSS badges."""
    statuses = [c[0] for c in CapaEffectivenessReview.STATUS_CHOICES]
    expected_statuses = ["scheduled", "in_progress", "completed", "cancelled"]
    for st in expected_statuses:
        assert st in statuses
        rev = _capamanagement_create_review(tenant_a, capa_investigation_a, admin_user, status=st)
        assert rev.status_badge in _CAPAMANAGEMENT_VALID_BADGE_CLASSES

    unmapped = CapaEffectivenessReview(status="unknown_status")
    assert unmapped.status_badge == "badge-slate"


def test_capamanagement_review_str_representation_with_and_without_capa(tenant_a, admin_user, capa_investigation_a):
    """__str__ must format as '{number}: {outcome_display} ({capa_num or Unassigned})'."""
    rev = _capamanagement_create_review(
        tenant_a, capa_investigation_a, admin_user, outcome="effective"
    )
    expected = f"{rev.number}: Effective — Actions Successful ({capa_investigation_a.number})"
    assert str(rev) == expected

    unassigned_rev = CapaEffectivenessReview(outcome="pending")
    expected_unassigned = "New: Pending Evaluation (Unassigned)"
    assert str(unassigned_rev) == expected_unassigned


def test_capamanagement_review_is_effective_property(tenant_a, admin_user, capa_investigation_a):
    """is_effective property returns True if and only if outcome == 'effective'."""
    rev = _capamanagement_create_review(tenant_a, capa_investigation_a, admin_user, outcome="pending")
    assert rev.is_effective is False

    rev.outcome = "ineffective"
    assert rev.is_effective is False

    rev.outcome = "inconclusive"
    assert rev.is_effective is False

    rev.outcome = "effective"
    assert rev.is_effective is True


def test_capamanagement_review_is_review_overdue_property(tenant_a, admin_user, capa_investigation_a):
    """is_review_overdue returns True when planned_review_date is past and status is scheduled."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    # Scheduled with past planned review date -> Overdue
    rev_overdue = _capamanagement_create_review(
        tenant_a, capa_investigation_a, admin_user, status="scheduled", planned_review_date=yesterday
    )
    assert rev_overdue.is_review_overdue is True

    # Scheduled with future planned review date -> Not overdue
    rev_future = _capamanagement_create_review(
        tenant_a, capa_investigation_a, admin_user, status="scheduled", planned_review_date=tomorrow
    )
    assert rev_future.is_review_overdue is False

    # In progress with past date -> Not overdue (status != 'scheduled')
    rev_inp = _capamanagement_create_review(
        tenant_a, capa_investigation_a, admin_user, status="in_progress", planned_review_date=yesterday
    )
    assert rev_inp.is_review_overdue is False

    # Completed with past date -> Not overdue
    rev_comp = _capamanagement_create_review(
        tenant_a, capa_investigation_a, admin_user, status="completed", planned_review_date=yesterday
    )
    assert rev_comp.is_review_overdue is False


def test_capamanagement_review_recurrence_observed_logic(tenant_a, admin_user, capa_investigation_a):
    """Verify recording of defect recurrence observations during evaluation window."""
    rev = _capamanagement_create_review(
        tenant_a,
        capa_investigation_a,
        admin_user,
        recurrence_observed=True,
        recurrence_details="One ferrule fractured during transit drop test on lot OF-2026-095. Tooling core pin #4 dimension out of spec.",
        outcome="ineffective",
        status="completed",
        actual_review_date=timezone.now().date(),
        review_notes="Effectiveness criteria failed. Reopening investigation and scheduling secondary RCA.",
    )
    assert rev.recurrence_observed is True
    assert "drop test" in rev.recurrence_details
    assert rev.is_effective is False
    assert rev.outcome == "ineffective"


def test_capamanagement_review_electronic_signature_link(
    tenant_a, admin_user, capa_investigation_a, quality_sig
):
    """Verify linking 21 CFR Part 11 ElectronicSignatureRecord for formal QA review closure."""
    rev = _capamanagement_create_review(
        tenant_a,
        capa_investigation_a,
        admin_user,
        outcome="effective",
        status="completed",
        formal_signature=quality_sig,
    )
    assert rev.formal_signature == quality_sig
    assert rev.formal_signature.signer == admin_user


def test_capamanagement_review_indexes_and_constraints(tenant_a, admin_user, capa_investigation_a):
    """Verify CapaEffectivenessReview indexes and tenant unique constraint."""
    indexes = [idx.name for idx in CapaEffectivenessReview._meta.indexes]
    expected_indexes = [
        "idx_qeff_ten_capa",
        "idx_qeff_ten_outcome",
        "idx_qeff_ten_plan_dt",
        "idx_qeff_ten_status",
        "idx_qeff_ten_created",
    ]
    for idx_name in expected_indexes:
        assert idx_name in indexes

    constraints = [c.name for c in CapaEffectivenessReview._meta.constraints]
    assert "quality_qeff_ten_num_uniq" in constraints


# =====================================================================
# 5. Multi-Tenant Isolation & Full Lifecycle Integration Tests
# =====================================================================

def test_capamanagement_multi_tenant_isolation_all_four_models(
    tenant_a, tenant_b, admin_user, admin_b, quality_department, quality_department_b
):
    """Ensure complete tenant isolation and independent numbering across all 4 CAPA models."""
    # Tenant A
    inv_a = _capamanagement_create_investigation(tenant_a, admin_user, admin_user, department=quality_department)
    rca_a = _capamanagement_create_rca(tenant_a, inv_a, admin_user)
    act_a = _capamanagement_create_action(tenant_a, inv_a, admin_user, root_cause=rca_a, department=quality_department)
    rev_a = _capamanagement_create_review(tenant_a, inv_a, admin_user)

    # Tenant B
    inv_b = _capamanagement_create_investigation(tenant_b, admin_b, admin_b, department=quality_department_b)
    rca_b = _capamanagement_create_rca(tenant_b, inv_b, admin_b)
    act_b = _capamanagement_create_action(tenant_b, inv_b, admin_b, root_cause=rca_b, department=quality_department_b)
    rev_b = _capamanagement_create_review(tenant_b, inv_b, admin_b)

    # Numbering prefixes are identical
    assert inv_a.number.startswith("QCAP-")
    assert inv_b.number.startswith("QCAP-")
    assert rca_a.number.startswith("QRCA-")
    assert rca_b.number.startswith("QRCA-")
    assert act_a.number.startswith("QACT-")
    assert act_b.number.startswith("QACT-")
    assert rev_a.number.startswith("QEFF-")
    assert rev_b.number.startswith("QEFF-")

    # Scoped queries do not leak across tenants
    assert not CapaInvestigation.objects.filter(tenant=tenant_a, pk=inv_b.pk).exists()
    assert not CapaInvestigation.objects.filter(tenant=tenant_b, pk=inv_a.pk).exists()
    assert not RootCauseAnalysis.objects.filter(tenant=tenant_a, pk=rca_b.pk).exists()
    assert not RootCauseAnalysis.objects.filter(tenant=tenant_b, pk=rca_a.pk).exists()
    assert not CapaAction.objects.filter(tenant=tenant_a, pk=act_b.pk).exists()
    assert not CapaAction.objects.filter(tenant=tenant_b, pk=act_a.pk).exists()
    assert not CapaEffectivenessReview.objects.filter(tenant=tenant_a, pk=rev_b.pk).exists()
    assert not CapaEffectivenessReview.objects.filter(tenant=tenant_b, pk=rev_a.pk).exists()


def test_capamanagement_full_capa_lifecycle_graph(tenant_a, admin_user, quality_department):
    """Test full progressive workflow across investigation, RCA, remediation action, and review."""
    # 1. Initiate investigation with immediate containment
    inv = _capamanagement_create_investigation(
        tenant_a,
        admin_user,
        admin_user,
        title="Catheter Lumen Occlusion During Flow Testing",
        action_type="corrective",
        source_type="ncr",
        risk_priority="high",
        status="under_investigation",
        department=quality_department,
        containment_actions="Quarantine Lot CATH-2026-44; inspect inventory of 1500 units.",
        containment_implemented=True,
        containment_verified_by=admin_user,
        containment_date=timezone.now().date(),
    )
    assert inv.status == "under_investigation"
    assert inv.actions_count == 0
    assert inv.rca_count == 0

    # 2. Complete RCA
    inv.status = "rca_in_progress"
    inv.save(update_fields=["status"])
    rca = _capamanagement_create_rca(
        tenant_a,
        inv,
        admin_user,
        rca_method="5_whys",
        problem_statement="Lumen cross-section constricted below minimum 0.5mm ID.",
        why_1="Extrusion die temperature exceeded 210C limit.",
        why_2="Thermocouple sensor wire had intermittent ground fault.",
        why_3="Thermocouple calibration check was performed annually rather than monthly.",
        root_cause_summary="Extrusion die overheating due to uncalibrated faulty thermocouple.",
        root_cause_category="equipment",
        status="completed",
    )
    rca.status = "verified"
    rca.verified_by = admin_user
    rca.verified_date = timezone.now().date()
    rca.save()
    assert inv.rca_count == 1
    assert rca.is_verified is True

    # 3. Formulate Action Plan
    inv.status = "action_plan_dev"
    inv.save(update_fields=["status"])
    act = _capamanagement_create_action(
        tenant_a,
        inv,
        admin_user,
        root_cause=rca,
        action_type="corrective",
        title="Replace Extrusion Die Thermocouple and Institute Monthly PM",
        description="Install new dual-redundant Type K thermocouple and update PM interval.",
        department=quality_department,
        status="in_progress",
    )
    assert inv.actions_count == 1
    assert inv.pending_actions_count == 1

    # 4. Implement and verify action
    inv.status = "action_implementation"
    inv.save(update_fields=["status"])
    act.status = "verified"
    act.completion_date = timezone.now().date()
    act.verified_by = admin_user
    act.verified_on = timezone.now().date()
    act.save()
    assert inv.pending_actions_count == 0

    # 5. Conduct effectiveness review
    inv.status = "effectiveness_review"
    inv.save(update_fields=["status"])
    rev = _capamanagement_create_review(
        tenant_a,
        inv,
        admin_user,
        review_criteria="Zero lumen occlusion defects across 10 consecutive production runs.",
        verification_method="statistical_sample",
        planned_review_date=timezone.now().date() + timedelta(days=30),
        status="scheduled",
    )
    rev.status = "completed"
    rev.actual_review_date = timezone.now().date()
    rev.metrics_evaluated = "Sampled 500 catheters across 10 runs; zero occlusions found. Cpk = 1.62."
    rev.recurrence_observed = False
    rev.outcome = "effective"
    rev.save()
    assert rev.is_effective is True

    # 6. Formally close investigation
    inv.status = "closed"
    inv.closure_summary = "All actions verified; 30-day statistical sample confirms effectiveness (Cpk 1.62)."
    inv.closed_at = timezone.now()
    inv.closure_approved_by = admin_user
    inv.save()
    assert inv.status == "closed"
    assert inv.days_open >= 0
