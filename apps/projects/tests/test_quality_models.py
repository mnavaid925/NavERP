"""Projects 7.6 Quality Management — MODEL tests.

The model lane owns the claims the four quality tables would be worthless without:

* **``TenantNumbered``** mints ``QPL-/QRV-/QCI-/QDF-`` once, per tenant, per MODEL — the same
  per-workspace independence the 7.1 lane proved for ``PRQ-`` and the shape the test contract's
  reminders pin (assert prefix + ``\\d{5}`` shape, never a hardcoded number).
* **The state machines are DERIVED, never stored.** Every board figure the two computed pages
  read — ``is_review_overdue``, ``is_locked``, ``is_improvement_overdue``, ``is_overdue``,
  ``age_days``, ``is_open``, ``defect_count``, ``is_acceptance`` — is a Python property over the
  status/date columns, on the ``timezone.localdate()`` clock (L16), so it cannot go stale the
  instant a row is edited.
* **The lock predicates gate edit/delete.** Plan superseded/closed · review closed/cancelled ·
  inspection passed/failed/cancelled **or** a usage decision already taken (both arms) · defect
  resolved/closed/**cancelled** (the M1 amendment).
* **``clean()`` is the same-project guard layer**: wbs_node / source_risk / quality_plan /
  milestone / inspection mismatches are refused at the model with field-keyed
  ``ValidationError``s, not just by the scoped dropdowns. The malformed row is built with the
  model directly — the factories deliberately raise on it instead of seeding bad data.
* **Choices and defaults are the contract's vocabulary**: every ``*_CHOICES`` constant is
  asserted as a full ordered list of machine values, and every status/enum default is read off a
  raw (unsaved) instance so a form regression can never mask a model default.

Contract: ``.claude/tasks/contract-projects-7.6.md`` §2 (models) as amended by the close-out;
factories per ``.claude/tasks/test-contract-projects-7.6.md`` §1.

**Factory composition, not fixture rows.** This module builds every lifecycle row through the
committed ``_quality_*`` FACTORIES (plus the 7.2 ``_planning_milestone`` and 7.5 ``_risk``
factories where a guard row needs one) — the sanctioned fallback for a fixture a module cannot
use. As committed, ``quality_project_a``/``quality_project_b`` (and every fixture chaining from
them) raise ``TypeError: ... got multiple values for keyword argument 'name'`` because
``_quality_project`` forwards ``name``/``code`` both explicitly and via ``**overrides``; that
belongs to the conftest owner to fix, so this lane routes around it and calls the factories
without colliding overrides. ``_quality_project(tenant)`` with NO overrides builds the host.

Determinism (L16): every date basis is ``_quality_today()`` (``timezone.localdate()``) — the
overdue/age offsets are what make the ``is_*`` booleans and ``age_days`` exact while the test
runs within one local day.

Naming (mandatory): every test is ``test_quality_*``, every module-level helper ``_quality_*`` —
the ``projectinitiation_``/``planning_``/``resource_``/``cost_``/``risk_`` namespaces stay
untouched. Flat functions, house style — no Test* classes.

Scope: models only. Forms, views/urls and permissions belong to the other three lanes. The shared
``TenantNumbered`` base beyond prefix minting is 7.1's to prove.
"""
import re
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.projects.models import (
    DeliverableInspection,
    QualityDefect,
    QualityPlan,
    QualityReview,
)
from apps.projects.tests.conftest import (
    _planning_milestone,
    _quality_defect,
    _quality_inspection,
    _quality_plan,
    _quality_project,
    _quality_review,
    _quality_today,
    _quality_wbs_node,
    _risk,
)


def _quality_host(tenant):
    """A throwaway ACTIVE host project built through the committed 7.6 factory.

    Called with NO ``name``/``code`` overrides on purpose — those collide with the factory's own
    kwargs today (see the module docstring); a test that wants an isolated register builds its
    host here, exactly the per-test isolation the computed boards' lens assumes.
    """
    return _quality_project(tenant)


# ==============================================================================================
# Numbering — TenantNumbered across the four quality models
# ==============================================================================================

