"""
Unit tests for apps/quality models (Sub-module 12.2: Design Controls & Development).

Covers:
- DesignProject [QDPL-]: auto-numbering, device classes, regulatory pathways,
  phases, status workflows, DHF lock logic, compound indexes, tenant isolation.
- DesignInput [QINP-]: auto-numbering, requirement types, priorities, verification
  status (direct query and prefetched cache), hierarchy (user_need_parent), cascading.
- DesignReview [QREV-]: auto-numbering, review stages, gate clearance invariants
  (action items and resolution), independent reviewer requirement (21 CFR § 820.30(e)).
- DesignVerification [QVER-]: auto-numbering, activity types, test methods, sample size,
  pass/fail criteria, is_passed property, links to ControlledDocument protocol & report.
"""

from datetime import timedelta
import re
import pytest
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.quality.models import (
    ControlledDocument,
    DesignInput,
    DesignProject,
    DesignReview,
    DesignVerification,
    ElectronicSignatureRecord,
)

pytestmark = pytest.mark.django_db

_DESIGNCONTROLS_VALID_BADGE_CLASSES = {
    "badge-slate",
    "badge-info",
    "badge-green",
    "badge-amber",
    "badge-red",
    "badge-muted",
}


# =====================================================================
# Module-level Fixtures and Helpers (Prefix: _designcontrols_*)
# =====================================================================


@pytest.fixture
def _designcontrols_org_unit(db, tenant_a):
    return OrgUnit.objects.create(
        tenant=tenant_a,
        name="Biomedical Engineering Dept",
        kind="department",
    )


