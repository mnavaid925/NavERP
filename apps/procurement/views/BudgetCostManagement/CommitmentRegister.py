"""Procurement 6.15 Budget & Cost Management — the Commitment Register.

**Commitment Accounting** bullet: one read-only page listing every live commitment in the
workspace — purchase orders that are approved or later but not closed, and requisitions that are
approved but not yet converted to an order.

**Nothing here is stored.** The register is a VIEW over the scm document spine (L36): there is no
encumbrance table, no cached balance, no ``transaction.atomic()`` and no audit row — exactly the
"derive, don't store" posture ``PurchaseRequisition.budget_check()`` documents. A commitment
moves through lifecycle purely by its source document's status changing.

**The double-count rule.** A CONVERTED requisition is excluded: it has become its purchase order,
and counting both would show one commitment twice. This is why the tuple of commitment statuses
lives in the BudgetMappings model module — the checker and the variance report read the same one.

**Four rules shared with scm 4.18's computed reports** (copied locally, per the peer-sub-module
rule): (1) nothing writes; (2) ``request.tenant is None`` renders an empty register, never a 500;
(3) junk GET params narrow nothing and return 200; (4) every row's url is reversed HERE in
Python, never in the template.
"""
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse

from apps.core.crud import as_db_int
from apps.accounting.models import Budget
from apps.core.models import Party
from apps.scm.models import PurchaseOrder, PurchaseRequisition

from apps.procurement.models._base import ZERO
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly (see
# BudgetChecks.py for the reason).
from apps.procurement.models.BudgetCostManagement.BudgetMappings import (
    COMMITTED_PR_STATUSES, OPEN_COMMITMENT_PO_STATUSES)
from apps.procurement.models.SpendAnalyticsReporting.SpendClassificationRules import money
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE = "procurement/budgetcost/commitment_register.html"

#: Hard ceiling on rendered rows — reported to the template as ``row_cap`` with ``truncated``, so
#: the page states the limit instead of implying its totals are complete.
ROW_CAP = 500

#: The ``?source=`` vocabulary. Frozen here because the template compares ``request.GET.source``
#: against these exact values.
SOURCE_CHOICES = [
    ("po", "Purchase Orders"),
    ("pr", "Requisitions"),
]

#: Badge colours for the PO commitment lifecycle (theme.css colour-named badges only, L33).
PO_STATUS_CSS = {
    "approved": "badge-amber",
    "sent": "badge-info",
    "acknowledged": "badge-info",
    "partially_received": "badge-green",
    "received": "badge-green",
}

_MONEY = DecimalField(max_digits=20, decimal_places=2)

#: The vendor filter applies to purchase orders only — a requisition has no vendor yet. When it
#: is set the requisition rows are hidden and the page says so.
VENDOR_FILTER_NOTE = (
    "The supplier filter applies to purchase orders: a requisition has no supplier yet, so "
    "requisition rows are hidden while this filter is set."
)


def _supplier_parties(tenant):
    """Parties this tenant can buy from — the 6.5/6.8 helper rule (supplier OR vendor role)."""
    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct()
            .order_by("name"))


def _po_rows(tenant, q, budget, vendor):
    """Open purchase-order commitments, one row each, amounts from the lines (never the header's
    editable=False totals alone — the annotation and the header total are the same figure, but
    the annotation keeps the row correct even mid-edit before recalc_totals has run)."""
    qs = (PurchaseOrder.objects
          .filter(tenant=tenant, status__in=OPEN_COMMITMENT_PO_STATUSES)
          .select_related("vendor", "requisition", "requisition__budget")
          .annotate(commit_total=Coalesce(
              Sum("lines__line_total"), Value(ZERO), output_field=_MONEY)))
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(vendor__name__icontains=q))
    if budget is not None:
        qs = qs.filter(requisition__budget_id=budget.pk)
    if vendor is not None:
        qs = qs.filter(vendor_id=vendor.pk)

    batch = list(qs[:ROW_CAP + 1])
    rows = []
    for order in batch[:ROW_CAP]:
        rows.append({
            "source": "po",
            "number": order.number,
            "url": reverse("scm:purchaseorder_detail", args=[order.pk]),
            "party": order.vendor.name if order.vendor_id else "",
            "status": order.status,
            "status_label": order.get_status_display(),
            "status_css": PO_STATUS_CSS.get(order.status, "badge-slate"),
            "budget": order.requisition.budget if order.requisition_id and
            order.requisition.budget_id else None,
            "amount": money(order.commit_total),
        })
    return rows, len(batch) > ROW_CAP