def test_quality_each_model_mints_its_own_prefix(tenant_a):
    host = _quality_host(tenant_a)
    plan = _quality_plan(tenant_a, host)
    review = _quality_review(tenant_a, host)
    inspection = _quality_inspection(tenant_a, host)
    defect = _quality_defect(tenant_a, host)
    assert re.fullmatch(r"QPL-\d{5}", plan.number)
    assert re.fullmatch(r"QRV-\d{5}", review.number)
    assert re.fullmatch(r"QCI-\d{5}", inspection.number)
    assert re.fullmatch(r"QDF-\d{5}", defect.number)


def test_quality_numbers_advance_per_tenant(tenant_a):
    """Two rows of one model in ONE tenant get different, consecutive numbers — the per-tenant
    sequence behind ``unique_together = ("tenant", "number")``."""
    host = _quality_host(tenant_a)
    for build in (_quality_plan, _quality_review, _quality_inspection, _quality_defect):
        first = build(tenant_a, host)
        second = build(tenant_a, host)
        assert second.number != first.number
        assert int(second.number.split("-")[1]) == int(first.number.split("-")[1]) + 1


def test_quality_numbers_independent_across_tenants(tenant_a, tenant_b):
    a = _quality_plan(tenant_a, _quality_host(tenant_a))
    b = _quality_plan(tenant_b, _quality_host(tenant_b))
    assert a.number == b.number  # same prefix+sequence, different workspaces
    assert a.tenant_id != b.tenant_id


def test_quality_plan_tenant_number_unique_together(tenant_a):
    host = _quality_host(tenant_a)
    plan = _quality_plan(tenant_a, host)
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            twin = _quality_plan(tenant_a, host)
            twin.number = plan.number
            twin.save()


# ==============================================================================================
# Choices — every CHOICES constant matches the contract's exact machine values
# ==============================================================================================

def test_quality_plan_choices_exact():
    assert [c[0] for c in QualityPlan.VERIFICATION_METHOD_CHOICES] == [
        "inspection", "testing", "demonstration", "review", "analysis", "audit"]
    assert [c[0] for c in QualityPlan.STATUS_CHOICES] == [
        "draft", "active", "superseded", "closed"]


def test_quality_review_choices_exact():
    assert [c[0] for c in QualityReview.REVIEW_TYPE_CHOICES] == [
        "methodology_review", "compliance_check", "gate_review", "kaizen_event", "retrospective",
        "maturity_assessment"]
    assert [c[0] for c in QualityReview.STATUS_CHOICES] == [
        "planned", "in_progress", "reported", "closed", "cancelled"]
    assert [c[0] for c in QualityReview.IMPROVEMENT_STATUS_CHOICES] == [
        "n_a", "planned", "in_progress", "done"]


def test_quality_inspection_choices_exact():
    assert [c[0] for c in DeliverableInspection.INSPECTION_TYPE_CHOICES] == [
        "review", "testing", "demonstration", "walkthrough", "acceptance"]
    assert [c[0] for c in DeliverableInspection.RESULT_CHOICES] == [
        "pending", "pass", "fail", "conditional", "not_applicable"]
    assert [c[0] for c in DeliverableInspection.USAGE_DECISION_CHOICES] == [
        "pending", "accept", "accept_with_deviation", "reject", "rework"]
    assert [c[0] for c in DeliverableInspection.STATUS_CHOICES] == [
        "planned", "in_progress", "passed", "failed", "on_hold", "cancelled"]


def test_quality_defect_choices_exact():
    assert [c[0] for c in QualityDefect.DEFECT_CATEGORY_CHOICES] == [
        "functional", "performance", "documentation", "compliance", "dimensional", "workmanship",
        "usability", "other"]
    assert [c[0] for c in QualityDefect.SEVERITY_CHOICES] == [
        "critical", "major", "minor", "observation"]
    assert [c[0] for c in QualityDefect.DISPOSITION_CHOICES] == [
        "open", "rework", "repair", "resubmit", "accept_as_is", "reject", "deferred"]
    assert [c[0] for c in QualityDefect.STATUS_CHOICES] == [
        "open", "in_progress", "resolved", "closed", "cancelled"]


# ==============================================================================================
# Defaults — model-level, read off a raw instance so no form can mask them
# ==============================================================================================

def test_quality_plan_defaults(tenant_a):
    host = _quality_host(tenant_a)
    raw = QualityPlan(tenant=tenant_a, project=host, title="Defaults",
                      acceptance_criteria="The deliverable passes its inspection.")
    assert raw.status == "draft"
    assert raw.verification_method == "inspection"
    assert _quality_plan(tenant_a, host).status == "draft"