@pytest.fixture
def _designcontrols_engineer_user(db, tenant_a):
    return User.objects.create_user(
        email="lead.engineer@acme.com",
        username="engineer_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )


@pytest.fixture
def _designcontrols_independent_user(db, tenant_a):
    return User.objects.create_user(
        email="independent.reviewer@acme.com",
        username="reviewer_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )


def _designcontrols_create_project(tenant, project_lead, quality_lead=None, **kwargs):
    if quality_lead is None:
        quality_lead = project_lead
    data = {
        "tenant": tenant,
        "title": "NextGen Infusion Pump System",
        "device_name": "InfuseFlow Pro 3000",
        "device_class": "class_ii",
        "regulatory_pathway": "510k",
        "intended_use": "Volumetric infusion pump for intravenous administration of fluids.",
        "current_phase": "planning",
        "status": "draft",
        "project_lead": project_lead,
        "quality_lead": quality_lead,
        "dhf_locked": False,
        "dhf_location": "DHF/INFUSE-3000/REV-A",
        "description": "Smart infusion pump development under 21 CFR § 820.30.",
    }
    data.update(kwargs)
    return DesignProject.objects.create(**data)


def _designcontrols_create_input(tenant, project, owner, **kwargs):
    data = {
        "tenant": tenant,
        "project": project,
        "identifier": "DI-001",
        "title": "Battery Backup Duration",
        "input_type": "functional",
        "priority": "major",
        "status": "draft",
        "description": "Device must operate on internal battery power during patient transport.",
        "acceptance_criteria": "Continuous infusion delivery for at least 8 hours at 125 mL/hr.",
        "rationale": "Clinical requirement per IEC 60601-2-24.",
        "owner": owner,
        "version": "1.0",
    }
    data.update(kwargs)
    return DesignInput.objects.create(**data)


def _designcontrols_create_review(tenant, project, lead_reviewer, independent_reviewer, **kwargs):
    data = {
        "tenant": tenant,
        "project": project,
        "title": "Design Input Phase Gate Review",
        "review_stage": "input_freeze",
        "review_date": timezone.now().date(),
        "status": "scheduled",
        "lead_reviewer": lead_reviewer,
        "independent_reviewer": independent_reviewer,
        "agenda": "Formal gate review to freeze functional and clinical user needs.",
        "discussion_summary": "Requirements traceability matrix evaluated against ISO 13485.",
        "conclusions": "Requirements deemed objective and testable.",
        "action_items": "",
        "action_items_resolved": False,
    }
    data.update(kwargs)
    return DesignReview.objects.create(**data)


def _designcontrols_create_verification(tenant, project, primary_input, **kwargs):
    data = {
        "tenant": tenant,
        "project": project,
        "primary_input": primary_input,
        "title": "Battery Runtime Bench Test Protocol",
        "activity_type": "verification",
        "status": "draft",
        "test_method": "lab_test",
        "acceptance_criteria": "Unit delivers fluid continuously >= 8 hours without low battery alarm.",
        "pass_fail_result": "pending",
        "results_summary": "",
        "deviation_notes": "",
    }
    data.update(kwargs)
    return DesignVerification.objects.create(**data)


# =====================================================================
# 1. DesignProject Model Tests
# =====================================================================


def test_designcontrols_project_auto_number_format(tenant_a, admin_user):
    """Auto-numbering must follow QDPL-##### format."""
    project = _designcontrols_create_project(tenant_a, admin_user)
    assert project.number.startswith("QDPL-")
    assert re.match(r"^QDPL-\d{5}$", project.number) is not None


def test_designcontrols_project_sequential_continuity_per_tenant(tenant_a, admin_user):
    """Sequential auto-numbering must increment monotonically per tenant."""
    p1 = _designcontrols_create_project(tenant_a, admin_user, title="Project 1")
    p2 = _designcontrols_create_project(tenant_a, admin_user, title="Project 2")
    p3 = _designcontrols_create_project(tenant_a, admin_user, title="Project 3")

    num1 = int(p1.number.split("-")[1])
    num2 = int(p2.number.split("-")[1])
    num3 = int(p3.number.split("-")[1])

    assert num2 == num1 + 1
    assert num3 == num2 + 1


def test_designcontrols_project_multi_tenant_sequence_isolation(tenant_a, tenant_b, admin_user, admin_b):
    """Auto-numbering sequence is isolated per tenant."""
    p_a = _designcontrols_create_project(tenant_a, admin_user, title="Acme Project")
    p_b = _designcontrols_create_project(tenant_b, admin_b, title="Globex Project")

    assert p_a.number == "QDPL-00001"
    assert p_b.number == "QDPL-00001"
    assert p_a.tenant != p_b.tenant


def test_designcontrols_project_str_representation(tenant_a, admin_user):
    """__str__ must format as '<number> — <title>'."""
    project = _designcontrols_create_project(tenant_a, admin_user, title="Syringe Pump v2")
    expected = f"{project.number} — Syringe Pump v2"
    assert str(project) == expected


def test_designcontrols_project_device_class_choices_and_badges(tenant_a, admin_user):
    """Verify device class choices, labels, and badge CSS properties."""
    classes = [c[0] for c in DesignProject.DEVICE_CLASS_CHOICES]
    expected_classes = [
        "class_i", "class_ii", "class_iii",
        "class_a", "class_b", "class_c", "class_d", "unclassified"
    ]
    for cls_name in expected_classes:
        assert cls_name in classes

    for cls_name in expected_classes:
        proj = _designcontrols_create_project(tenant_a, admin_user, device_class=cls_name)
        assert proj.device_class_css in _DESIGNCONTROLS_VALID_BADGE_CLASSES

    # Unknown fallback
    proj_fake = DesignProject(device_class="non_existent")
    assert proj_fake.device_class_css == "badge-slate"


def test_designcontrols_project_regulatory_pathway_choices(tenant_a, admin_user):
    """Verify regulatory pathway enumeration per commercial standards."""
    pathways = [c[0] for c in DesignProject.REGULATORY_PATHWAY_CHOICES]
    expected = ["510k", "pma", "de_novo", "ce_mdr", "ce_ivdr", "health_canada", "exempt", "other"]
    for p in expected:
        assert p in pathways

    proj = _designcontrols_create_project(tenant_a, admin_user, regulatory_pathway="ce_mdr")
    assert proj.regulatory_pathway == "ce_mdr"


def test_designcontrols_project_phase_choices_and_badges(tenant_a, admin_user):
    """Verify design phase choices and phase badge styling."""
    phases = [c[0] for c in DesignProject.CURRENT_PHASE_CHOICES]
    expected_phases = ["planning", "input", "output_verification", "validation", "commercial_closure", "closed"]
    for ph in expected_phases:
        assert ph in phases

    for ph in expected_phases:
        proj = _designcontrols_create_project(tenant_a, admin_user, current_phase=ph)
        assert proj.phase_css in _DESIGNCONTROLS_VALID_BADGE_CLASSES

    proj_fake = DesignProject(current_phase="unknown_phase")
    assert proj_fake.phase_css == "badge-slate"


def test_designcontrols_project_status_choices_and_badges(tenant_a, admin_user):
    """Verify status choices and status badge styling."""
    statuses = [c[0] for c in DesignProject.STATUS_CHOICES]
    expected_statuses = ["draft", "active", "gate_review", "on_hold", "completed", "cancelled"]
    for st in expected_statuses:
        assert st in statuses

    for st in expected_statuses:
        proj = _designcontrols_create_project(tenant_a, admin_user, status=st)
        assert proj.status_css in _DESIGNCONTROLS_VALID_BADGE_CLASSES

    proj_fake = DesignProject(status="unknown_status")
    assert proj_fake.status_css == "badge-slate"


def test_designcontrols_project_default_values(tenant_a, admin_user):
    """Verify model default values on creation."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    assert proj.device_class == "class_ii"
    assert proj.regulatory_pathway == "510k"
    assert proj.current_phase == "planning"
    assert proj.status == "draft"
    assert proj.dhf_locked is False
    assert proj.target_completion_date is None
    assert proj.actual_completion_date is None


def test_designcontrols_project_dhf_locked_logic(tenant_a, admin_user):
    """is_locked property must be True if dhf_locked or status in completed/cancelled."""
    # Active & unlocked
    proj = _designcontrols_create_project(tenant_a, admin_user, status="active", dhf_locked=False)
    assert proj.is_locked is False

    # Explicit DHF lock
    proj.dhf_locked = True
    proj.save()
    assert proj.is_locked is True

    # Completed status locks project
    proj_completed = _designcontrols_create_project(tenant_a, admin_user, status="completed", dhf_locked=False)
    assert proj_completed.is_locked is True

    # Cancelled status locks project
    proj_cancelled = _designcontrols_create_project(tenant_a, admin_user, status="cancelled", dhf_locked=False)
    assert proj_cancelled.is_locked is True

    # Gate review unlocked
    proj_gate = _designcontrols_create_project(tenant_a, admin_user, status="gate_review", dhf_locked=False)
    assert proj_gate.is_locked is False


def test_designcontrols_project_completion_dates_persistence(tenant_a, admin_user):
    """Target and actual completion dates persist accurately."""
    today = timezone.now().date()
    target = today + timedelta(days=180)
    proj = _designcontrols_create_project(
        tenant_a,
        admin_user,
        target_completion_date=target,
        actual_completion_date=today,
    )
    proj.refresh_from_db()
    assert proj.target_completion_date == target
    assert proj.actual_completion_date == today


def test_designcontrols_project_compound_indexes_and_meta(tenant_a):
    """Verify meta options, compound indexes, and unique constraints."""
    meta = DesignProject._meta
    assert meta.ordering == ["-created_at"]

    index_names = [idx.name for idx in meta.indexes]
    assert "idx_qdpl_ten_created" in index_names
    assert "idx_qdpl_ten_status" in index_names
    assert "idx_qdpl_ten_phase" in index_names
    assert "idx_qdpl_ten_dclass" in index_names

    constraint_names = [c.name for c in meta.constraints]
    assert "quality_qdpl_ten_num_uniq" in constraint_names


def test_designcontrols_project_unique_constraint_enforcement(tenant_a, tenant_b, admin_user, admin_b):
    """Database UniqueConstraint prevents duplicate (tenant, number)."""
    p1 = _designcontrols_create_project(tenant_a, admin_user)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DesignProject.objects.create(
                tenant=tenant_a,
                number=p1.number,
                title="Duplicate Number Collision",
                device_name="Device Duplicate",
                project_lead=admin_user,
                quality_lead=admin_user,
            )

    # Cross-tenant same number is allowed
    p_b = DesignProject.objects.create(
        tenant=tenant_b,
        number=p1.number,
        title="Globex Independent Number",
        device_name="Device Globex",
        project_lead=admin_b,
        quality_lead=admin_b,
    )
    assert p_b.number == p1.number
    assert p_b.tenant != p1.tenant


def test_designcontrols_project_protected_leads(tenant_a, _designcontrols_engineer_user):
    """Deleting a user who is project_lead or quality_lead raises ProtectedError."""
    proj = _designcontrols_create_project(
        tenant_a,
        project_lead=_designcontrols_engineer_user,
        quality_lead=_designcontrols_engineer_user,
    )
    with pytest.raises(ProtectedError):
        _designcontrols_engineer_user.delete()


def test_designcontrols_project_department_set_null(tenant_a, admin_user, _designcontrols_org_unit):
    """Deleting OrgUnit department sets project.department to NULL."""
    proj = _designcontrols_create_project(
        tenant_a,
        admin_user,
        department=_designcontrols_org_unit,
    )
    assert proj.department == _designcontrols_org_unit
    _designcontrols_org_unit.delete()
    proj.refresh_from_db()
    assert proj.department is None


# =====================================================================
# 2. DesignInput Model Tests
# =====================================================================


def test_designcontrols_input_auto_number_format(tenant_a, admin_user):
    """Auto-numbering must follow QINP-##### format."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    assert inp.number.startswith("QINP-")
    assert re.match(r"^QINP-\d{5}$", inp.number) is not None


def test_designcontrols_input_sequential_continuity_per_tenant(tenant_a, admin_user):
    """Sequential auto-numbering must increment monotonically per tenant."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    i1 = _designcontrols_create_input(tenant_a, proj, admin_user, identifier="DI-001")
    i2 = _designcontrols_create_input(tenant_a, proj, admin_user, identifier="DI-002")
    i3 = _designcontrols_create_input(tenant_a, proj, admin_user, identifier="DI-003")

    num1 = int(i1.number.split("-")[1])
    num2 = int(i2.number.split("-")[1])
    num3 = int(i3.number.split("-")[1])

    assert num2 == num1 + 1
    assert num3 == num2 + 1


def test_designcontrols_input_multi_tenant_isolation(tenant_a, tenant_b, admin_user, admin_b):
    """Input sequences must start independently per tenant."""
    proj_a = _designcontrols_create_project(tenant_a, admin_user)
    proj_b = _designcontrols_create_project(tenant_b, admin_b)

    inp_a = _designcontrols_create_input(tenant_a, proj_a, admin_user)
    inp_b = _designcontrols_create_input(tenant_b, proj_b, admin_b)

    assert inp_a.number == "QINP-00001"
    assert inp_b.number == "QINP-00001"
    assert inp_a.tenant != inp_b.tenant


def test_designcontrols_input_str_representation(tenant_a, admin_user):
    """__str__ must format as '<identifier> (<number>) — <title>'."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(
        tenant_a,
        proj,
        admin_user,
        identifier="REQ-PWR-01",
        title="Power Supply Isolation",
    )
    expected = f"REQ-PWR-01 ({inp.number}) — Power Supply Isolation"
    assert str(inp) == expected


def test_designcontrols_input_choices_and_badges(tenant_a, admin_user):
    """Verify input types, priorities, and status choices with badge CSS."""
    types = [c[0] for c in DesignInput.INPUT_TYPE_CHOICES]
    expected_types = [
        "user_need", "functional", "performance", "safety",
        "regulatory", "human_factors", "software", "interface", "packaging"
    ]
    for t in expected_types:
        assert t in types

    priorities = [c[0] for c in DesignInput.PRIORITY_CHOICES]
    expected_priorities = ["critical", "major", "minor"]
    for p in expected_priorities:
        assert p in priorities

    statuses = [c[0] for c in DesignInput.STATUS_CHOICES]
    expected_statuses = ["draft", "in_review", "approved", "verified", "deferred", "obsolete"]
    for s in expected_statuses:
        assert s in statuses

    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(
        tenant_a,
        proj,
        admin_user,
        input_type="safety",
        priority="critical",
        status="approved",
    )
    assert inp.input_type_css == "badge-red"
    assert inp.priority_css == "badge-red"
    assert inp.status_css == "badge-info"

    # Fallback badging
    inp_fake = DesignInput(input_type="invalid", priority="invalid", status="invalid")
    assert inp_fake.input_type_css == "badge-slate"
    assert inp_fake.priority_css == "badge-slate"
    assert inp_fake.status_css == "badge-slate"


def test_designcontrols_input_default_values(tenant_a, admin_user):
    """Verify input defaults."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    assert inp.input_type == "functional"
    assert inp.priority == "major"
    assert inp.status == "draft"
    assert inp.version == "1.0"
    assert inp.user_need_parent is None
    assert inp.controlled_document is None


def test_designcontrols_input_is_verified_status_verified(tenant_a, admin_user):
    """is_verified returns True immediately if status is 'verified'."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user, status="verified")
    assert inp.is_verified is True


def test_designcontrols_input_is_verified_direct_query(tenant_a, admin_user):
    """is_verified via direct DB query evaluates associated verifications."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user, status="approved")

    # No verifications
    assert inp.is_verified is False

    # Pending verification
    ver1 = _designcontrols_create_verification(
        tenant_a, proj, inp, pass_fail_result="pending", status="testing"
    )
    assert inp.is_verified is False

    # Failed verification
    ver1.pass_fail_result = "fail"
    ver1.status = "failed"
    ver1.save()
    assert inp.is_verified is False

    # Passing verification added
    ver2 = _designcontrols_create_verification(
        tenant_a, proj, inp, pass_fail_result="pass", status="passed", title="Pass protocol"
    )
    assert inp.is_verified is True


def test_designcontrols_input_is_verified_prefetched_cache(tenant_a, admin_user):
    """is_verified utilizes _prefetched_objects_cache without issuing extra queries."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user, status="approved")
    _designcontrols_create_verification(
        tenant_a, proj, inp, pass_fail_result="pass", status="passed"
    )

    # Prefetch query
    prefetched_inp = DesignInput.objects.prefetch_related("verifications").get(pk=inp.pk)
    assert hasattr(prefetched_inp, "_prefetched_objects_cache")
    assert "verifications" in prefetched_inp._prefetched_objects_cache
    assert prefetched_inp.is_verified is True

    # Test prefetched cache with all failed
    inp_failed = _designcontrols_create_input(tenant_a, proj, admin_user, identifier="DI-FAIL")
    _designcontrols_create_verification(
        tenant_a, proj, inp_failed, pass_fail_result="fail", status="failed"
    )
    prefetched_fail = DesignInput.objects.prefetch_related("verifications").get(pk=inp_failed.pk)
    assert prefetched_fail.is_verified is False


def test_designcontrols_input_hierarchy_user_need_parent(tenant_a, admin_user):
    """User Needs can be parent to derived functional requirements."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    user_need = _designcontrols_create_input(
        tenant_a,
        proj,
        admin_user,
        identifier="UN-001",
        input_type="user_need",
        title="Clinician Portability Need",
    )
    func_spec_1 = _designcontrols_create_input(
        tenant_a,
        proj,
        admin_user,
        identifier="DI-001",
        input_type="functional",
        title="Weight under 2.5 kg",
        user_need_parent=user_need,
    )
    func_spec_2 = _designcontrols_create_input(
        tenant_a,
        proj,
        admin_user,
        identifier="DI-002",
        input_type="functional",
        title="Integrated carry handle",
        user_need_parent=user_need,
    )

    derived = list(user_need.derived_inputs.all())
    assert func_spec_1 in derived
    assert func_spec_2 in derived
    assert len(derived) == 2

    # Deleting parent sets FK to NULL (SET_NULL)
    user_need.delete()
    func_spec_1.refresh_from_db()
    assert func_spec_1.user_need_parent is None


def test_designcontrols_input_controlled_document_link(tenant_a, admin_user):
    """DesignInput links to ControlledDocument specification; SET_NULL on doc deletion."""
    doc = ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Product Requirements Document (PRD)",
        document_type="spec",
        owner=admin_user,
        revision="1.0",
        lifecycle_state="approved",
    )
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user, controlled_document=doc)
    assert inp.controlled_document == doc

    doc.delete()
    inp.refresh_from_db()
    assert inp.controlled_document is None


def test_designcontrols_input_cascade_on_project_delete(tenant_a, admin_user):
    """Deleting DesignProject cascades and removes all associated DesignInputs."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    inp_id = inp.pk

    proj.delete()
    assert not DesignInput.objects.filter(pk=inp_id).exists()


def test_designcontrols_input_protected_owner(tenant_a, _designcontrols_engineer_user):
    """Deleting owner user is prevented via ProtectedError."""
    proj = _designcontrols_create_project(tenant_a, _designcontrols_engineer_user)
    inp = _designcontrols_create_input(tenant_a, proj, _designcontrols_engineer_user)

    with pytest.raises(ProtectedError):
        _designcontrols_engineer_user.delete()


def test_designcontrols_input_indexes_and_meta(tenant_a):
    """Verify input indexes and ordering."""
    meta = DesignInput._meta
    assert meta.ordering == ["project", "identifier", "-created_at"]

    index_names = [idx.name for idx in meta.indexes]
    assert "idx_qinp_ten_project" in index_names
    assert "idx_qinp_ten_type" in index_names
    assert "idx_qinp_ten_status" in index_names

    constraint_names = [c.name for c in meta.constraints]
    assert "quality_qinp_ten_num_uniq" in constraint_names


# =====================================================================
# 3. DesignReview Model Tests
# =====================================================================


def test_designcontrols_review_auto_number_format(tenant_a, admin_user, _designcontrols_independent_user):
    """Auto-numbering must follow QREV-##### format."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    rev = _designcontrols_create_review(tenant_a, proj, admin_user, _designcontrols_independent_user)
    assert rev.number.startswith("QREV-")
    assert re.match(r"^QREV-\d{5}$", rev.number) is not None


def test_designcontrols_review_sequential_continuity_per_tenant(
    tenant_a, admin_user, _designcontrols_independent_user
):
    """Sequential auto-numbering must increment monotonically per tenant."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    r1 = _designcontrols_create_review(tenant_a, proj, admin_user, _designcontrols_independent_user)
    r2 = _designcontrols_create_review(tenant_a, proj, admin_user, _designcontrols_independent_user)
    r3 = _designcontrols_create_review(tenant_a, proj, admin_user, _designcontrols_independent_user)

    num1 = int(r1.number.split("-")[1])
    num2 = int(r2.number.split("-")[1])
    num3 = int(r3.number.split("-")[1])

    assert num2 == num1 + 1
    assert num3 == num2 + 1


def test_designcontrols_review_multi_tenant_isolation(
    tenant_a, tenant_b, admin_user, admin_b, _designcontrols_independent_user
):
    """Review numbering sequence is isolated per tenant."""
    indep_b = User.objects.create_user(
        email="indep@globex.com",
        username="indep_globex",
        password="TestPass123!",
        tenant=tenant_b,
    )
    proj_a = _designcontrols_create_project(tenant_a, admin_user)
    proj_b = _designcontrols_create_project(tenant_b, admin_b)

    rev_a = _designcontrols_create_review(tenant_a, proj_a, admin_user, _designcontrols_independent_user)
    rev_b = _designcontrols_create_review(tenant_b, proj_b, admin_b, indep_b)

    assert rev_a.number == "QREV-00001"
    assert rev_b.number == "QREV-00001"
    assert rev_a.tenant != rev_b.tenant


def test_designcontrols_review_str_representation(tenant_a, admin_user, _designcontrols_independent_user):
    """__str__ must format as '<number> — <review_stage_display> (<title>)'."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    rev = _designcontrols_create_review(
        tenant_a,
        proj,
        admin_user,
        _designcontrols_independent_user,
        title="Input Phase Freeze",
        review_stage="input_freeze",
    )
    expected = f"{rev.number} — Design Input Freeze Gate (Input Phase Freeze)"
    assert str(rev) == expected


def test_designcontrols_review_choices_and_badges(tenant_a, admin_user, _designcontrols_independent_user):
    """Verify review stages and status choices with badge styling."""
    stages = [c[0] for c in DesignReview.REVIEW_STAGE_CHOICES]
    expected_stages = [
        "planning", "concept", "input_freeze", "detailed_design",
        "verification_gate", "validation_gate", "transfer_gate", "post_launch"
    ]
    for st in expected_stages:
        assert st in stages

    statuses = [c[0] for c in DesignReview.STATUS_CHOICES]
    expected_statuses = ["scheduled", "in_progress", "approved", "conditional", "rejected", "cancelled"]
    for s in expected_statuses:
        assert s in statuses

    proj = _designcontrols_create_project(tenant_a, admin_user)
    for st in expected_stages:
        rev = _designcontrols_create_review(
            tenant_a, proj, admin_user, _designcontrols_independent_user, review_stage=st
        )
        assert rev.stage_css in _DESIGNCONTROLS_VALID_BADGE_CLASSES

    for s in expected_statuses:
        rev = _designcontrols_create_review(
            tenant_a, proj, admin_user, _designcontrols_independent_user, status=s
        )
        assert rev.status_css in _DESIGNCONTROLS_VALID_BADGE_CLASSES

    rev_fake = DesignReview(review_stage="fake", status="fake")
    assert rev_fake.stage_css == "badge-slate"
    assert rev_fake.status_css == "badge-slate"


def test_designcontrols_review_default_values(tenant_a, admin_user, _designcontrols_independent_user):
    """Verify review default field values."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    rev = _designcontrols_create_review(tenant_a, proj, admin_user, _designcontrols_independent_user)
    assert rev.review_stage == "input_freeze"
    assert rev.status == "scheduled"
    assert rev.action_items_resolved is False
    assert rev.electronic_signature is None


def test_designcontrols_review_is_cleared_logic(tenant_a, admin_user, _designcontrols_independent_user):
    """
    is_cleared is True only when:
    status == 'approved' AND (action_items_resolved OR no action_items)
    """
    proj = _designcontrols_create_project(tenant_a, admin_user)

    # 1. Approved with no action items -> Cleared
    rev1 = _designcontrols_create_review(
        tenant_a,
        proj,
        admin_user,
        _designcontrols_independent_user,
        status="approved",
        action_items="",
        action_items_resolved=False,
    )
    assert rev1.is_cleared is True

    # 2. Approved with action items unresolved -> NOT Cleared
    rev2 = _designcontrols_create_review(
        tenant_a,
        proj,
        admin_user,
        _designcontrols_independent_user,
        status="approved",
        action_items="Resolve biocompatibility discrepancy per ISO 10993.",
        action_items_resolved=False,
    )
    assert rev2.is_cleared is False

    # 3. Approved with action items resolved -> Cleared
    rev2.action_items_resolved = True
    rev2.save()
    assert rev2.is_cleared is True

    # 4. Conditional approval -> NOT Cleared
    rev3 = _designcontrols_create_review(
        tenant_a,
        proj,
        admin_user,
        _designcontrols_independent_user,
        status="conditional",
        action_items="",
        action_items_resolved=True,
    )
    assert rev3.is_cleared is False

    # 5. Rejected -> NOT Cleared
    rev4 = _designcontrols_create_review(
        tenant_a,
        proj,
        admin_user,
        _designcontrols_independent_user,
        status="rejected",
        action_items="",
        action_items_resolved=True,
    )
    assert rev4.is_cleared is False


def test_designcontrols_review_independent_reviewer_mandatory(tenant_a, admin_user):
    """Independent reviewer is required per 21 CFR § 820.30(e); cannot be null."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DesignReview.objects.create(
                tenant=tenant_a,
                project=proj,
                title="Invalid Review Without Independent Reviewer",
                review_date=timezone.now().date(),
                lead_reviewer=admin_user,
                independent_reviewer=None,
            )


def test_designcontrols_review_electronic_signature_link(
    tenant_a, admin_user, _designcontrols_independent_user
):
    """DesignReview links to 21 CFR Part 11 ElectronicSignatureRecord; SET_NULL on signature delete."""
    doc = ControlledDocument.objects.create(
        tenant=tenant_a,
        title="DHF Gate Signoff Form",
        document_type="form",
        owner=admin_user,
        revision="1.0",
        lifecycle_state="effective",
    )
    sig = ElectronicSignatureRecord(
        tenant=tenant_a,
        document=doc,
        signer=admin_user,
        signer_name="Admin QA Director",
        signer_title="QA Director",
        signature_meaning="quality_approval",
        document_revision="1.0",
        ip_address="127.0.0.1",
        comments="Gate 2 closure approved.",
    )
    sig.verification_hash = sig.generate_hash()
    sig.save()

    proj = _designcontrols_create_project(tenant_a, admin_user)
    rev = _designcontrols_create_review(
        tenant_a,
        proj,
        admin_user,
        _designcontrols_independent_user,
        electronic_signature=sig,
    )
    assert rev.electronic_signature == sig

    sig.delete()
    rev.refresh_from_db()
    assert rev.electronic_signature is None


def test_designcontrols_review_cascade_on_project_delete(
    tenant_a, admin_user, _designcontrols_independent_user
):
    """Deleting DesignProject cascades and removes all associated DesignReviews."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    rev = _designcontrols_create_review(tenant_a, proj, admin_user, _designcontrols_independent_user)
    rev_id = rev.pk

    proj.delete()
    assert not DesignReview.objects.filter(pk=rev_id).exists()


def test_designcontrols_review_protected_reviewers(
    tenant_a, admin_user, _designcontrols_independent_user
):
    """Deleting lead_reviewer or independent_reviewer is protected."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    _designcontrols_create_review(tenant_a, proj, admin_user, _designcontrols_independent_user)

    with pytest.raises(ProtectedError):
        admin_user.delete()

    with pytest.raises(ProtectedError):
        _designcontrols_independent_user.delete()


def test_designcontrols_review_indexes_and_meta(tenant_a):
    """Verify review indexes, ordering, and constraints."""
    meta = DesignReview._meta
    assert meta.ordering == ["project", "-review_date", "-created_at"]

    index_names = [idx.name for idx in meta.indexes]
    assert "idx_qrev_ten_project" in index_names
    assert "idx_qrev_ten_stage" in index_names
    assert "idx_qrev_ten_status" in index_names

    constraint_names = [c.name for c in meta.constraints]
    assert "quality_qrev_ten_num_uniq" in constraint_names


# =====================================================================
# 4. DesignVerification Model Tests
# =====================================================================


def test_designcontrols_verification_auto_number_format(tenant_a, admin_user):
    """Auto-numbering must follow QVER-##### format."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    ver = _designcontrols_create_verification(tenant_a, proj, inp)
    assert ver.number.startswith("QVER-")
    assert re.match(r"^QVER-\d{5}$", ver.number) is not None


def test_designcontrols_verification_sequential_continuity_per_tenant(tenant_a, admin_user):
    """Sequential auto-numbering must increment monotonically per tenant."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    v1 = _designcontrols_create_verification(tenant_a, proj, inp, title="Test 1")
    v2 = _designcontrols_create_verification(tenant_a, proj, inp, title="Test 2")
    v3 = _designcontrols_create_verification(tenant_a, proj, inp, title="Test 3")

    num1 = int(v1.number.split("-")[1])
    num2 = int(v2.number.split("-")[1])
    num3 = int(v3.number.split("-")[1])

    assert num2 == num1 + 1
    assert num3 == num2 + 1


def test_designcontrols_verification_multi_tenant_isolation(tenant_a, tenant_b, admin_user, admin_b):
    """Verification numbering sequence is isolated per tenant."""
    proj_a = _designcontrols_create_project(tenant_a, admin_user)
    proj_b = _designcontrols_create_project(tenant_b, admin_b)

    inp_a = _designcontrols_create_input(tenant_a, proj_a, admin_user)
    inp_b = _designcontrols_create_input(tenant_b, proj_b, admin_b)

    v_a = _designcontrols_create_verification(tenant_a, proj_a, inp_a)
    v_b = _designcontrols_create_verification(tenant_b, proj_b, inp_b)

    assert v_a.number == "QVER-00001"
    assert v_b.number == "QVER-00001"
    assert v_a.tenant != v_b.tenant


def test_designcontrols_verification_str_representation(tenant_a, admin_user):
    """__str__ must format as '<number> — <title> (<pass_fail_result_display>)'."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    ver = _designcontrols_create_verification(
        tenant_a,
        proj,
        inp,
        title="Drop Testing Protocol",
        pass_fail_result="pass",
    )
    expected = f"{ver.number} — Drop Testing Protocol (Pass)"
    assert str(ver) == expected


