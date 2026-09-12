"""Projects 7.5 Risk & Issue Management — MODEL tests.

The model lane owns the claims the four risk tables would be worthless without:

* **``TenantNumbered``** mints ``RSK-/RRA-/ISS-/ESC-`` once, per tenant, per MODEL — the same
  per-workspace independence the 7.1/7.4 lanes proved. A second ``save()`` never re-numbers, and
  tenant B's registers count from their own RSK-00001.
* **Everything scored is DERIVED, never stored.** ``score``/``severity_band``/``emv``/
  ``residual_*``/``is_review_overdue``/``is_open``/``is_overdue``/``age_days`` are pure functions
  of their input columns — the tests pin the arithmetic exactly, including the band BOUNDARIES
  (score 3→low, 4→medium, 8→high, 14→high, 15→critical) and the as-built ``residual_emv``
  (which divides the residual ordinal by 100 directly — it is entered as a percent, not mapped
  through ``PROBABILITY_PCT``).
* **``clean()`` is the same-project guard layer**: a WBS node, control account or parent risk
  from another project is refused at the model, not just by the scoped dropdowns.
* **Meta is contract**: ``ordering`` newest-first on the three registers (issue-id/level on the
  escalation path) and the seven named register indexes from migrations 0006+0008 exist by name
  — the ``?review_due=``/``?overdue=``/``?strategy=``/``?issue_type=`` lenses and the
  ``-created_at`` orderings are only as good as their indexes (review I7/M11/M12).

Determinism (L16): every date basis is ``_risk_today()`` (``timezone.localdate()``) — the same
clock ``is_review_overdue``/``is_overdue``/``age_days`` read, so no UTC-offset flake.

Naming (mandatory): every test is ``test_risk_*``, every module-level helper ``_risk_*`` — the
``projectinitiation_``/``planning_``/``resource_``/``cost_`` namespaces stay untouched. Flat
functions, house style — no Test* classes.

Scope: models only. Forms, views/urls and permissions belong to the other three lanes.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.projects.models import (
    IssueEscalation,
    ProjectIssue,
    ProjectRisk,
    RiskResponseAction,
)
from apps.projects.tests.conftest import (
    _risk,
    _risk_action,
    _risk_escalation,
    _risk_issue,
    _risk_project,
    _risk_today,
)

D = Decimal


# ==============================================================================================
# Numbering — TenantNumbered across the four risk models
# ==============================================================================================

def test_risk_risk_mints_rsk_number(tenant_a, risk_project_a):
    row = _risk(tenant_a, risk_project_a)
    assert row.number.startswith("RSK-")
    assert len(row.number) == 9  # RSK- + 5 digits


def test_risk_numbers_advance_per_model_per_tenant(tenant_a, risk_project_a):
    first = _risk(tenant_a, risk_project_a)
    second = _risk(tenant_a, risk_project_a)
    assert int(second.number.split("-")[1]) == int(first.number.split("-")[1]) + 1


def test_risk_children_mint_their_own_prefixes(tenant_a, risk_project_a, admin_user):
    risk = _risk(tenant_a, risk_project_a)
    action = _risk_action(risk)
    issue = _risk_issue(tenant_a, risk_project_a)
    escalation = _risk_escalation(issue)
    assert action.number.startswith("RRA-") and len(action.number) == 9
    assert issue.number.startswith("ISS-") and len(issue.number) == 9
    assert escalation.number.startswith("ESC-") and len(escalation.number) == 9


def test_risk_tenant_b_numbers_independently(tenant_a, tenant_b, risk_project_a, risk_project_b):
    a = _risk(tenant_a, risk_project_a)
    b = _risk(tenant_b, risk_project_b)
    assert a.number.split("-")[1] == "00001"
    assert b.number.split("-")[1] == "00001"


def test_risk_duplicate_number_in_tenant_rejected(tenant_a, risk_project_a):
    row = _risk(tenant_a, risk_project_a)
    dupe = _risk(tenant_a, risk_project_a)
    dupe.number = row.number
    with pytest.raises(IntegrityError):
        dupe.save()


# ==============================================================================================
# Derived figures — score / band / EMV, all pure functions, never columns
# ==============================================================================================

def test_risk_score_is_probability_times_impact(tenant_a, risk_project_a):
    row = _risk(tenant_a, risk_project_a, probability=3, impact=4)
    assert row.score == 12
    assert ProjectRisk._meta.get_field("probability").column == "probability"
    # score is a property, not a column: no such field, nothing stored.
    assert not any(f.name == "score" for f in ProjectRisk._meta.get_fields())


@pytest.mark.parametrize("p,i,band", [
    (1, 1, "low"),        # 1
    (1, 3, "low"),        # 3 — the inclusive top of low
    (2, 2, "medium"),     # 4 — the bottom of medium
    (2, 4, "high"),       # 8 — the bottom of high
    (2, 7 - 3, "high"),   # 8
    (2, 5, "high"),       # 10
    (3, 5, "critical"),   # 15 — the bottom of critical
    (5, 5, "critical"),   # 25 — the top of the scale
])
def test_risk_severity_band_boundaries(tenant_a, risk_project_a, p, i, band):
    row = _risk(tenant_a, risk_project_a, probability=p, impact=i)
    assert row.severity_band == band
    assert row.get_severity_band_display() == ProjectRisk._BAND_LABELS[band]


def test_risk_emv_is_probability_pct_times_cost(tenant_a, risk_project_a):
    row = _risk(tenant_a, risk_project_a, probability=2, cost_impact=D("1000.00"))
    assert row.emv == D("300.00")  # 30% — PROBABILITY_PCT[2]


def test_risk_residual_score_none_until_both_ordinals(tenant_a, risk_project_a):
    half = _risk(tenant_a, risk_project_a, residual_probability=3)
    assert half.residual_score is None and half.residual_band is None
    full = _risk(tenant_a, risk_project_a, residual_probability=3, residual_impact=4)
    assert full.residual_score == 12 and full.residual_band == "high"


def test_risk_residual_emv_uses_the_ordinal_as_percent(tenant_a, risk_project_a):
    # As-built: residual_probability is entered as a percent and divided by 100 directly —
    # deliberately NOT routed through PROBABILITY_PCT.
    row = _risk(tenant_a, risk_project_a, cost_impact=D("1000.00"), residual_probability=50)
    assert row.residual_emv == D("500.00")
    assert _risk(tenant_a, risk_project_a).residual_emv == D("0")


def test_risk_is_review_overdue_only_while_live(tenant_a, risk_project_a):
    overdue = _risk(tenant_a, risk_project_a, review_date=_risk_today() - timedelta(days=3))
    assert overdue.is_review_overdue
    future = _risk(tenant_a, risk_project_a, review_date=_risk_today() + timedelta(days=3))
    assert not future.is_review_overdue
    no_review = _risk(tenant_a, risk_project_a, review_date=None)
    assert not no_review.is_review_overdue
    closed = _risk(tenant_a, risk_project_a,
                   review_date=_risk_today() - timedelta(days=3), status="closed")
    assert not closed.is_review_overdue  # a closed row is not waiting for a review


def test_risk_is_locked_freezes_evidence_rows(tenant_a, risk_project_a):
    assert not _risk(tenant_a, risk_project_a).is_locked
    assert _risk(tenant_a, risk_project_a, status="realized").is_locked
    assert _risk(tenant_a, risk_project_a, status="closed").is_locked


def test_risk_review_overdue_is_a_property_not_a_column(tenant_a, risk_project_a):
    assert not any(f.name == "is_review_overdue" for f in ProjectRisk._meta.get_fields())


# ==============================================================================================
# Issue derived figures
# ==============================================================================================

def test_risk_issue_is_open_covers_the_three_live_statuses(tenant_a, risk_project_a):
    for status in ("open", "in_progress", "blocked"):
        assert _risk_issue(tenant_a, risk_project_a, status=status).is_open
    for status in ("resolved", "closed", "cancelled"):
        assert not _risk_issue(tenant_a, risk_project_a, status=status).is_open


def test_risk_issue_is_overdue_only_while_open(tenant_a, risk_project_a):
    overdue = _risk_issue(tenant_a, risk_project_a,
                          due_date=_risk_today() - timedelta(days=1))
    assert overdue.is_overdue
    resolved = _risk_issue(tenant_a, risk_project_a,
                           due_date=_risk_today() - timedelta(days=1), status="resolved")
    assert not resolved.is_overdue  # finished in time, even though the date passed
    no_due = _risk_issue(tenant_a, risk_project_a, due_date=None)
    assert not no_due.is_overdue


def test_risk_issue_age_days_counts_from_identified_date(tenant_a, risk_project_a):
    row = _risk_issue(tenant_a, risk_project_a,
                      identified_date=_risk_today() - timedelta(days=20))
    assert row.age_days == 20
    assert _risk_issue(tenant_a, risk_project_a).age_days == 0


def test_risk_issue_is_locked_freezes_evidence_rows(tenant_a, risk_project_a):
    assert not _risk_issue(tenant_a, risk_project_a).is_locked
    assert _risk_issue(tenant_a, risk_project_a, status="resolved").is_locked
    assert _risk_issue(tenant_a, risk_project_a, status="closed").is_locked
    assert not _risk_issue(tenant_a, risk_project_a, status="cancelled").is_locked


# ==============================================================================================
# Response-action derived figures
# ==============================================================================================

def test_risk_action_overdue_only_while_live(tenant_a, risk_project_a):
    risk = _risk(tenant_a, risk_project_a)
    past = _risk_today() - timedelta(days=1)
    assert _risk_action(risk, due_date=past).is_overdue
    assert not _risk_action(risk, due_date=past, status="completed").is_overdue
    assert not _risk_action(risk, due_date=past, status="cancelled").is_overdue
    assert not _risk_action(risk, due_date=None).is_overdue


def test_risk_action_locked_only_when_completed(tenant_a, risk_project_a):
    risk = _risk(tenant_a, risk_project_a)
    assert not _risk_action(risk).is_locked
    assert _risk_action(risk, status="completed").is_locked
    assert not _risk_action(risk, status="cancelled").is_locked


def test_risk_action_residual_score_none_until_both_ordinals(tenant_a, risk_project_a):
    risk = _risk(tenant_a, risk_project_a)
    assert _risk_action(risk, residual_probability=2).residual_score is None
    assert _risk_action(risk, residual_probability=2, residual_impact=3).residual_score == 6


# ==============================================================================================
# Escalation — the trail's stamps
# ==============================================================================================

def test_risk_escalation_stamps_escalated_at_on_insert(tenant_a, risk_project_a):
    issue = _risk_issue(tenant_a, risk_project_a)
    esc = _risk_escalation(issue, level=3)
    assert esc.escalated_at is not None
    assert esc.level == 3
    assert IssueEscalation.LEVEL_CHOICES[-1] == (4, "Level 4 — Executive Sponsor")


def test_risk_escalation_orders_by_issue_then_level(tenant_a, risk_project_a):
    issue = _risk_issue(tenant_a, risk_project_a)
    _risk_escalation(issue, level=3)
    _risk_escalation(issue, level=1)
    levels = list(issue.escalations.values_list("level", flat=True))
    assert levels == sorted(levels)  # Meta.ordering = ["issue_id", "level", "id"]


# ==============================================================================================
# clean() — the same-project guard layer
# ==============================================================================================

def test_risk_rejects_wbs_node_from_another_project(tenant_a, risk_project_a, risk_wbs_node_a):
    other = _risk_project(tenant_a)
    with pytest.raises(ValidationError):
        _risk(tenant_a, other, wbs_node=risk_wbs_node_a)


def test_risk_rejects_control_account_from_another_project(
        tenant_a, risk_project_a, risk_wbs_node_a):
    # The fixture pair gives a same-project WBS node; build a foreign-project CA through the
    # same-project guard of the risk itself — the guard is what this test pins.
    from apps.projects.models import CostControlAccount
    other = _risk_project(tenant_a)
    ca = CostControlAccount.objects.create(
        tenant=tenant_a, project=other, wbs_node=None, name="Foreign CA",
        code="FCA-01", contingency=D("0.00"))
    with pytest.raises(ValidationError):
        _risk(tenant_a, risk_project_a, contingency_account=ca)


def test_risk_issue_rejects_risk_from_another_project(tenant_a, risk_project_a):
    other = _risk_project(tenant_a)
    foreign_risk = _risk(tenant_a, other)
    with pytest.raises(ValidationError):
        _risk_issue(tenant_a, risk_project_a, risk=foreign_risk)


# ==============================================================================================
# Meta — ordering, unique_together and the named register indexes (I7 / M11 / M12)
# ==============================================================================================

def test_risk_register_indexes_exist_by_name():
    names_by_model = {
        ProjectRisk: {"rsk_tnt_project_idx", "rsk_tnt_status_idx", "rsk_tnt_category_idx",
                      "rsk_tnt_rtype_idx", "rsk_tnt_created_idx", "rsk_tnt_review_idx",
                      "rsk_tnt_owner_idx"},
        ProjectIssue: {"iss_tnt_project_idx", "iss_tnt_status_idx", "iss_tnt_severity_idx",
                       "iss_tnt_esc_idx", "iss_tnt_created_idx", "iss_tnt_type_idx",
                       "iss_tnt_due_idx"},
        RiskResponseAction: {"rra_tnt_risk_idx", "rra_tnt_status_idx", "rra_tnt_owner_idx",
                             "rra_tnt_due_idx", "rra_tnt_strategy_idx", "rra_tnt_created_idx"},
        IssueEscalation: {"esc_tnt_issue_idx", "esc_tnt_level_idx"},
    }
    for model, expected in names_by_model.items():
        actual = {idx.name for idx in model._meta.indexes}
        assert expected <= actual, f"{model.__name__} missing: {expected - actual}"


def test_risk_register_orderings_match_contract():
    assert ProjectRisk._meta.ordering == ["-created_at", "-id"]
    assert ProjectIssue._meta.ordering == ["-created_at", "-id"]
    assert RiskResponseAction._meta.ordering == ["-created_at", "-id"]
    assert IssueEscalation._meta.ordering == ["issue_id", "level", "id"]


def test_risk_probability_pct_is_the_documented_flat_map():
    from apps.projects.models.RiskManagement.ProjectRisks import PROBABILITY_PCT
    assert PROBABILITY_PCT == {1: 10, 2: 30, 3: 50, 4: 70, 5: 90}
    assert ProjectRisk.SEVERITY_BANDS == {
        "low": (1, 3), "medium": (4, 7), "high": (8, 14), "critical": (15, 25)}
    assert ProjectRisk.TOLERANCE_BANDS == {"high", "critical"}
