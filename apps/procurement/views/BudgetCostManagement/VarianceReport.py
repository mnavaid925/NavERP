"""Procurement 6.15 Budget & Cost Management — the Budget Variance Report.

**Variance Analysis** bullet: budgeted vs committed vs invoiced, one row per
(GL account, department) pair, with a CSV download.

**Actuals basis.** "What was actually spent" is read from 6.13's RECOGNISED supplier invoices
(``approved`` / ``scheduled`` / ``paid`` — the same population 6.14 analytics reports on), not
from scm 4.18's landed-cost vouchers: those answer the supply-chain incurrence question without a
GL dimension, and this page answers the procurement budget question with one.

**The remaining formula, stated plainly (and on the page).**
``remaining = budgeted - committed - invoiced-without-a-PO``.
Invoiced spend that sits behind an open purchase order is ALREADY inside that commitment — a PO
stays a commitment until it is closed — so deducting it again would double-count. Only invoices
raised without a purchase order (services billed direct) are deducted on top of commitments. The
invoiced column itself is informational: how far the commitments have progressed to paper, plus —
when no specific budget is selected — the PO-less invoices.

**The one honest gap, stated rather than papered over.** When a specific budget IS selected,
invoices raised without a purchase order cannot be attributed to it and are left out (the page
says so); the org-unit of any line is resolved through the requisition behind the purchase order,
and a line whose chain is broken by a SET_NULL lands in the ``Unassigned`` row rather than being
dropped — a breakdown that silently drops rows makes its totals disagree with the KPI strip.

**Arithmetic and caps.** Grouped ``.values(...).annotate(Sum(...))`` queries fetch per-pair
subtotals (one round trip, never one query per row); every ratio is done in Decimal in Python,
and ``.order_by()`` on the grouped querysets is LOAD-BEARING — Django appends a model's
``Meta.ordering`` to the GROUP BY, and every model involved has one. Same pattern and same
reasoning as scm 4.18's ``_grouped_sum``; copied locally per the peer-sub-module rule.
"""
import csv
import datetime
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse

from apps.core.crud import as_db_int
from apps.accounting.models import Budget, BudgetLine, FiscalPeriod, GLAccount
from apps.core.models import OrgUnit