def test_designcontrols_verification_choices_and_badges(tenant_a, admin_user):
    """Verify activity types, statuses, test methods, result choices and badges."""
    activities = [c[0] for c in DesignVerification.ACTIVITY_TYPE_CHOICES]
    expected_activities = ["verification", "validation", "usability", "process_validation"]
    for act in expected_activities:
        assert act in activities

    statuses = [c[0] for c in DesignVerification.STATUS_CHOICES]
    expected_statuses = ["draft", "approved_protocol", "testing", "passed", "failed", "waived"]
    for s in expected_statuses:
        assert s in statuses

    methods = [c[0] for c in DesignVerification.TEST_METHOD_CHOICES]
    expected_methods = ["inspection", "lab_test", "analysis", "clinical_trial", "demonstration"]
    for m in expected_methods:
        assert m in methods

    results = [c[0] for c in DesignVerification.RESULT_CHOICES]
    expected_results = ["pending", "pass", "fail"]
    for r in expected_results:
        assert r in results

    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    for act in expected_activities:
        ver = _designcontrols_create_verification(tenant_a, proj, inp, activity_type=act)
        assert ver.activity_type_css in _DESIGNCONTROLS_VALID_BADGE_CLASSES

    for s in expected_statuses:
        ver = _designcontrols_create_verification(tenant_a, proj, inp, status=s)
        assert ver.status_css in _DESIGNCONTROLS_VALID_BADGE_CLASSES

    for r in expected_results:
        ver = _designcontrols_create_verification(tenant_a, proj, inp, pass_fail_result=r)
        assert ver.result_css in _DESIGNCONTROLS_VALID_BADGE_CLASSES

    ver_fake = DesignVerification(activity_type="fake", status="fake", pass_fail_result="fake")
    assert ver_fake.activity_type_css == "badge-slate"
    assert ver_fake.status_css == "badge-slate"
    assert ver_fake.result_css == "badge-slate"