def test_quality_review_defaults(tenant_a):
    host = _quality_host(tenant_a)
    raw = QualityReview(tenant=tenant_a, project=host, title="Defaults")
    assert raw.status == "planned"
    assert raw.review_type == "methodology_review"
    assert raw.improvement_status == "n_a"
    assert raw.maturity_score is None
    assert raw.review_date == _quality_today()  # default callable, same clock as the lenses
    assert _quality_review(tenant_a, host).status == "planned"


def test_quality_inspection_defaults(tenant_a):
    host = _quality_host(tenant_a)
    raw = DeliverableInspection(tenant=tenant_a, project=host, title="Defaults")
    assert raw.status == "planned"
    assert raw.inspection_type == "review"  # NOT acceptance — never in the queue by default
    assert raw.result == "pending"
    assert raw.usage_decision == "pending"
    assert _quality_inspection(tenant_a, host).status == "planned"


def test_quality_defect_defaults(tenant_a):
    host = _quality_host(tenant_a)
    raw = QualityDefect(tenant=tenant_a, project=host, title="Defaults",
                        description="The output does not meet the acceptance criterion.")
    assert raw.status == "open"
    assert raw.defect_category == "other"
    assert raw.severity == "minor"
    assert raw.disposition == "open"
    assert raw.identified_date == _quality_today()  # default callable
    assert _quality_defect(tenant_a, host).status == "open"


# ==============================================================================================
# QualityPlan — derived figures (never stored)
# ==============================================================================================

def test_quality_plan_review_overdue_true_cases(tenant_a):
    """A past review date on a still-draft plan — the ``?review_due=1`` lens row's shape."""
    host = _quality_host(tenant_a)
    plan = _quality_plan(tenant_a, host,
                         planned_review_date=_quality_today() - timedelta(days=3))
    assert plan.is_review_overdue is True


def test_quality_plan_review_overdue_false_cases(tenant_a):
    host = _quality_host(tenant_a)
    today = _quality_today()
    assert _quality_plan(tenant_a, host).is_review_overdue is False  # no date set
    future = _quality_plan(tenant_a, host, planned_review_date=today + timedelta(days=7))
    assert future.is_review_overdue is False
    due_today = _quality_plan(tenant_a, host, planned_review_date=today)
    assert due_today.is_review_overdue is False  # strictly < today


def test_quality_plan_review_overdue_gated_by_status(tenant_a):
    """Only a LIVE plan (draft/active) can be review-overdue; the locked statuses suppress it."""
    host = _quality_host(tenant_a)
    past = _quality_today() - timedelta(days=3)
    active = _quality_plan(tenant_a, host, planned_review_date=past, status="active")
    assert active.is_review_overdue is True
    superseded = _quality_plan(tenant_a, host, planned_review_date=past, status="superseded")
    assert superseded.is_review_overdue is False
    closed = _quality_plan(tenant_a, host, planned_review_date=past, status="closed")
    assert closed.is_review_overdue is False


def test_quality_plan_is_locked_statuses(tenant_a):
    host = _quality_host(tenant_a)
    assert _quality_plan(tenant_a, host).is_locked is False  # draft is editable
    assert _quality_plan(tenant_a, host, status="active").is_locked is False
    assert _quality_plan(tenant_a, host, status="superseded").is_locked is True
    assert _quality_plan(tenant_a, host, status="closed").is_locked is True


# ==============================================================================================
# QualityReview — derived figures (never stored)
# ==============================================================================================

def test_quality_review_improvement_overdue_true_cases(tenant_a):
    """Due date passed while the action is still open — ``planned`` and ``in_progress`` both."""
    host = _quality_host(tenant_a)
    past = _quality_today() - timedelta(days=3)
    in_progress = _quality_review(tenant_a, host, improvement_status="in_progress",
                                  improvement_due_date=past)
    assert in_progress.is_improvement_overdue is True
    planned = _quality_review(tenant_a, host, improvement_status="planned",
                              improvement_due_date=past)
    assert planned.is_improvement_overdue is True


