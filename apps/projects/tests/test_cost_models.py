"""Projects 7.4 Cost & Budget Management — MODEL tests.

The model lane owns the claims the four cost tables would be worthless without:

* **``TenantNumbered``** mints ``BVR-/CCA-/PBL-/PEX-`` once, per tenant, per MODEL — the same
  per-workspace independence the 7.1 lane proved for ``PRQ-``. A second ``save()`` never
  re-numbers.
* **The state machine's data layer.** A revision locks itself when approved or superseded
  (``is_locked``); the baseline is the approved row with ``activated_at`` stamped — there is no
  ``is_active`` boolean, so ``active_revision`` picking the latest-activated row IS the
  invariant ``bvr_activate`` keeps.
* **The EVM economics are DERIVED, never columns.** Every figure in the test-contract table
  (``.claude/tasks/test-contract-projects-7.4.md`` §3) is asserted exactly — all ``Decimal``,
  ``None`` where the ratio has no denominator (``cpi`` with no actuals), and the zero-rows CA
  reads zeros with ``health`` still green (absence of spend is not distress).
* **``cached_property`` is a documented contract** (review finding C2): ``bac``/``ac``/
  ``committed``/``active_revision`` cache per instance, so a mutation through the same
  in-memory instance reads stale until a re-fetch. The tests pin both halves.
* **``clean()`` is the same-project guard layer**: revision/wbs/control-account mismatches are
  refused at the model, not just by the scoped dropdowns.

Determinism (L16): every date basis is ``_cost_today()`` (``timezone.localdate()``) — the PV
fraction over ``cost_wbs_node_a``'s today−4..today+4 window is exactly ``0.5`` while the test
runs within one local day.

Naming (mandatory): every test is ``test_cost_*``, every module-level helper ``_cost_*`` — the
``projectinitiation_``/``planning_``/``resource_`` namespaces stay untouched. Flat functions,
house style — no Test* classes.

Scope: models only. Forms, views/urls and permissions belong to the other three lanes.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.projects.models import (
    BudgetRevision,
    CostControlAccount,
    Project,
    ProjectBudgetLine,
    ProjectExpense,
    ProjectTask,
)
from apps.projects.tests.conftest import (
    _cost_budget_line,
    _cost_control_account,
    _cost_expense,
    _cost_revision,
    _cost_today,
)

D = Decimal


def _cost_task(project, name, start, end):
    """A throwaway WBS work package with an exact planned window (PV edge tests)."""
    return ProjectTask.objects.create(
        tenant=project.tenant, project=project, name=name,
        node_type="work_package", planned_start=start, planned_end=end)


# ==============================================================================================
# Numbering — TenantNumbered across the four cost models
# ==============================================================================================

def test_cost_revision_mints_bvr_number(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    assert rev.number.startswith("BVR-")
    assert len(rev.number) == 9  # BVR- + 5 digits


def test_cost_numbers_advance_per_model_per_tenant(tenant_a, cost_project_a):
    first = _cost_revision(tenant_a, cost_project_a)
    second = _cost_revision(tenant_a, cost_project_a, no=1)
    assert int(second.number.split("-")[1]) == int(first.number.split("-")[1]) + 1


def test_cost_numbers_independent_across_tenants(tenant_a, tenant_b,
                                                 cost_project_a, cost_project_b):
    a = _cost_revision(tenant_a, cost_project_a)
    b = _cost_revision(tenant_b, cost_project_b)
    assert a.number == b.number  # same prefix+sequence, different workspaces
    assert a.tenant_id != b.tenant_id


def test_cost_save_never_renumbers(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    first = rev.number
    rev.title = "Renamed"
    rev.save()
    rev.refresh_from_db()
    assert rev.number == first


def test_cost_each_model_mints_its_own_prefix(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    ca = _cost_control_account(tenant_a, cost_project_a, "CA-N.1")
    line = _cost_budget_line(tenant_a, rev, cost_project_a)
    exp = _cost_expense(tenant_a, cost_project_a, ca)
    assert rev.number.startswith("BVR-")
    assert ca.number.startswith("CCA-")
    assert line.number.startswith("PBL-")
    assert exp.number.startswith("PEX-")


def test_cost_number_unique_per_tenant(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            dup = _cost_revision(tenant_a, cost_project_a)
            dup.number = rev.number
            dup.save()


# ==============================================================================================
# BudgetRevision
# ==============================================================================================

def test_cost_revision_choices_and_defaults(tenant_a, cost_project_a):
    assert [c[0] for c in BudgetRevision.STATUS_CHOICES] == [
        "draft", "pending_approval", "approved", "rejected", "superseded"]
    rev = _cost_revision(tenant_a, cost_project_a)
    assert rev.status == "draft"
    assert rev.revision_no == 0  # 0 = the original plan


def test_cost_revision_locked_states(tenant_a, cost_project_a):
    assert _cost_revision(tenant_a, cost_project_a).is_locked is False
    assert _cost_revision(tenant_a, cost_project_a, no=1, status="approved").is_locked is True
    # rejected is NOT frozen — it can be reworked and resubmitted
    assert _cost_revision(tenant_a, cost_project_a, no=2, status="rejected").is_locked is False
    assert _cost_revision(tenant_a, cost_project_a, no=3,
                          status="superseded").is_locked is True


def test_cost_revision_unique_project_revision_no(tenant_a, cost_project_a):
    """Two originals is a bug, not a limit — (tenant, project, revision_no) is a constraint."""
    _cost_revision(tenant_a, cost_project_a, no=0)
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            _cost_revision(tenant_a, cost_project_a, no=0)


def test_cost_revision_unique_tenant_number(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            twin = _cost_revision(tenant_a, cost_project_a, no=1)
            twin.number = rev.number
            twin.save()


def test_cost_active_revision_none_without_baseline(tenant_a, cost_project_a):
    _cost_revision(tenant_a, cost_project_a, status="approved")  # approved, NOT activated
    rev = _cost_revision(tenant_a, cost_project_a, no=1)
    assert rev.active_revision is None


def test_cost_active_revision_is_the_activated_row(tenant_a, cost_project_a):
    baseline = _cost_revision(tenant_a, cost_project_a, activate=True)
    rev = _cost_revision(tenant_a, cost_project_a, no=1)
    assert rev.active_revision == baseline


def test_cost_active_revision_prefers_latest_activation(tenant_a, cost_project_a):
    """'Most recently activated' — the timestamps must be distinguishable for the ordering to
    be defined (bvr_activate stamps now() per activation; a same-instant tie is unspecified,
    which is why the seeder/test fixtures backdate earlier baselines)."""
    _cost_revision(tenant_a, cost_project_a, activate=True,
                   activated_at=timezone.now() - timedelta(minutes=5))
    newer = _cost_revision(tenant_a, cost_project_a, no=1, activate=True,
                           activated_at=timezone.now())
    probe = _cost_revision(tenant_a, cost_project_a, no=2)
    assert probe.active_revision == newer


def test_cost_active_revision_never_a_superseded_row(tenant_a, cost_project_a):
    """Superseded rows KEEP activated_at as history — the status predicate is what keeps them
    out of the baseline slot (the shape bvr_activate leaves behind: supersede-in-place)."""
    row = _cost_revision(tenant_a, cost_project_a, activate=True)
    row.status = "superseded"  # the bvr_activate supersede writes status ONLY — stamp kept
    row.save(update_fields=["status", "updated_at"])
    probe = _cost_revision(tenant_a, cost_project_a, no=1)
    assert probe.active_revision is None


def test_cost_lines_sum_is_q2_clamped(tenant_a, cost_project_a, cost_currency):
    rev = _cost_revision(tenant_a, cost_project_a, currency=cost_currency)
    _cost_budget_line(tenant_a, rev, cost_project_a, amount="120.50")
    _cost_budget_line(tenant_a, rev, cost_project_a, category="material", amount="80.25")
    assert rev.lines_sum() == D("200.75")


def test_cost_amount_delta_is_zero_for_the_baseline_itself(tenant_a, cost_project_a):
    baseline = _cost_revision(tenant_a, cost_project_a, activate=True)
    assert baseline.amount_delta == D("0.00")


def test_cost_amount_delta_without_baseline_is_the_own_total(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    _cost_budget_line(tenant_a, rev, cost_project_a, amount="100.00")
    assert rev.amount_delta == D("100.00")  # baseline sum is 0 with no active revision


def test_cost_amount_delta_against_the_baseline(tenant_a, cost_project_a):
    baseline = _cost_revision(tenant_a, cost_project_a, activate=True)
    _cost_budget_line(tenant_a, baseline, cost_project_a, amount="300.00")
    change = _cost_revision(tenant_a, cost_project_a, no=1)
    _cost_budget_line(tenant_a, change, cost_project_a, category="material",
                      amount="100.00")
    assert change.amount_delta == D("-200.00")  # 100 − 300


def test_cost_revision_ordering_newest_first(tenant_a, cost_project_a):
    _cost_revision(tenant_a, cost_project_a)
    new = _cost_revision(tenant_a, cost_project_a, no=1)
    assert BudgetRevision.objects.filter(tenant=tenant_a).first() == new


def test_cost_revision_str(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a, title="Original budget")
    assert str(rev) == f"{rev.number} — Original budget"


# ==============================================================================================
# CostControlAccount — the EVM economics (test-contract §3 table, asserted exactly)
# ==============================================================================================

def test_cost_control_account_choices_and_defaults(tenant_a, cost_project_a):
    assert [c[0] for c in CostControlAccount.STATUS_CHOICES] == ["planning", "active", "closed"]
    assert _cost_control_account(tenant_a, cost_project_a, "CA-S.1").status == "active"
    raw = CostControlAccount(tenant=tenant_a, project=cost_project_a, code="CA-S.2",
                             name="Defaults")
    assert raw.status == "planning"  # MODEL default
    assert raw.contingency == D("0.00") and raw.percent_complete == D("0.00")


def test_cost_control_account_percent_complete_bounded(tenant_a, cost_project_a):
    ca = _cost_control_account(tenant_a, cost_project_a, "CA-P.1",
                               percent_complete=D("100.00"))
    ca.full_clean()  # the boundary value is legal
    ca.percent_complete = D("100.01")
    with pytest.raises(ValidationError):
        ca.full_clean()
    ca.percent_complete = D("-0.01")
    with pytest.raises(ValidationError):
        ca.full_clean()


def test_cost_control_account_contingency_non_negative(tenant_a, cost_project_a):
    ca = _cost_control_account(tenant_a, cost_project_a, "CA-P.2", contingency=D("-1.00"))
    with pytest.raises(ValidationError):
        ca.full_clean()


def test_cost_control_account_unique_code_per_project(tenant_a, cost_project_a):
    _cost_control_account(tenant_a, cost_project_a, "CA-U.1")
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            _cost_control_account(tenant_a, cost_project_a, "CA-U.1")


def test_cost_control_account_clean_rejects_foreign_project_wbs(tenant_a, cost_project_a,
                                                                cost_wbs_node_b):
    ca = CostControlAccount(tenant=tenant_a, project=cost_project_a, code="CA-X.1",
                            name="Cross", wbs_node=cost_wbs_node_b)
    with pytest.raises(ValidationError) as ei:
        ca.clean()
    assert "wbs_node" in ei.value.message_dict


def test_cost_control_account_clean_allows_same_project_wbs(tenant_a, cost_project_a,
                                                            cost_wbs_node_a):
    ca = CostControlAccount(tenant=tenant_a, project=cost_project_a, code="CA-X.2",
                            name="Same", wbs_node=cost_wbs_node_a)
    ca.clean()  # no raise


def test_cost_evm_column_a_no_actuals(tenant_a, cost_project_a, cost_control_account_a,
                                      cost_budget_line_a):
    """§3 column A: the CA + its 300 line on the active baseline, nothing posted."""
    ca = cost_control_account_a
    assert ca.bac == D("300.00")
    assert ca.bac_with_contingency == D("325.00")
    assert ca.ev == D("150.00")          # 300 × 50%
    assert ca.pv == D("150.00")          # 300 × 4/8 (the anchor's today−4..today+4 window)
    assert ca.ac == D("0.00")
    assert ca.committed == D("0.00")
    assert ca.available == D("300.00")
    assert ca.cv == D("150.00")
    assert ca.sv == D("0.00")
    assert ca.cpi is None                # no actuals — never a fabricated 1.0
    assert ca.spi == D("1.00")
    assert ca.eac == D("300.00")         # cpi None → fallback BAC
    assert ca.etc == D("300.00")
    assert ca.tcpi == D("0.50")
    assert ca.vac == D("0.00")
    assert ca.health == {"state": "under", "badge": "badge-green"}


def test_cost_evm_column_b_with_posted_actual(tenant_a, cost_project_a,
                                              cost_control_account_a, cost_budget_line_a,
                                              cost_expense_posted):
    """§3 column B: the full default set — one posted actual of 100."""
    ca = CostControlAccount.objects.get(pk=cost_control_account_a.pk)  # fresh cache
    assert ca.ac == D("100.00")
    assert ca.available == D("200.00")
    assert ca.cv == D("50.00")
    assert ca.cpi == D("1.50")           # 150 / 100
    assert ca.eac == D("200.00")         # 300 / 1.5
    assert ca.etc == D("100.00")
    assert ca.tcpi == D("0.75")          # (300−150)/(300−100)
    assert ca.vac == D("100.00")
    assert ca.health == {"state": "under", "badge": "badge-green"}


def test_cost_control_account_zero_rows_edge(cost_control_account_b):
    """The all-zero CA: every money figure 0, ratios None, health still green."""
    ca = cost_control_account_b
    assert ca.bac == D("0.00") and ca.ev == D("0.00") and ca.pv == D("0.00")
    assert ca.ac == D("0.00") and ca.committed == D("0.00")
    assert ca.cpi is None and ca.spi is None and ca.tcpi is None
    assert ca.eac == D("0.00") and ca.vac == D("0.00") and ca.etc == D("0.00")
    assert ca.health == {"state": "under", "badge": "badge-green"}


def test_cost_committed_only_counts_posted_commitments(tenant_a, cost_project_a,
                                                       cost_control_account_a,
                                                       cost_budget_line_a):
    _cost_expense(tenant_a, cost_project_a, cost_control_account_a,
                  entry_type="commitment", amount="40.00", status="posted")
    _cost_expense(tenant_a, cost_project_a, cost_control_account_a,
                  entry_type="commitment", amount="10.00", status="draft")
    ca = CostControlAccount.objects.get(pk=cost_control_account_a.pk)
    assert ca.committed == D("40.00")
    assert ca.available == D("260.00")   # 300 − 40 − 0


def test_cost_void_rows_stay_out_of_ac(tenant_a, cost_project_a, cost_control_account_a,
                                       cost_budget_line_a):
    _cost_expense(tenant_a, cost_project_a, cost_control_account_a, amount="75.00",
                  status="void")
    ca = CostControlAccount.objects.get(pk=cost_control_account_a.pk)
    assert ca.ac == D("0.00")            # visible, but stops counting


def test_cost_accruals_burn_like_actuals(tenant_a, cost_project_a, cost_control_account_a,
                                         cost_budget_line_a):
    _cost_expense(tenant_a, cost_project_a, cost_control_account_a, entry_type="accrual",
                  amount="60.00", status="posted")
    ca = CostControlAccount.objects.get(pk=cost_control_account_a.pk)
    assert ca.ac == D("60.00")


def test_cost_cached_property_reads_stale_until_refetch(tenant_a, cost_project_a,
                                                        cost_control_account_a,
                                                        cost_budget_line_a):
    """Review C2's contract: bac/ac/committed cache per instance — the same in-memory
    instance must NOT re-query after a mutation; a fresh fetch is current."""
    ca = cost_control_account_a
    assert ca.ac == D("0.00")
    _cost_expense(tenant_a, cost_project_a, ca, amount="50.00", status="posted")
    assert ca.ac == D("0.00")
    assert CostControlAccount.objects.get(pk=ca.pk).ac == D("50.00")


def test_cost_cached_bac_stale_until_refetch_after_new_line(tenant_a, cost_project_a,
                                                            cost_control_account_a,
                                                            cost_budget_line_a,
                                                            cost_revision_activated):
    ca = cost_control_account_a
    assert ca.bac == D("300.00")
    _cost_budget_line(tenant_a, cost_revision_activated, cost_project_a,
                      category="material", amount="100.00", control_account=ca)
    assert ca.bac == D("300.00"), "cached per instance — must NOT re-query"
    assert CostControlAccount.objects.get(pk=ca.pk).bac == D("400.00")


def test_cost_activate_flip_moves_the_baseline(tenant_a, cost_project_a,
                                               cost_control_account_a, cost_budget_line_a,
                                               cost_expense_posted, cost_revision_approved):
    """bvr_activate on a second approved revision re-baselines the project: the CA's bac drops
    to the NEW baseline's lines (none) while ac is unchanged → over/red."""
    ca = cost_control_account_a
    assert ca.health["state"] == "under"
    _cost_revision(tenant_a, cost_project_a, no=6, status="approved", activate=True)
    fresh = CostControlAccount.objects.get(pk=ca.pk)
    assert fresh.bac == D("0.00")
    assert fresh.ev == D("0.00")
    assert fresh.ac == D("100.00")       # evidence does not care which baseline is active
    assert fresh.available == D("-100.00")
    assert fresh.cpi == D("0.00")
    assert fresh.health == {"state": "over", "badge": "badge-red"}


