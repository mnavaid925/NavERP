"""Procurement 6.15 Budget & Cost Management — the Budget Availability Checker.

**Budget Availability Check** bullet. One GET form page: pick a budget, optionally a department,
a GL account and the amount about to be spent — the page answers "is there room?" with
budgeted / committed / requested / remaining.

**Advisory and view-time, deliberately.** Exactly the posture of scm 4.1's
``PurchaseRequisition.budget_check()`` and scm 4.18's variance report: the budget belongs to
Module 2, nothing here is a stored encumbrance, and nothing this page computes is written
anywhere. Two buyers checking at once both see the same remaining figure — there is no lock, and
pretending there is one would be a lie the page should not tell.

**Figures, like-for-like (the 4.1 rule).** Committed is split by source and never double-counted:
open PO lines through the requisition behind the order, PLUS requisition lines that are approved
but NOT converted (a converted requisition IS its PO — counting both would double the spend).
Requested is the pending-approval pipeline. A budget line with no org unit is a company-wide line
and applies to every department, exactly as ``budget_check()`` reads it.

**L11 discipline.** All four GET params are parsed defensively — ``as_db_int`` for the three pks,
a local ``_as_decimal`` for the amount; junk narrows nothing and returns 200. The selected
budget/org/GL are resolved THROUGH the tenant-scoped querysets, so a pk belonging to another
workspace selects nothing instead of narrowing this page by a stranger's row.
"""
from decimal import Decimal, InvalidOperation

from django.db.models import Q, Sum

from apps.core.crud import as_db_int
from apps.accounting.models import Budget, GLAccount
from apps.core.models import OrgUnit

from apps.procurement.models._base import ZERO
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULES directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.BudgetCostManagement.BudgetMappings import (
    committed_pr_lines, open_po_commitment_lines, requested_pr_lines)
from apps.procurement.models.SpendAnalyticsReporting.SpendClassificationRules import money
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE = "procurement/budgetcost/availability.html"

#: Printed under the figures. ONE constant so the page cannot describe its own honesty
#: differently from one render to the next.
ADVISORY_NOTE = (
    "This check is advisory and computed at view time: nothing is reserved or written when you "
    "run it, and there is no lock — two requisitions checked at the same moment both see the "
    "same remaining figure. Commitments are purchase orders that are approved or later (never "
    "draft, cancelled or closed) plus requisitions approved but not yet converted to an order."
)

#: Amounts across the spine are summed at face value — there is no exchange-rate table anywhere
#: in this repo, and the page says so rather than implying a conversion.
CURRENCY_NOTE = (
    "Amounts are summed at face value across currencies — there is no exchange-rate table in "
    "this system, so nothing below is converted."
)


def _as_decimal(raw):
    """A GET value as a non-negative Decimal, or ``None``.

    Junk is SKIPPED, never raised on — the same L11 posture ``as_db_int`` takes for int filters.
    A negative "amount to spend" makes no sense here, so it is treated the same as junk.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite() or value < 0:
        return None
    return value


def _availability_figures(tenant, budget, org_unit, gl_account, check_amount):
    """``{"budgeted", "po_committed", "pr_committed", "requested", "remaining", "over_budget"}``.

    Mirrors ``budget_check()``'s semantics, extended with the PO commitment column 6.15 exists
    to add. All four populations are scoped through the SAME budget, and the GL / org narrowing
    applies to all of them so the figures are like-for-like.
    """
    line_qs = budget.lines.all()
    if gl_account is not None:
        line_qs = line_qs.filter(gl_account_id=gl_account.pk)
    if org_unit is not None:
        # A budget line with no org unit is a company-wide line and applies to every department.
        line_qs = line_qs.filter(Q(org_unit_id=org_unit.pk) | Q(org_unit__isnull=True))
    budgeted = money(line_qs.aggregate(s=Sum("amount"))["s"] or ZERO)

    po_lines = open_po_commitment_lines(tenant).filter(
        purchase_order__requisition__budget_id=budget.pk)
    pr_lines = committed_pr_lines(tenant).filter(requisition__budget_id=budget.pk)
    requested = requested_pr_lines(tenant).filter(requisition__budget_id=budget.pk)
    if gl_account is not None:
        po_lines = po_lines.filter(gl_account_id=gl_account.pk)
        pr_lines = pr_lines.filter(gl_account_id=gl_account.pk)
        requested = requested.filter(gl_account_id=gl_account.pk)
    if org_unit is not None:
        po_lines = po_lines.filter(purchase_order__requisition__org_unit_id=org_unit.pk)
        pr_lines = pr_lines.filter(requisition__org_unit_id=org_unit.pk)
        requested = requested.filter(requisition__org_unit_id=org_unit.pk)

    po_committed = money(po_lines.aggregate(s=Sum("line_total"))["s"] or ZERO)
    pr_committed = money(pr_lines.aggregate(s=Sum("line_total"))["s"] or ZERO)
    requested_total = money(requested.aggregate(s=Sum("line_total"))["s"] or ZERO)

    spend = check_amount or ZERO
    remaining = money(budgeted - po_committed - pr_committed - requested_total - spend)
    return {
        "budgeted": budgeted,
        "po_committed": po_committed,
        "pr_committed": pr_committed,
        "committed": money(po_committed + pr_committed),
        "requested": requested_total,
        "check_amount": money(spend),
        "remaining": remaining,
        "over_budget": remaining < ZERO,
    }


@login_required
def budget_availability(request):
    """Is there room in this budget? Advisory, view-time, writes nothing — see the docstring."""
    budget_id = as_db_int(request.GET.get("budget"))
    org_unit_id = as_db_int(request.GET.get("org_unit"))
    gl_account_id = as_db_int(request.GET.get("gl_account"))
    check_amount = _as_decimal(request.GET.get("amount"))

    budgets = Budget.objects.none()
    org_units = OrgUnit.objects.none()
    gl_accounts = GLAccount.objects.none()
    selected_budget = selected_org_unit = selected_gl_account = None
    figures = None

    if request.tenant is not None:
        budgets = (Budget.objects.filter(tenant=request.tenant)
                   .select_related("fiscal_period").order_by("-id"))
        org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
        gl_accounts = (GLAccount.objects.filter(tenant=request.tenant, is_active=True)
                       .order_by("code"))
        # Resolved THROUGH the tenant-scoped querysets: a foreign pk selects nothing.
        if budget_id is not None:
            selected_budget = budgets.filter(pk=budget_id).first()
        if org_unit_id is not None:
            selected_org_unit = org_units.filter(pk=org_unit_id).first()
        if gl_account_id is not None:
            selected_gl_account = gl_accounts.filter(pk=gl_account_id).first()
        if selected_budget is not None:
            figures = _availability_figures(
                request.tenant, selected_budget, selected_org_unit, selected_gl_account,
                check_amount)

    return render(request, TEMPLATE, {
        "budgets": budgets,
        "org_units": org_units,
        "gl_accounts": gl_accounts,
        "selected_budget": selected_budget,
        "selected_org_unit": selected_org_unit,
        "selected_gl_account": selected_gl_account,
        # Echoed as a plain string for the <input type="number"> value; junk arrives as None and
        # the input renders empty.
        "check_amount": ("" if check_amount is None else str(check_amount)),
        "figures": figures,
        "advisory_note": ADVISORY_NOTE,
        "currency_note": CURRENCY_NOTE,
    })