def test_quality_review_improvement_overdue_false_cases(tenant_a):
    host = _quality_host(tenant_a)
    today = _quality_today()
    assert _quality_review(tenant_a, host).is_improvement_overdue is False  # no due date
    done = _quality_review(tenant_a, host, improvement_status="done",
                           improvement_due_date=today - timedelta(days=7))
    assert done.is_improvement_overdue is False  # finished — out of the overdue lens
    future = _quality_review(tenant_a, host, improvement_status="planned",
                             improvement_due_date=today + timedelta(days=7))
    assert future.is_improvement_overdue is False
    due_today = _quality_review(tenant_a, host, improvement_status="planned",
                                improvement_due_date=today)
    assert due_today.is_improvement_overdue is False  # strictly < today


def test_quality_review_is_locked_statuses(tenant_a):
    host = _quality_host(tenant_a)
    assert _quality_review(tenant_a, host).is_locked is False  # planned
    assert _quality_review(tenant_a, host, status="in_progress").is_locked is False
    assert _quality_review(tenant_a, host, status="reported").is_locked is False
    assert _quality_review(tenant_a, host, status="closed").is_locked is True
    assert _quality_review(tenant_a, host, status="cancelled").is_locked is True


# ==============================================================================================
# DeliverableInspection — derived figures (never stored)
# ==============================================================================================

def test_quality_inspection_overdue_true_cases(tenant_a):
    """Planned date passed while never executed and still executable — the ``?overdue=1`` shape."""
    host = _quality_host(tenant_a)
    past = _quality_today() - timedelta(days=3)
    planned = _quality_inspection(tenant_a, host, planned_date=past)
    assert planned.is_overdue is True
    in_progress = _quality_inspection(tenant_a, host, status="in_progress", planned_date=past)
    assert in_progress.is_overdue is True  # in_progress is still executable


def test_quality_inspection_overdue_false_cases(tenant_a):
    host = _quality_host(tenant_a)
    today = _quality_today()
    assert _quality_inspection(tenant_a, host).is_overdue is False  # no planned date
    future = _quality_inspection(tenant_a, host, planned_date=today + timedelta(days=7))
    assert future.is_overdue is False
    executed = _quality_inspection(tenant_a, host, planned_date=today - timedelta(days=1),
                                   inspected_date=today - timedelta(days=1),
                                   result="pass", status="in_progress")
    assert executed.is_overdue is False  # already executed
    on_hold = _quality_inspection(tenant_a, host, status="on_hold",
                                  planned_date=today - timedelta(days=3))
    assert on_hold.is_overdue is False  # on_hold is outside the executable statuses


def test_quality_inspection_locked_terminal_statuses(tenant_a):
    """Arm 1: the terminal statuses freeze the row; the live ones (pending decision) do not."""
    host = _quality_host(tenant_a)
    assert _quality_inspection(tenant_a, host).is_locked is False  # planned
    assert _quality_inspection(tenant_a, host, status="in_progress").is_locked is False
    assert _quality_inspection(tenant_a, host, status="on_hold").is_locked is False
    assert _quality_inspection(tenant_a, host, status="passed").is_locked is True
    assert _quality_inspection(tenant_a, host, status="failed").is_locked is True
    assert _quality_inspection(tenant_a, host, status="cancelled").is_locked is True


def test_quality_inspection_locked_by_usage_decision(tenant_a):
    """Arm 2: a decision already taken freezes the row even at a non-terminal status."""
    host = _quality_host(tenant_a)
    deviated = _quality_inspection(tenant_a, host, status="in_progress", result="conditional",
                                   usage_decision="accept_with_deviation")
    assert deviated.is_locked is True
    rework = _quality_inspection(tenant_a, host, usage_decision="rework")
    assert rework.is_locked is True


def test_quality_inspection_defect_count(tenant_a):
    """A live read of the child punch-list table, never a stored count."""
    host = _quality_host(tenant_a)
    inspection = _quality_inspection(tenant_a, host)
    assert inspection.defect_count == 0
    _quality_defect(tenant_a, host, inspection=inspection, title="Punch one")
    _quality_defect(tenant_a, host, inspection=inspection, title="Punch two")
    other = _quality_inspection(tenant_a, host)
    _quality_defect(tenant_a, host, inspection=other, title="Not this one")
    assert inspection.defect_count == 2