def test_cost_posting_the_draft_expense_lands_cpi_exactly_one(tenant_a, cost_project_a,
                                                              cost_control_account_a,
                                                              cost_budget_line_a,
                                                              cost_expense_posted,
                                                              cost_expense_draft):
    cost_expense_draft.status = "posted"
    cost_expense_draft.save(update_fields=["status", "updated_at"])
    ca = CostControlAccount.objects.get(pk=cost_control_account_a.pk)
    assert ca.ac == D("150.00")          # posted 100 + newly posted 50
    assert ca.cpi == D("1.00")           # exactly 1.00 → NOT watch (strict < 1.00)
    assert ca.health["state"] == "under"


def test_cost_voiding_the_posted_expense_returns_to_column_a(tenant_a, cost_project_a,
                                                             cost_control_account_a,
                                                             cost_budget_line_a,
                                                             cost_expense_posted):
    cost_expense_posted.status = "void"
    cost_expense_posted.save(update_fields=["status", "updated_at"])
    ca = CostControlAccount.objects.get(pk=cost_control_account_a.pk)
    assert ca.ac == D("0.00")
    assert ca.cpi is None
    assert ca.eac == D("300.00") and ca.tcpi == D("0.50") and ca.vac == D("0.00")


def test_cost_health_over_via_negative_available(tenant_a, cost_project_a,
                                                 cost_control_account_a, cost_budget_line_a):
    _cost_expense(tenant_a, cost_project_a, cost_control_account_a, amount="400.00",
                  status="posted")
    ca = CostControlAccount.objects.get(pk=cost_control_account_a.pk)
    assert ca.available == D("-100.00")
    assert ca.health == {"state": "over", "badge": "badge-red"}