def _pr_rows(tenant, q, budget):
    """Approved-not-converted requisition commitments. ``estimated_total`` is the model's own
    derived figure — reading it, not recomputing it, keeps one source of truth."""
    qs = (PurchaseRequisition.objects
          .filter(tenant=tenant, status__in=COMMITTED_PR_STATUSES)
          .select_related("budget", "requester"))
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(title__icontains=q))
    if budget is not None:
        qs = qs.filter(budget_id=budget.pk)

    batch = list(qs[:ROW_CAP + 1])
    rows = []
    for req in batch[:ROW_CAP]:
        requester = req.requester
        rows.append({
            "source": "pr",
            "number": req.number,
            "url": reverse("procurement:req_detail", args=[req.pk]),
            "party": (requester.get_full_name() or requester.username) if requester else "",
            "status": req.status,
            "status_label": req.get_status_display(),
            "status_css": "badge-green",
            "budget": req.budget if req.budget_id else None,
            "amount": money(req.estimated_total or ZERO),
        })
    return rows, len(batch) > ROW_CAP


@login_required
def commitment_register(request):
    """Every live commitment in the workspace — derived on read, stored nowhere."""
    q = (request.GET.get("q") or "").strip()
    source = (request.GET.get("source") or "").strip()
    if source not in {"po", "pr"}:
        source = ""
    budget_id = as_db_int(request.GET.get("budget"))
    vendor_id = as_db_int(request.GET.get("vendor"))

    budgets = Budget.objects.none()
    vendors = Party.objects.none()
    selected_budget = selected_vendor = None
    rows, truncated = [], False

    if request.tenant is not None:
        budgets = (Budget.objects.filter(tenant=request.tenant)
                   .select_related("fiscal_period").order_by("-id"))
        vendors = _supplier_parties(request.tenant)
        if budget_id is not None:
            selected_budget = budgets.filter(pk=budget_id).first()
        if vendor_id is not None:
            selected_vendor = vendors.filter(pk=vendor_id).first()

        if source != "pr":
            found, cut = _po_rows(request.tenant, q, selected_budget, selected_vendor)
            rows.extend(found)
            truncated = truncated or cut
        # A requisition has no supplier: with a vendor filter set its rows are hidden, and the
        # template prints VENDOR_FILTER_NOTE rather than silently dropping them.
        if source != "po" and selected_vendor is None:
            found, cut = _pr_rows(request.tenant, q, selected_budget)
            rows.extend(found)
            truncated = truncated or cut

    # Biggest commitment first — the order a budget owner reads in.
    rows.sort(key=lambda r: (-(r["amount"] or ZERO), r["number"] or ""))
    if len(rows) > ROW_CAP:
        rows = rows[:ROW_CAP]
        truncated = True

    po_total = money(sum((r["amount"] for r in rows if r["source"] == "po"), ZERO))
    pr_total = money(sum((r["amount"] for r in rows if r["source"] == "pr"), ZERO))
    return render(request, TEMPLATE, {
        "rows": rows,
        "totals": {
            "count": len(rows),
            "po_committed": po_total,
            "pr_committed": pr_total,
            "committed": money(po_total + pr_total),
        },
        "budgets": budgets,
        "vendors": vendors,
        "selected_budget": selected_budget,
        "selected_vendor": selected_vendor,
        "source_choices": SOURCE_CHOICES,
        "vendor_filter_note": VENDOR_FILTER_NOTE if selected_vendor is not None else "",
        "row_cap": ROW_CAP,
        "truncated": truncated,
    })