def test_quality_inspection_is_acceptance(tenant_a):
    """The acceptance page lenses on ``inspection_type="acceptance"`` — nothing else."""
    host = _quality_host(tenant_a)
    acceptance = _quality_inspection(tenant_a, host, inspection_type="acceptance",
                                     inspected_date=_quality_today() - timedelta(days=1),
                                     result="pass", status="in_progress")
    assert acceptance.is_acceptance is True
    assert _quality_inspection(tenant_a, host).is_acceptance is False


# ==============================================================================================
# QualityDefect — derived figures (never stored)
# ==============================================================================================

def test_quality_defect_overdue_true_cases(tenant_a):
    host = _quality_host(tenant_a)
    past = _quality_today() - timedelta(days=2)
    assert _quality_defect(tenant_a, host, due_date=past).is_overdue is True
    in_progress = _quality_defect(tenant_a, host, status="in_progress", due_date=past)
    assert in_progress.is_overdue is True  # in_progress is the other live status


def test_quality_defect_overdue_false_cases(tenant_a):
    host = _quality_host(tenant_a)
    today = _quality_today()
    assert _quality_defect(tenant_a, host).is_overdue is False  # no due date
    future = _quality_defect(tenant_a, host, due_date=today + timedelta(days=5))
    assert future.is_overdue is False
    resolved = _quality_defect(tenant_a, host, status="resolved",
                               due_date=today - timedelta(days=2))
    assert resolved.is_overdue is False  # a dispositioned defect is not overdue


def test_quality_defect_age_days(tenant_a):
    host = _quality_host(tenant_a)
    two = _quality_defect(tenant_a, host,
                          identified_date=_quality_today() - timedelta(days=2))
    assert two.age_days == 2
    twenty = _quality_defect(tenant_a, host,
                             identified_date=_quality_today() - timedelta(days=20))
    assert twenty.age_days == 20
    assert _quality_defect(tenant_a, host).age_days == 0  # identified today


def test_quality_defect_is_open_statuses(tenant_a):
    host = _quality_host(tenant_a)
    assert _quality_defect(tenant_a, host).is_open is True  # open
    assert _quality_defect(tenant_a, host, status="in_progress").is_open is True
    assert _quality_defect(tenant_a, host, status="resolved").is_open is False
    assert _quality_defect(tenant_a, host, status="closed").is_open is False
    assert _quality_defect(tenant_a, host, status="cancelled").is_open is False


def test_quality_defect_is_locked_statuses(tenant_a):
    host = _quality_host(tenant_a)
    assert _quality_defect(tenant_a, host).is_locked is False  # open
    assert _quality_defect(tenant_a, host, status="in_progress").is_locked is False
    assert _quality_defect(tenant_a, host, status="resolved").is_locked is True
    assert _quality_defect(tenant_a, host, status="closed").is_locked is True
    assert _quality_defect(tenant_a, host, status="cancelled").is_locked is True  # M1 amendment


# ==============================================================================================
# clean() — the same-project guard layer; the foreign rows hang off a SECOND project built via
# ``_quality_project`` in the same tenant, so the guard is project-scoped, not tenant-scoped
# ==============================================================================================

def test_quality_plan_clean_rejects_foreign_project_wbs_node(tenant_a):
    host = _quality_host(tenant_a)
    foreign = _quality_wbs_node(tenant_a, _quality_host(tenant_a))
    plan = QualityPlan(tenant=tenant_a, project=host, title="Cross",
                       acceptance_criteria="criteria", wbs_node=foreign)
    with pytest.raises(ValidationError) as ei:
        plan.clean()
    assert "wbs_node" in ei.value.message_dict


def test_quality_plan_clean_rejects_foreign_project_source_risk(tenant_a):
    host = _quality_host(tenant_a)
    foreign_risk = _risk(tenant_a, _quality_host(tenant_a))
    plan = QualityPlan(tenant=tenant_a, project=host, title="Cross",
                       acceptance_criteria="criteria", source_risk=foreign_risk)
    with pytest.raises(ValidationError) as ei:
        plan.clean()
    assert "source_risk" in ei.value.message_dict


def test_quality_plan_clean_allows_same_project_anchors(tenant_a):
    host = _quality_host(tenant_a)
    node = _quality_wbs_node(tenant_a, host)
    plan = _quality_plan(tenant_a, host, wbs_node=node, source_risk=_risk(tenant_a, host))
    assert plan.wbs_node.project_id == plan.project_id  # built through clean() — no raise