def test_cost_health_over_via_low_cpi(tenant_a, cost_project_a):
    baseline = _cost_revision(tenant_a, cost_project_a, activate=True)
    ca = _cost_control_account(tenant_a, cost_project_a, "CA-H.1",
                               percent_complete=D("10.00"))
    _cost_budget_line(tenant_a, baseline, cost_project_a, amount="300.00",
                      control_account=ca)
    _cost_expense(tenant_a, cost_project_a, ca, amount="100.00", status="posted")
    fresh = CostControlAccount.objects.get(pk=ca.pk)
    assert fresh.cpi == D("0.30")        # ev 30 / ac 100 — under 0.95
    assert fresh.health == {"state": "over", "badge": "badge-red"}


def test_cost_health_watch_at_cpi_exactly_095(tenant_a, cost_project_a):
    baseline = _cost_revision(tenant_a, cost_project_a, activate=True)
    ca = _cost_control_account(tenant_a, cost_project_a, "CA-H.2",
                               percent_complete=D("47.50"))
    _cost_budget_line(tenant_a, baseline, cost_project_a, amount="300.00",
                      control_account=ca)
    _cost_expense(tenant_a, cost_project_a, ca, amount="150.00", status="posted")
    fresh = CostControlAccount.objects.get(pk=ca.pk)
    assert fresh.cpi == D("0.95")        # strictly-below cut: 0.95 is NOT over
    assert fresh.health == {"state": "watch", "badge": "badge-amber"}