def test_designcontrols_verification_default_values(tenant_a, admin_user):
    """Verify verification model default values."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    ver = _designcontrols_create_verification(tenant_a, proj, inp)

    assert ver.activity_type == "verification"
    assert ver.status == "draft"
    assert ver.test_method == "lab_test"
    assert ver.sample_size == 1
    assert ver.pass_fail_result == "pending"
    assert ver.executed_by is None
    assert ver.execution_date is None
    assert ver.protocol_document is None
    assert ver.report_document is None


def test_designcontrols_verification_is_passed_logic(tenant_a, admin_user):
    """is_passed is True ONLY when pass_fail_result == 'pass' AND status == 'passed'."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)

    # 1. Result pass but status testing -> False
    v1 = _designcontrols_create_verification(
        tenant_a, proj, inp, pass_fail_result="pass", status="testing"
    )
    assert v1.is_passed is False

    # 2. Result pass and status passed -> True
    v1.status = "passed"
    v1.save()
    assert v1.is_passed is True

    # 3. Result fail and status failed -> False
    v2 = _designcontrols_create_verification(
        tenant_a, proj, inp, pass_fail_result="fail", status="failed"
    )
    assert v2.is_passed is False

    # 4. Result pending and status draft -> False
    v3 = _designcontrols_create_verification(
        tenant_a, proj, inp, pass_fail_result="pending", status="draft"
    )
    assert v3.is_passed is False