def test_quality_review_clean_rejects_foreign_project_wbs_node(tenant_a):
    host = _quality_host(tenant_a)
    foreign = _quality_wbs_node(tenant_a, _quality_host(tenant_a))
    review = QualityReview(tenant=tenant_a, project=host, title="Cross", wbs_node=foreign)
    with pytest.raises(ValidationError) as ei:
        review.clean()
    assert "wbs_node" in ei.value.message_dict


def test_quality_review_clean_rejects_foreign_project_quality_plan(tenant_a):
    host = _quality_host(tenant_a)
    foreign_plan = _quality_plan(tenant_a, _quality_host(tenant_a))
    review = QualityReview(tenant=tenant_a, project=host, title="Cross",
                           quality_plan=foreign_plan)
    with pytest.raises(ValidationError) as ei:
        review.clean()
    assert "quality_plan" in ei.value.message_dict


def test_quality_review_clean_allows_same_project_anchors(tenant_a):
    host = _quality_host(tenant_a)
    plan = _quality_plan(tenant_a, host)
    review = _quality_review(tenant_a, host, wbs_node=_quality_wbs_node(tenant_a, host),
                             quality_plan=plan)
    assert review.quality_plan_id == plan.pk  # built through clean() — no raise


def test_quality_inspection_clean_rejects_foreign_project_wbs_node(tenant_a):
    host = _quality_host(tenant_a)
    foreign = _quality_wbs_node(tenant_a, _quality_host(tenant_a))
    inspection = DeliverableInspection(tenant=tenant_a, project=host, title="Cross",
                                       wbs_node=foreign)
    with pytest.raises(ValidationError) as ei:
        inspection.clean()
    assert "wbs_node" in ei.value.message_dict


def test_quality_inspection_clean_rejects_foreign_project_quality_plan(tenant_a):
    host = _quality_host(tenant_a)
    foreign_plan = _quality_plan(tenant_a, _quality_host(tenant_a))
    inspection = DeliverableInspection(tenant=tenant_a, project=host, title="Cross",
                                       quality_plan=foreign_plan)
    with pytest.raises(ValidationError) as ei:
        inspection.clean()
    assert "quality_plan" in ei.value.message_dict


def test_quality_inspection_clean_rejects_foreign_project_milestone(tenant_a):
    host = _quality_host(tenant_a)
    foreign_milestone = _planning_milestone(tenant_a, _quality_host(tenant_a))
    inspection = DeliverableInspection(tenant=tenant_a, project=host, title="Cross",
                                       milestone=foreign_milestone)
    with pytest.raises(ValidationError) as ei:
        inspection.clean()
    assert "milestone" in ei.value.message_dict


def test_quality_inspection_clean_allows_same_project_anchors(tenant_a):
    host = _quality_host(tenant_a)
    plan = _quality_plan(tenant_a, host)
    inspection = _quality_inspection(tenant_a, host,
                                     wbs_node=_quality_wbs_node(tenant_a, host),
                                     quality_plan=plan,
                                     milestone=_planning_milestone(tenant_a, host))
    assert inspection.milestone.project_id == inspection.project_id  # clean() passed


def test_quality_defect_clean_rejects_foreign_project_wbs_node(tenant_a):
    host = _quality_host(tenant_a)
    foreign = _quality_wbs_node(tenant_a, _quality_host(tenant_a))
    defect = QualityDefect(tenant=tenant_a, project=host, title="Cross",
                           description="Does not meet the criterion.", wbs_node=foreign)
    with pytest.raises(ValidationError) as ei:
        defect.clean()
    assert "wbs_node" in ei.value.message_dict


def test_quality_defect_clean_rejects_foreign_project_quality_plan(tenant_a):
    host = _quality_host(tenant_a)
    foreign_plan = _quality_plan(tenant_a, _quality_host(tenant_a))
    defect = QualityDefect(tenant=tenant_a, project=host, title="Cross",
                           description="Does not meet the criterion.", quality_plan=foreign_plan)
    with pytest.raises(ValidationError) as ei:
        defect.clean()
    assert "quality_plan" in ei.value.message_dict


def test_quality_defect_clean_rejects_foreign_project_inspection(tenant_a):
    host = _quality_host(tenant_a)
    foreign_inspection = _quality_inspection(tenant_a, _quality_host(tenant_a))
    defect = QualityDefect(tenant=tenant_a, project=host, title="Cross",
                           description="Does not meet the criterion.",
                           inspection=foreign_inspection)
    with pytest.raises(ValidationError) as ei:
        defect.clean()
    assert "inspection" in ei.value.message_dict