def test_cost_pv_full_after_the_window(tenant_a, cost_project_a):
    baseline = _cost_revision(tenant_a, cost_project_a, activate=True)
    node = _cost_task(cost_project_a, "Past package",
                      _cost_today() - timedelta(days=10),
                      _cost_today() - timedelta(days=5))
    ca = _cost_control_account(tenant_a, cost_project_a, "CA-PV.1", wbs_node=node)
    _cost_budget_line(tenant_a, baseline, cost_project_a, amount="300.00",
                      control_account=ca)
    assert ca.pv == ca.bac == D("300.00")  # fraction 1 after finish


def test_cost_pv_zero_before_the_window(tenant_a, cost_project_a):
    baseline = _cost_revision(tenant_a, cost_project_a, activate=True)
    node = _cost_task(cost_project_a, "Future package",
                      _cost_today() + timedelta(days=5),
                      _cost_today() + timedelta(days=10))
    ca = _cost_control_account(tenant_a, cost_project_a, "CA-PV.2", wbs_node=node)
    _cost_budget_line(tenant_a, baseline, cost_project_a, amount="300.00",
                      control_account=ca)
    assert ca.pv == D("0.00")


def test_cost_pv_linear_inside_the_window(tenant_a, cost_project_a, cost_control_account_a,
                                          cost_budget_line_a):
    # The fixture anchor's window is today−4..today+4 → 4 of 8 days elapsed.
    assert cost_control_account_a.pv == D("150.00")