from apps.procurement.models._base import ZERO
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULES directly (see
# BudgetChecks.py for the reason).
from apps.procurement.models.BudgetCostManagement.BudgetMappings import (
    COMMITTED_PR_STATUSES, OPEN_COMMITMENT_PO_STATUSES,
    committed_pr_lines, open_po_commitment_lines)
from apps.procurement.models.SpendAnalyticsReporting.SpendClassificationRules import (
    RECOGNISED_INVOICE_STATUSES, invoiced_line_window, money)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import csv_safe

TEMPLATE = "procurement/budgetcost/variance_report.html"

#: Same cap discipline as scm 4.18's computed reports: state the limit rather than imply the
#: totals are complete.
ROW_CAP = 500

#: The label a row with no org unit carries. NEVER blank — a nameless row in a variance report
#: is one a reader silently attributes to the row above it.
UNASSIGNED_LABEL = "Unassigned"

#: Printed on the page and in the CSV's covering context — the remaining formula, in the
#: reader's words, so nobody has to read this module to trust a figure.
REMAINING_NOTE = (
    "Remaining = budgeted - committed - recognised invoices raised without a purchase order. "
    "An invoice behind an open purchase order is already inside that commitment, so it is shown "
    "but not deducted again."
)

#: Printed when a specific budget is selected — see the module docstring's honest gap.
SCOPED_INVOICE_NOTE = (
    "Invoices raised without a purchase order cannot be attributed to one budget and are left "
    "out of this scoped view; they appear on the all-budgets view."
)


def _as_date(raw):
    """A ``YYYY-MM-DD`` GET value as a ``date``, or ``None`` — junk is skipped, never raised on
    (L11; a local copy of scm 4.18's helper per the peer-sub-module rule)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _variance_pct(variance, base):
    """``variance / base * 100`` at 1dp, or ``None`` when there is no base to divide by.

    ``None``, never zero: "no budget set" and "exactly on budget" are different findings and
    the templates render them differently.
    """
    base = base or ZERO
    if base <= ZERO:
        return None
    return (variance * Decimal("100") / base).quantize(Decimal("0.1"))


def _grouped_pair_sum(qs, key1, key2, column):
    """``{(group1, group2): Decimal}`` from ONE grouped query. ``.order_by()`` is load-bearing —
    see the module docstring."""
    rows = qs.order_by().values(key1, key2).annotate(s=Sum(column))
    return {(row[key1], row[key2]): (row["s"] or ZERO) for row in rows}


def _variance_rows(tenant, budget, period):
    """``(rows, truncated)`` — budgeted vs committed vs invoiced, one row per (GL, org) pair."""
    from apps.scm.models import PurchaseOrderLine, PurchaseRequisitionLine

    scoped = budget is not None

    # -- budgeted: the accounting module's own lines, grouped by the pair ------------------------
    budget_lines = BudgetLine.objects.filter(tenant=tenant)
    if budget is not None:
        budget_lines = budget_lines.filter(budget=budget)
    if period is not None:
        budget_lines = budget_lines.filter(budget__fiscal_period=period)
    budgeted = _grouped_pair_sum(budget_lines, "gl_account", "org_unit", "amount")

    # -- committed: open PO lines + approved-not-converted requisition lines ---------------------
    po_lines = PurchaseOrderLine.objects.filter(
        purchase_order__tenant=tenant,
        purchase_order__status__in=OPEN_COMMITMENT_PO_STATUSES)
    pr_lines = PurchaseRequisitionLine.objects.filter(
        requisition__tenant=tenant, requisition__status__in=COMMITTED_PR_STATUSES)
    if budget is not None:
        po_lines = po_lines.filter(purchase_order__requisition__budget=budget)
        pr_lines = pr_lines.filter(requisition__budget=budget)
    if period is not None:
        po_lines = po_lines.filter(purchase_order__requisition__budget__fiscal_period=period)
        pr_lines = pr_lines.filter(requisition__budget__fiscal_period=period)
    committed_po = _grouped_pair_sum(
        po_lines, "gl_account", "purchase_order__requisition__org_unit", "line_total")
    committed_pr = _grouped_pair_sum(
        pr_lines, "gl_account", "requisition__org_unit", "line_total")

    # -- invoiced: recognised supplier invoices ---------------------------------------------------
    # The window is the widest one worth rendering: everything recognised up to tomorrow. The
    # variance question is "to date", not "this month".
    end = datetime.date.today() + datetime.timedelta(days=1)
    start = datetime.date(end.year - 10, 1, 1)
    inv_lines = invoiced_line_window(tenant, start, end)
    if budget is not None:
        # With a budget selected only PO-backed invoices can be attributed to it — the honest gap
        # the page prints (SCOPED_INVOICE_NOTE).
        inv_lines = inv_lines.filter(invoice__purchase_order__requisition__budget=budget)
    if period is not None:
        inv_lines = inv_lines.filter(
            invoice__purchase_order__requisition__budget__fiscal_period=period)
    invoiced = _grouped_pair_sum(
        inv_lines, "gl_account", "invoice__purchase_order__requisition__org_unit", "line_total")
    # The ONLY invoiced money deducted from the budget on top of commitments: invoices with no
    # purchase order, because nothing else has committed it.
    standalone = _grouped_pair_sum(
        inv_lines.filter(invoice__purchase_order__isnull=True),
        "gl_account", "invoice__purchase_order__requisition__org_unit", "line_total")

    keys = set(budgeted) | set(committed_po) | set(committed_pr) | set(standalone)
    if not scoped:
        keys |= set(invoiced)
    if not keys:
        return [], False

    # ONE query each for the labels — never a per-row get().
    gl_ids = {key[0] for key in keys if key[0] is not None}
    org_ids = {key[1] for key in keys if key[1] is not None}
    accounts = {account.pk: account for account in
                GLAccount.objects.filter(tenant=tenant, pk__in=gl_ids)}
    units = {unit.pk: unit for unit in OrgUnit.objects.filter(tenant=tenant, pk__in=org_ids)}

    rows = []
    for gl_id, org_id in keys:
        account = accounts.get(gl_id) if gl_id is not None else None
        unit = units.get(org_id) if org_id is not None else None
        budgeted_amount = money(budgeted.get((gl_id, org_id), ZERO))
        committed = money(committed_po.get((gl_id, org_id), ZERO) +
                          committed_pr.get((gl_id, org_id), ZERO))
        # The scoped case is already handled upstream: with a budget selected, `inv_lines` is
        # filtered to that budget's PO-backed invoices before the grouping runs.
        invoiced_amount = money(invoiced.get((gl_id, org_id), ZERO))
        standalone_amount = money(standalone.get((gl_id, org_id), ZERO))
        remaining = money(budgeted_amount - committed - standalone_amount)
        rows.append({
            "gl_code": account.code if account is not None else "—",
            "gl_name": account.name if account is not None else "(no GL account)",
            "org_unit_name": unit.name if unit is not None else UNASSIGNED_LABEL,
            "budgeted": budgeted_amount,
            "committed": committed,
            "invoiced": invoiced_amount,
            "standalone_invoiced": standalone_amount,
            "remaining": remaining,
            "variance_pct": _variance_pct(remaining, budgeted_amount),
            "over_budget": remaining < ZERO,
        })

    # Biggest budget first; unbudgeted spend (budgeted == 0) sorts to the bottom, which is
    # exactly where a reader looks for it.
    rows.sort(key=lambda r: (-(r["budgeted"] or ZERO), r["gl_code"], r["org_unit_name"]))
    truncated = len(rows) > ROW_CAP
    return rows[:ROW_CAP], truncated


def _variance_context(request):
    """Shared parse + row build for the page and its CSV — one code path, two renders."""
    budget_id = as_db_int(request.GET.get("budget"))
    period_id = as_db_int(request.GET.get("fiscal_period"))

    budgets = Budget.objects.none()
    fiscal_periods = FiscalPeriod.objects.none()
    selected_budget = selected_period = None
    rows, truncated = [], False

    if request.tenant is not None:
        budgets = (Budget.objects.filter(tenant=request.tenant)
                   .select_related("fiscal_period").order_by("-id"))
        fiscal_periods = (FiscalPeriod.objects.filter(tenant=request.tenant)
                          .order_by("-start_date", "-id"))
        if budget_id is not None:
            selected_budget = budgets.filter(pk=budget_id).first()
        if period_id is not None:
            selected_period = fiscal_periods.filter(pk=period_id).first()
        rows, truncated = _variance_rows(request.tenant, selected_budget, selected_period)

    totals = {
        "budgeted": money(sum((r["budgeted"] for r in rows), ZERO)),
        "committed": money(sum((r["committed"] for r in rows), ZERO)),
        "invoiced": money(sum((r["invoiced"] for r in rows), ZERO)),
        "remaining": money(sum((r["remaining"] for r in rows), ZERO)),
    }
    return rows, truncated, totals, budgets, fiscal_periods, selected_budget, selected_period


@login_required
def budget_variance(request):
    """Budgeted vs committed vs invoiced per (GL, department). View-time, writes nothing —
    the budget belongs to Module 2 and a stored balance here would be a second source of truth."""
    (rows, truncated, totals, budgets, fiscal_periods,
     selected_budget, selected_period) = _variance_context(request)

    return render(request, TEMPLATE, {
        "rows": rows,
        "totals": totals,
        "budgets": budgets,
        "fiscal_periods": fiscal_periods,
        "selected_budget": selected_budget,
        "selected_period": selected_period,
        "remaining_note": REMAINING_NOTE,
        "scoped_invoice_note": SCOPED_INVOICE_NOTE if selected_budget is not None else "",
        "row_cap": ROW_CAP,
        "truncated": truncated,
    })


@login_required
def budget_variance_export(request):
    """CSV of the exact rows the page shows — every cell through ``csv_safe``."""
    (rows, _truncated, totals, _budgets, _periods,
     selected_budget, _period) = _variance_context(request)

    response = HttpResponse(content_type="text/csv")
    # Filename from the system-assigned budget number only, never user text.
    suffix = f"-{selected_budget.number}" if selected_budget is not None else ""
    response["Content-Disposition"] = f'attachment; filename="budget-variance{suffix}.csv"'
    writer = csv.writer(response)
    writer.writerow([csv_safe(cell) for cell in (
        "GL Code", "GL Account", "Department", "Budgeted", "Committed", "Invoiced",
        "Remaining", "Variance %")])
    for row in rows:
        writer.writerow([csv_safe(cell) for cell in (
            row["gl_code"], row["gl_name"], row["org_unit_name"],
            str(row["budgeted"]), str(row["committed"]), str(row["invoiced"]),
            str(row["remaining"]),
            "" if row["variance_pct"] is None else str(row["variance_pct"]))])
    writer.writerow([csv_safe(cell) for cell in (
        "TOTAL", "", "", str(totals["budgeted"]), str(totals["committed"]),
        str(totals["invoiced"]), str(totals["remaining"]), "")])
    return response