def test_quality_defect_clean_allows_same_project_anchors(tenant_a):
    host = _quality_host(tenant_a)
    plan = _quality_plan(tenant_a, host)
    inspection = _quality_inspection(tenant_a, host)
    defect = _quality_defect(tenant_a, host, wbs_node=_quality_wbs_node(tenant_a, host),
                             quality_plan=plan, inspection=inspection)
    assert defect.inspection_id == inspection.pk  # built through clean() — no raise


# ==============================================================================================
# Meta — ordering (first row returned is newest) + the named indexes
# ==============================================================================================

def test_quality_plan_ordering_newest_first(tenant_a):
    host = _quality_host(tenant_a)
    _quality_plan(tenant_a, host, title="First plan")
    newest = _quality_plan(tenant_a, host, title="Second plan")
    assert QualityPlan.objects.filter(tenant=tenant_a).first() == newest


def test_quality_plan_meta_indexes():
    assert {i.name for i in QualityPlan._meta.indexes} == {
        "qpl_tnt_project_idx", "qpl_tnt_status_idx", "qpl_tnt_wbs_idx", "qpl_tnt_created_idx"}
    assert ("tenant", "number") in QualityPlan._meta.unique_together


def test_quality_review_ordering_by_review_date_newest_first(tenant_a):
    host = _quality_host(tenant_a)
    newest = _quality_review(tenant_a, host)  # review_date today, minted FIRST
    older = _quality_review(tenant_a, host,
                            review_date=_quality_today() - timedelta(days=5))
    rows = list(QualityReview.objects.filter(tenant=tenant_a)[:2])
    assert rows[0] == newest and rows[1] == older  # -review_date leads; -id only breaks ties


def test_quality_review_meta_indexes():
    assert {i.name for i in QualityReview._meta.indexes} == {
        "qrv_tnt_project_idx", "qrv_tnt_type_idx", "qrv_tnt_status_idx", "qrv_tnt_imp_idx",
        "qrv_tnt_date_idx"}
    assert ("tenant", "number") in QualityReview._meta.unique_together


def test_quality_inspection_ordering_newest_first(tenant_a):
    host = _quality_host(tenant_a)
    _quality_inspection(tenant_a, host)
    newest = _quality_inspection(tenant_a, host)
    assert DeliverableInspection.objects.filter(tenant=tenant_a).first() == newest


def test_quality_inspection_meta_indexes():
    assert {i.name for i in DeliverableInspection._meta.indexes} == {
        "qci_tnt_project_idx", "qci_tnt_status_idx", "qci_tnt_result_idx",
        "qci_tnt_decision_idx", "qci_tnt_wbs_idx"}
    assert ("tenant", "number") in DeliverableInspection._meta.unique_together


def test_quality_defect_ordering_newest_first(tenant_a):
    host = _quality_host(tenant_a)
    _quality_defect(tenant_a, host)
    newest = _quality_defect(tenant_a, host)
    assert QualityDefect.objects.filter(tenant=tenant_a).first() == newest


def test_quality_defect_meta_indexes():
    assert {i.name for i in QualityDefect._meta.indexes} == {
        "qdf_tnt_project_idx", "qdf_tnt_status_idx", "qdf_tnt_severity_idx",
        "qdf_tnt_disp_idx", "qdf_tnt_created_idx"}
    assert ("tenant", "number") in QualityDefect._meta.unique_together


# ==============================================================================================
# __str__ — the register/detail headers read off this
# ==============================================================================================

def test_quality_str_formats_number_and_title(tenant_a):
    host = _quality_host(tenant_a)
    plan = _quality_plan(tenant_a, host, title="Plan title")
    review = _quality_review(tenant_a, host, title="Review title")
    inspection = _quality_inspection(tenant_a, host, title="Inspection title")
    defect = _quality_defect(tenant_a, host, title="Defect title")
    assert str(plan) == f"{plan.number} — Plan title"
    assert str(review) == f"{review.number} — Review title"
    assert str(inspection) == f"{inspection.number} — Inspection title"
    assert str(defect) == f"{defect.number} — Defect title"