def test_cost_pv_zero_before_the_project_window(tenant_b, cost_project_b,
                                                cost_control_account_b, cost_revision_b):
    """Unanchored CA on the DRAFT-host project whose window starts today+30 → the fallback
    project window's fraction is 0 before start. The baseline is minted here (the fixture
    project has none) so bac is non-trivial."""
    baseline = _cost_revision(tenant_b, cost_project_b, no=1, activate=True)
    _cost_budget_line(tenant_b, baseline, cost_project_b, amount="300.00",
                      control_account=cost_control_account_b)
    fresh = CostControlAccount.objects.get(pk=cost_control_account_b.pk)
    assert fresh.bac == D("300.00")
    assert fresh.pv == D("0.00")


def test_cost_pv_zero_without_any_window(tenant_a):
    bare = Project.objects.create(tenant=tenant_a, name="Windowless", status="active")
    baseline = _cost_revision(tenant_a, bare, activate=True)
    ca = _cost_control_account(tenant_a, bare, "CA-PV.3")
    _cost_budget_line(tenant_a, baseline, bare, amount="300.00", control_account=ca)
    assert ca.pv == D("0.00")            # no valid window → fraction 0, never a crash


def test_cost_control_account_ordering_newest_first(tenant_a, cost_project_a):
    _cost_control_account(tenant_a, cost_project_a, "CA-O.1")
    newest = _cost_control_account(tenant_a, cost_project_a, "CA-O.2")
    assert CostControlAccount.objects.filter(tenant=tenant_a).first() == newest