def test_designcontrols_verification_controlled_document_links(tenant_a, admin_user):
    """Protocol and Report documents link to ControlledDocument; SET_NULL on document deletion."""
    protocol = ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Protocol: Occlusion Pressure Sensor Calibration",
        document_type="protocol",
        owner=admin_user,
        revision="1.0",
        lifecycle_state="effective",
    )
    report = ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Report: Final Occlusion Pressure Test Results",
        document_type="record",
        owner=admin_user,
        revision="1.0",
        lifecycle_state="effective",
    )

    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    ver = _designcontrols_create_verification(
        tenant_a,
        proj,
        inp,
        protocol_document=protocol,
        report_document=report,
    )

    assert ver.protocol_document == protocol
    assert ver.report_document == report

    protocol.delete()
    ver.refresh_from_db()
    assert ver.protocol_document is None
    assert ver.report_document == report

    report.delete()
    ver.refresh_from_db()
    assert ver.report_document is None


def test_designcontrols_verification_executed_by_set_null(tenant_a, admin_user, _designcontrols_engineer_user):
    """Deleting executed_by user sets verification.executed_by to NULL."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    ver = _designcontrols_create_verification(
        tenant_a,
        proj,
        inp,
        executed_by=_designcontrols_engineer_user,
        execution_date=timezone.now().date(),
    )
    assert ver.executed_by == _designcontrols_engineer_user

    _designcontrols_engineer_user.delete()
    ver.refresh_from_db()
    assert ver.executed_by is None


def test_designcontrols_verification_cascade_on_project_delete(tenant_a, admin_user):
    """Deleting DesignProject cascades and removes all associated DesignVerifications."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    ver = _designcontrols_create_verification(tenant_a, proj, inp)
    ver_id = ver.pk

    proj.delete()
    assert not DesignVerification.objects.filter(pk=ver_id).exists()