def test_cost_control_account_str(tenant_a, cost_project_a):
    ca = _cost_control_account(tenant_a, cost_project_a, "CA-S.9", name="Discovery")
    assert str(ca) == f"{ca.number} — Discovery"


# ==============================================================================================
# ProjectBudgetLine
# ==============================================================================================

def test_cost_budget_line_categories_exact():
    assert [c[0] for c in ProjectBudgetLine.CATEGORY_CHOICES] == [
        "labor", "material", "equipment", "subcontract", "overhead", "contingency", "other"]


def test_cost_budget_line_category_required_no_default(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    raw = ProjectBudgetLine(tenant=tenant_a, budget_revision=rev, project=cost_project_a,
                            amount=D("10.00"))
    with pytest.raises(ValidationError) as ei:
        raw.full_clean()
    assert "category" in ei.value.message_dict


def test_cost_budget_line_amount_non_negative(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    raw = ProjectBudgetLine(tenant=tenant_a, budget_revision=rev, project=cost_project_a,
                            category="labor", amount=D("-1.00"))
    with pytest.raises(ValidationError):
        raw.full_clean()


def test_cost_budget_line_project_must_match_revision(tenant_a, cost_project_a,
                                                      cost_revision_b):
    line = ProjectBudgetLine(tenant=tenant_a, budget_revision=cost_revision_b,
                             project=cost_project_a, category="labor", amount=D("10.00"))
    with pytest.raises(ValidationError) as ei:
        line.clean()
    assert "project" in ei.value.message_dict


def test_cost_budget_line_wbs_must_match_project(tenant_a, cost_project_a, cost_wbs_node_b):
    rev = _cost_revision(tenant_a, cost_project_a)
    line = ProjectBudgetLine(tenant=tenant_a, budget_revision=rev, project=cost_project_a,
                             category="labor", amount=D("10.00"), wbs_node=cost_wbs_node_b)
    with pytest.raises(ValidationError) as ei:
        line.clean()
    assert "wbs_node" in ei.value.message_dict


def test_cost_budget_line_control_account_must_match_project(tenant_a, cost_project_a,
                                                             cost_control_account_b):
    """cost_control_account_b hangs off project_b — the model guard refuses it even though the
    scoped dropdowns would never have offered it (the crafted-POST layer)."""
    rev = _cost_revision(tenant_a, cost_project_a)
    line = ProjectBudgetLine(tenant=tenant_a, budget_revision=rev, project=cost_project_a,
                             category="labor", amount=D("10.00"),
                             control_account=cost_control_account_b)
    with pytest.raises(ValidationError) as ei:
        line.clean()
    assert "control_account" in ei.value.message_dict


def test_cost_budget_line_numbering_and_str(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    line = _cost_budget_line(tenant_a, rev, cost_project_a, category="material",
                             amount="42.00")
    assert line.number.startswith("PBL-")
    assert str(line) == f"{line.number} — Material 42.00"


def test_cost_budget_line_ordering_newest_first(tenant_a, cost_project_a):
    rev = _cost_revision(tenant_a, cost_project_a)
    _cost_budget_line(tenant_a, rev, cost_project_a)
    newest = _cost_budget_line(tenant_a, rev, cost_project_a, category="material")
    assert ProjectBudgetLine.objects.filter(tenant=tenant_a).first() == newest


# ==============================================================================================
# ProjectExpense
# ==============================================================================================

def test_cost_expense_choices_exact():
    assert [c[0] for c in ProjectExpense.ENTRY_TYPE_CHOICES] == [
        "commitment", "actual", "accrual"]
    assert [c[0] for c in ProjectExpense.SOURCE_KIND_CHOICES] == [
        "purchase_order", "supplier_invoice", "contract", "timesheet", "manual", "accrual"]
    assert [c[0] for c in ProjectExpense.STATUS_CHOICES] == ["draft", "posted", "void"]


def test_cost_expense_defaults(tenant_a, cost_project_a, cost_control_account_a):
    raw = ProjectExpense(tenant=tenant_a, project=cost_project_a,
                         control_account=cost_control_account_a, amount=D("10.00"),
                         entry_date=_cost_today())
    assert raw.entry_type == "actual"
    assert raw.source_kind == "manual"   # deviation #4
    assert raw.status == "draft"         # drafts never burn budget


def test_cost_expense_source_kind_max_length_holds_the_longest_choice(
        tenant_a, cost_project_a, cost_control_account_a):
    exp = _cost_expense(tenant_a, cost_project_a, cost_control_account_a,
                        source_kind="supplier_invoice")  # 16 chars — the fields.E009 guard
    exp.full_clean()  # no raise


def test_cost_expense_entry_date_required(tenant_a, cost_project_a, cost_control_account_a):
    raw = ProjectExpense(tenant=tenant_a, project=cost_project_a,
                         control_account=cost_control_account_a, amount=D("10.00"))
    with pytest.raises(ValidationError) as ei:
        raw.full_clean()
    assert "entry_date" in ei.value.message_dict


def test_cost_expense_control_account_required(tenant_a, cost_project_a):
    raw = ProjectExpense(tenant=tenant_a, project=cost_project_a, amount=D("10.00"),
                         entry_date=_cost_today())
    with pytest.raises(ValidationError) as ei:
        raw.full_clean()
    assert "control_account" in ei.value.message_dict


def test_cost_expense_amount_non_negative(tenant_a, cost_project_a, cost_control_account_a):
    raw = ProjectExpense(tenant=tenant_a, project=cost_project_a,
                         control_account=cost_control_account_a, amount=D("-5.00"),
                         entry_date=_cost_today())
    with pytest.raises(ValidationError):
        raw.full_clean()


def test_cost_expense_control_account_must_match_project(tenant_a, cost_project_a,
                                                         cost_control_account_b):
    exp = ProjectExpense(tenant=tenant_a, project=cost_project_a,
                         control_account=cost_control_account_b, amount=D("5.00"),
                         entry_date=_cost_today())
    with pytest.raises(ValidationError) as ei:
        exp.clean()
    assert "control_account" in ei.value.message_dict


def test_cost_expense_wbs_must_match_project(tenant_a, cost_project_a, cost_control_account_a,
                                             cost_wbs_node_b):
    exp = ProjectExpense(tenant=tenant_a, project=cost_project_a,
                         control_account=cost_control_account_a, amount=D("5.00"),
                         entry_date=_cost_today(), wbs_node=cost_wbs_node_b)
    with pytest.raises(ValidationError) as ei:
        exp.clean()
    assert "wbs_node" in ei.value.message_dict


def test_cost_expense_is_locked_states(tenant_a, cost_project_a, cost_control_account_a):
    assert _cost_expense(tenant_a, cost_project_a, cost_control_account_a).is_locked is False
    assert _cost_expense(tenant_a, cost_project_a, cost_control_account_a,
                         status="posted").is_locked is True
    assert _cost_expense(tenant_a, cost_project_a, cost_control_account_a,
                         status="void").is_locked is True


def test_cost_expense_ordering_by_entry_date(tenant_a, cost_project_a, cost_control_account_a):
    today = _cost_today()
    newer = _cost_expense(tenant_a, cost_project_a, cost_control_account_a, entry_date=today)
    older = _cost_expense(tenant_a, cost_project_a, cost_control_account_a,
                          entry_date=today - timedelta(days=3))
    rows = list(ProjectExpense.objects.filter(tenant=tenant_a)[:2])
    assert rows[0] == newer and rows[1] == older


def test_cost_expense_numbering_and_str(tenant_a, cost_project_a, cost_control_account_a):
    exp = _cost_expense(tenant_a, cost_project_a, cost_control_account_a,
                        entry_type="commitment", amount="12.34")
    assert exp.number.startswith("PEX-")
    assert str(exp) == f"{exp.number} — Commitment 12.34"


def test_cost_expense_soft_source_reference_is_a_string(tenant_a, cost_project_a,
                                                        cost_control_account_a):
    """Ruling 5: the PO reference is a bare CharField — no FK, no constraint, nothing to
    migrate when the owning system renumbers."""
    exp = _cost_expense(tenant_a, cost_project_a, cost_control_account_a,
                        source_kind="purchase_order", source_number="PO-00042")
    exp.full_clean()
    assert exp.source_number == "PO-00042"