def test_designcontrols_verification_cascade_on_input_delete(tenant_a, admin_user):
    """Deleting primary DesignInput cascades and removes all associated DesignVerifications."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    ver = _designcontrols_create_verification(tenant_a, proj, inp)
    ver_id = ver.pk

    inp.delete()
    assert not DesignVerification.objects.filter(pk=ver_id).exists()


def test_designcontrols_verification_indexes_and_meta(tenant_a):
    """Verify verification indexes, ordering, and constraints."""
    meta = DesignVerification._meta
    assert meta.ordering == ["project", "primary_input", "-created_at"]

    index_names = [idx.name for idx in meta.indexes]
    assert "idx_qver_ten_project" in index_names
    assert "idx_qver_ten_input" in index_names
    assert "idx_qver_ten_acttype" in index_names
    assert "idx_qver_ten_status" in index_names
    assert "idx_qver_ten_result" in index_names

    constraint_names = [c.name for c in meta.constraints]
    assert "quality_qver_ten_num_uniq" in constraint_names


# =====================================================================
# 5. Full End-to-End Design Controls Traceability Matrix Tests
# =====================================================================


def test_designcontrols_full_traceability_matrix_workflow(
    tenant_a, admin_user, _designcontrols_independent_user
):
    """
    Simulates a compliant 21 CFR § 820.30 Design Controls flow:
    1. Project created and scoped
    2. User Need input documented
    3. Derived Functional Spec input linked to User Need
    4. Verification Protocol executed, tested, and passed
    5. Input marked verified via passing verification
    6. Gate Review held with independent reviewer, action items recorded and cleared
    7. Project DHF locked upon design transfer readiness
    """
    # 1. Project Creation
    project = _designcontrols_create_project(
        tenant_a,
        admin_user,
        title="Pulse Oximeter Transducer",
        device_name="OxiPulse Pro",
        device_class="class_ii",
        regulatory_pathway="510k",
        current_phase="planning",
        status="active",
    )
    assert project.number.startswith("QDPL-")
    assert project.is_locked is False

    # 2. User Need
    user_need = _designcontrols_create_input(
        tenant_a,
        project,
        admin_user,
        identifier="UN-SPO2-01",
        title="Accurate SpO2 measurement in low perfusion",
        input_type="user_need",
        priority="critical",
        status="approved",
    )

    # 3. Functional Requirement deriving from User Need
    func_req = _designcontrols_create_input(
        tenant_a,
        project,
        admin_user,
        identifier="REQ-OPT-01",
        title="Dual wavelength optical sensor (660nm & 940nm)",
        input_type="functional",
        priority="critical",
        status="approved",
        user_need_parent=user_need,
    )
    assert func_req.is_verified is False
    assert user_need.derived_inputs.count() == 1

    # 4. Verification Test
    verification = _designcontrols_create_verification(
        tenant_a,
        project,
        func_req,
        title="Optical Spectrum Spectrophotometer Protocol",
        activity_type="verification",
        test_method="lab_test",
        sample_size=10,
        acceptance_criteria="Emitted wavelengths within +/- 2nm of nominal 660nm and 940nm.",
        pass_fail_result="pass",
        status="passed",
        results_summary="All 10 LED modules conformed to optical bandwidth tolerances.",
    )
    assert verification.is_passed is True

    # 5. Requirement is now verified via verification link
    assert func_req.is_verified is True

    # 6. Gate Review
    review = _designcontrols_create_review(
        tenant_a,
        project,
        admin_user,
        _designcontrols_independent_user,
        title="Design Verification Gate Review",
        review_stage="verification_gate",
        status="approved",
        action_items="Verify vendor LED calibration certificates.",
        action_items_resolved=False,
    )
    # Action item pending -> not cleared yet
    assert review.is_cleared is False

    # Resolve action item
    review.action_items_resolved = True
    review.save()
    assert review.is_cleared is True

    # 7. Design Transfer & DHF Lock
    project.current_phase = "commercial_closure"
    project.status = "completed"
    project.dhf_locked = True
    project.actual_completion_date = timezone.now().date()
    project.save()

    assert project.is_locked is True
    assert project.inputs.count() == 2
    assert project.reviews.count() == 1
    assert project.verifications.count() == 1
