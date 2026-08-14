"""SCM 4.18 Finance & Accounting Integration — the four READ-ONLY computed reports.

``finance_payables`` · ``finance_receivables`` · ``finance_budget_variance`` · ``landed_cost_variance``

--------------------------------------------------------------------------------------------------
FOUR RULES EVERY VIEW IN THIS MODULE OBEYS
--------------------------------------------------------------------------------------------------

**1. Nothing here writes.** No model, no form, no ``transaction.atomic()``, no ``write_audit_log``,
no ``JournalEntry``. Three of 4.18's five NavERP.md bullets (Accounts Payable, Accounts Receivable,
Budgeting) are delivered as reports over tables that already shipped rather than as new tables —
see the L29 section in ``apps/scm/models/FinanceIntegration/Reports.py`` for why a fourth copy of
"what we owe" would be a defect. Because they only read, none of them is ``@tenant_admin_required``:
a member who can see a goods receipt can already see what it cost.

**2. ``request.tenant is None`` returns an EMPTY report, never a 500.** The superuser has
``tenant=None`` BY DESIGN (multi-tenancy rule 1), so every view returns zeroed totals and an empty
row list rather than querying with ``tenant=None`` and rendering a page whose totals are somebody
else's. Each template's empty state names *why* it is empty.

**3. Junk in any GET parameter narrows nothing and returns 200 (L11).** Choice parameters are
checked against their own ``*_CHOICES`` set before they reach ``.filter()``; the two pk parameters go
through :func:`~apps.core.crud.as_db_int` (which refuses non-decimal, Unicode-superscript AND
over-64-bit values); the two date parameters go through :func:`_as_date`, which returns ``None`` on
anything that is not ``YYYY-MM-DD``. A hand-edited ``?status=lol`` must not 500 on a URL anybody can
type into the address bar.

**4. Every row's ``url`` is ALREADY REVERSED HERE, in Python.** The templates render
``<a href="{{ row.url }}">`` and never call ``{% url %}`` on a variable view name — the latter is
exactly how a report page that unions three different documents turns into a ``NoReverseMatch`` 500
the moment one source contributes a row.

--------------------------------------------------------------------------------------------------
ARITHMETIC AND CAPS
--------------------------------------------------------------------------------------------------
Every figure is summed in PYTHON through ``q2``/``q4`` from ``models/_base.py``, never with an
``F()`` expression — the SQLite integer-division trap ``FreightInvoice.recalc_amounts`` names in its
own docstring. Grouped ``.values(...).annotate(Sum(...))`` queries are used to FETCH per-group
subtotals (one round trip, never one query per row); the cross-group merging and every ratio is done
in Decimal, in Python.

Each report caps its output at :data:`ROW_CAP` rows and reports ``truncated`` so the template can say
"showing the first N" in its own words instead of quietly lying about a total. The two reports that
have to walk detail rows to build their groups also cap that SCAN at :data:`SCAN_CAP`; hitting either
cap sets the same ``truncated`` flag.
"""
import datetime

from django.db.models import DecimalField, Value
from django.db.models.functions import Coalesce
# Row links are reversed here rather than in the template — see rule 4 above.
from django.urls import reverse

from apps.scm.views._common import *  # noqa: F401,F403

from apps.scm.models._base import ZERO, q2, q4
from apps.scm.models import (
    ClientBillingRun,
    FreightInvoice,
    GoodsReceiptLine,
    GoodsReceiptNote,
    LandedCostAllocation,
    LandedCostCharge,
    LandedCostVoucher,
    PurchaseOrderLine,
    PurchaseRequisitionLine,
    ReturnAuthorization,
    SalesOrder,
)
from apps.accounting.models import Bill, Budget, BudgetLine, FiscalPeriod, Invoice
# The budget-variance report groups by `core.OrgUnit` (2.13's `BudgetLine.org_unit` IS the
# supply-chain department dimension), so the spine model is imported directly rather than reached
# through a relation — `_common` re-exports `Party` but not this one.
from apps.core.models import OrgUnit


#: Hard ceiling on the rows any one report renders. Reported to the template as ``row_cap`` and
#: paired with ``truncated`` so the page states the limit rather than implying its totals are
#: complete. These are scan-and-group reports with no pagination by design — a filter bar narrows
#: them, a page 2 would just hide the cap behind a Next button.
ROW_CAP = 500

#: Ceiling on the DETAIL rows the grouping reports walk to build those rows. A landed-cost variance
#: grouped by item reads one allocation per (charge x received stock move), so the scan is an order
#: of magnitude wider than its output; capping the scan separately keeps a workspace with a very
#: large receipt from turning a report page into an unbounded fetch.
SCAN_CAP = ROW_CAP * 10

#: The ``?source=`` vocabulary on the two ledger reports. Frozen here (rather than derived) because
#: the templates compare ``request.GET.source`` against these exact values.
PAYABLE_SOURCE_CHOICES = [
    ("grn", "Goods Receipts"),
    ("freight", "Freight Invoices"),
    ("landed", "Landed Cost Vouchers"),
]
RECEIVABLE_SOURCE_CHOICES = [
    ("sales_order", "Sales Orders"),
    ("billing_run", "3PL Billing Runs"),
    ("return", "Return Credit Notes"),
]

#: The ``?group=`` vocabulary on the landed-cost variance report.
GROUP_CHOICES = [
    ("charge_type", "By Charge Type"),
    ("item", "By Item"),
    ("shipment", "By Shipment"),
]
DEFAULT_GROUP = "charge_type"

#: Purchase-order statuses that represent a live commitment to a vendor. ``draft`` and
#: ``pending_approval`` are not commitments yet; ``cancelled`` and ``closed`` no longer are.
COMMITTED_PO_STATUSES = ("approved", "sent", "acknowledged", "partially_received", "received")

#: Requisition status that is an APPROVED-but-not-yet-ordered commitment. ``converted`` is
#: deliberately EXCLUDED: a converted requisition has become a purchase order, and counting both
#: would double-count the same spend against the same budget. (``PurchaseRequisition``'s own
#: ``COMMITTED_STATUSES`` includes ``converted`` because ``budget_check()`` looks at requisitions
#: alone and never at the orders they became — a different question from this one.)
COMMITTED_PR_STATUSES = ("approved",)

#: Landed-cost voucher statuses whose ``actual_total`` is real incurred spend. A ``draft`` voucher is
#: an estimate nobody has agreed to; a ``cancelled`` one is not spend at all.
INCURRED_VOUCHER_STATUSES = ("allocated", "accrued", "reconciled")

#: The label a row with no ``core.OrgUnit`` carries. NEVER blank — a nameless row in a variance
#: report is one a reader silently attributes to the row above it.
UNASSIGNED_LABEL = "Unassigned"

_MONEY = DecimalField(max_digits=20, decimal_places=2)


# ============================================================================ shared guards
def _as_date(raw):
    """A ``YYYY-MM-DD`` GET value as a ``date``, or ``None``.

    Junk is SKIPPED, never raised on — the same L11 posture ``as_db_int`` takes for int filters, and
    a local copy of the ``ClientBillingRuns._as_date`` precedent (peer sub-modules do not import each
    other's private helpers).
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _as_choice(raw, choices):
    """A GET value that IS one of ``choices``' values, or ``""``.

    Checked against the vocabulary BEFORE it reaches ``.filter()`` rather than after: a status value
    that is merely wrong narrows to nothing (fine), but the guard also documents at the top of each
    view exactly which strings the page accepts.
    """
    raw = (raw or "").strip()
    return raw if raw in {value for value, _label in choices} else ""


def _grouped_sum(qs, key, column):
    """``{group value: Decimal}`` from ONE grouped query — ``SUM(column) GROUP BY key``.

    **``.order_by()`` IS LOAD-BEARING, not tidiness.** Django appends a queryset's ordering fields to
    the GROUP BY of a ``.values(...).annotate(...)``, so a model with a ``Meta.ordering`` silently
    groups by that column too. Every model this helper is pointed at has one —
    ``BudgetLine.Meta.ordering = ["gl_account__code"]``, ``PurchaseRequisitionLine`` and
    ``PurchaseOrderLine`` order by ``["id"]``, ``LandedCostVoucher`` by ``["-cost_date", "-id"]`` —
    and with ``id`` in the GROUP BY every single line becomes its own group, so the report renders
    one row per document instead of one per department, with every figure wrong. Clearing the
    ordering here means no caller can forget it.
    """
    rows = qs.order_by().values(key).annotate(s=Sum(column))
    return {row[key]: (row["s"] or ZERO) for row in rows}


def _bucket(buckets, key, label):
    """Fetch-or-create one accumulator in an insertion-ordered ``{key: row}`` map."""
    row = buckets.get(key)
    if row is None:
        row = {"key": key, "label": label,
               "estimated": ZERO, "actual": ZERO, "allocated": ZERO, "quantity": ZERO}
        buckets[key] = row
    return row


def _variance_pct(variance, base):
    """``variance / base * 100`` at 2dp, or ``None`` when there is no base to divide by.

    ``None``, never zero: "no budget set" and "exactly on budget" are different findings and the
    templates render them differently. A zero here would read as the second when it is the first.
    """
    base = base or ZERO
    if base <= ZERO:
        return None
    return q2(variance * 100 / base)


# ============================================================================ 4.18 Accounts Payable
def _payable_grn_rows(tenant, q, status):
    """4.1's three-way match, read as an AP exposure: what we received vs. what the vendor billed.

    ``prefetch_related`` on the lines (with ``select_related("po_line")`` INSIDE the prefetch) is what
    keeps ``received_value()`` — which walks every line's ``po_line.unit_price`` — from firing two
    queries per row. Cancelled receipts are excluded: they create no payable.
    """
    qs = (GoodsReceiptNote.objects.filter(tenant=tenant)
          .exclude(status="cancelled")
          .select_related("bill", "purchase_order", "purchase_order__vendor")
          .prefetch_related(Prefetch(
              "lines", queryset=GoodsReceiptLine.objects.select_related("po_line"))))
    if q:
        qs = qs.filter(Q(number__icontains=q) |
                       Q(purchase_order__number__icontains=q) |
                       Q(purchase_order__vendor__name__icontains=q) |
                       Q(bill__number__icontains=q))
    if status:
        qs = qs.filter(bill__status=status)

    batch = list(qs[:ROW_CAP + 1])
    rows = []
    for grn in batch[:ROW_CAP]:
        lines = list(grn.lines.all())
        amount = q2(grn.received_value(lines=lines))
        rows.append({
            "source": "grn",
            "source_label": "Goods Receipts",
            "document": "Goods Receipt",
            "number": grn.number,
            # `goodsreceipt_detail`, NOT `goodsreceiptnote_detail`: 4.1's route is named after the
            # page, not after the model class. A name that does not exist is a NoReverseMatch 500 on
            # the whole report, not a dead link on one row.
            "url": reverse("scm:goodsreceipt_detail", args=[grn.pk]),
            "party": grn.purchase_order.vendor.name if grn.purchase_order_id else "",
            "bill": grn.bill,
            "bill_number": grn.bill.number if grn.bill_id else "",
            "bill_status": grn.bill.status if grn.bill_id else "",
            "bill_status_label": grn.bill.get_status_display() if grn.bill_id else "",
            "amount": amount,
            # None, not zero: an unbilled receipt has no variance yet, and rendering that as 0.00
            # would put it in the "agrees with the vendor" bucket it has not reached.
            "variance": q2(grn.billed_value() - amount) if grn.bill_id else None,
            "match_status": grn.match_status,
            "match_status_label": grn.get_match_status_display(),
        })
    return rows, len(batch) > ROW_CAP


def _payable_freight_rows(tenant, q, status):
    """4.6's freight audit. ``carrier.name`` is a PROPERTY reading ``party.name``, so the chain
    ``carrier__party`` has to be select_related or every row costs two queries."""
    qs = (FreightInvoice.objects.filter(tenant=tenant)
          .exclude(approval_status="rejected")
          .select_related("bill", "carrier", "carrier__party"))
    if q:
        qs = qs.filter(Q(number__icontains=q) |
                       Q(carrier_invoice_number__icontains=q) |
                       Q(carrier__party__name__icontains=q) |
                       Q(bill__number__icontains=q))
    if status:
        qs = qs.filter(bill__status=status)

    batch = list(qs[:ROW_CAP + 1])
    rows = []
    for inv in batch[:ROW_CAP]:
        rows.append({
            "source": "freight",
            "source_label": "Freight Invoices",
            "document": "Freight Invoice",
            "number": inv.number,
            "url": reverse("scm:freightinvoice_detail", args=[inv.pk]),
            "party": inv.carrier.name if inv.carrier_id else "",
            "bill": inv.bill,
            "bill_number": inv.bill.number if inv.bill_id else "",
            "bill_status": inv.bill.status if inv.bill_id else "",
            "bill_status_label": inv.bill.get_status_display() if inv.bill_id else "",
            "amount": q2(inv.billed_amount or ZERO),
            # The freight audit's own billed-vs-contract variance, which already exists as a stored
            # derived column — not recomputed here into a second, drifting figure.
            "variance": q2(inv.variance_amount) if inv.contract_amount else None,
            "match_status": inv.match_status,
            "match_status_label": inv.get_match_status_display(),
        })
    return rows, len(batch) > ROW_CAP


def _payable_landed_rows(tenant, q, status):
    """4.18's own hand-off: the landed-cost voucher and the draft bill it raised."""
    qs = (LandedCostVoucher.objects.filter(tenant=tenant)
          .exclude(status="cancelled")
          .select_related("bill", "party", "goods_receipt"))
    if q:
        qs = qs.filter(Q(number__icontains=q) |
                       Q(party__name__icontains=q) |
                       Q(goods_receipt__number__icontains=q) |
                       Q(bill__number__icontains=q))
    if status:
        qs = qs.filter(bill__status=status)

    batch = list(qs[:ROW_CAP + 1])
    rows = []
    for voucher in batch[:ROW_CAP]:
        rows.append({
            "source": "landed",
            "source_label": "Landed Cost Vouchers",
            "document": "Landed Cost Voucher",
            "number": voucher.number,
            "url": reverse("scm:landedcostvoucher_detail", args=[voucher.pk]),
            "party": voucher.party.name if voucher.party_id else "",
            "bill": voucher.bill,
            "bill_number": voucher.bill.number if voucher.bill_id else "",
            "bill_status": voucher.bill.status if voucher.bill_id else "",
            "bill_status_label": voucher.bill.get_status_display() if voucher.bill_id else "",
            "amount": q2(voucher.actual_total or ZERO),
            "variance": q2(voucher.variance_amount) if voucher.estimated_total else None,
            # The voucher's OWN lifecycle status is its reconciliation state — it has no separate
            # match_status column, and inventing one here would be a second source of truth for it.
            "match_status": voucher.status,
            "match_status_label": voucher.get_status_display(),
        })
    return rows, len(batch) > ROW_CAP


@login_required
def finance_payables(request):
    """Every SCM document that owes (or has drafted) an ``accounting.Bill``, in one list.

    THE UNION IS OF POINTERS, NOT COPIES: ``GoodsReceiptNote.bill``, ``FreightInvoice.bill`` and
    ``LandedCostVoucher.bill`` all FK the same ``accounting.Bill``. SCM holds no payable of its own
    and this page invents none — an unbilled row is reported as unbilled (``bill`` is ``None`` and
    ``variance`` is ``None``), never as a payable we made up.

    ``row.party`` is the counterparty's NAME as a string rather than a ``core.Party`` instance: the
    three sources reach it down three different chains (``purchase_order.vendor``,
    ``carrier.party``, ``voucher.party``) and resolving each to a string here is what lets the
    template render one column without walking a relation per row.

    Context (frozen): ``rows``, ``totals``, ``source_choices``, ``status_choices``, ``row_cap``,
    ``truncated``.
    """
    q = (request.GET.get("q") or "").strip()
    source = _as_choice(request.GET.get("source"), PAYABLE_SOURCE_CHOICES)
    status = _as_choice(request.GET.get("status"), Bill.STATUS_CHOICES)

    rows, truncated = [], False
    # A tenant-less user (the superuser) sees an empty report, not another workspace's payables.
    if request.tenant is not None:
        builders = (
            ("grn", _payable_grn_rows),
            ("freight", _payable_freight_rows),
            ("landed", _payable_landed_rows),
        )
        for key, builder in builders:
            if source and source != key:
                continue
            found, cut = builder(request.tenant, q, status)
            rows.extend(found)
            truncated = truncated or cut

    # Biggest exposure first — the order somebody checking an AP run reads in. The cap is applied
    # PER SOURCE before this sort (each source is queried in its own Meta order), so `truncated`
    # means "one of the three sources had more than the cap", which is what the template says.
    rows.sort(key=lambda r: (-(r["amount"] or ZERO), r["number"] or ""))
    if len(rows) > ROW_CAP:
        rows = rows[:ROW_CAP]
        truncated = True

    amount = q2(sum((r["amount"] or ZERO for r in rows), ZERO))
    billed = q2(sum((r["amount"] or ZERO for r in rows if r["bill"] is not None), ZERO))
    return render(request, "scm/finance/payables.html", {
        "rows": rows,
        "totals": {
            "count": len(rows),
            "amount": amount,
            "billed": billed,
            "unbilled": q2(amount - billed),
        },
        "source_choices": PAYABLE_SOURCE_CHOICES,
        "status_choices": Bill.STATUS_CHOICES,
        "row_cap": ROW_CAP,
        "truncated": truncated,
    })


# ========================================================================= 4.18 Accounts Receivable
def _receivable_salesorder_rows(tenant, q, status):
    qs = (SalesOrder.objects.filter(tenant=tenant)
          .exclude(status="cancelled")
          .select_related("customer", "invoice"))
    if q:
        qs = qs.filter(Q(number__icontains=q) |
                       Q(customer__name__icontains=q) |
                       Q(invoice__number__icontains=q))
    if status:
        qs = qs.filter(invoice__status=status)

    batch = list(qs[:ROW_CAP + 1])
    rows = [_receivable_row("sales_order", "Sales Orders", "Sales Order",
                            order.number, reverse("scm:salesorder_detail", args=[order.pk]),
                            order.customer.name if order.customer_id else "",
                            order.invoice, order.total)
            for order in batch[:ROW_CAP]]
    return rows, len(batch) > ROW_CAP


def _receivable_billingrun_rows(tenant, q, status):
    qs = (ClientBillingRun.objects.filter(tenant=tenant)
          .exclude(status="void")
          .select_related("client", "client__party", "invoice"))
    if q:
        qs = qs.filter(Q(number__icontains=q) |
                       Q(client__code__icontains=q) |
                       Q(client__party__name__icontains=q) |
                       Q(invoice__number__icontains=q))
    if status:
        qs = qs.filter(invoice__status=status)

    batch = list(qs[:ROW_CAP + 1])
    rows = [_receivable_row("billing_run", "3PL Billing Runs", "Billing Run",
                            run.number, reverse("scm:clientbillingrun_detail", args=[run.pk]),
                            run.client.party.name if run.client_id and run.client.party_id else "",
                            run.invoice, run.total)
            for run in batch[:ROW_CAP]]
    return rows, len(batch) > ROW_CAP


def _receivable_return_rows(tenant, q, status):
    """4.10's credit notes. A credit note is a NEGATIVE receivable and is reported as the signed
    figure the model already stores — flipping the sign here would make it look like revenue."""
    qs = (ReturnAuthorization.objects.filter(tenant=tenant)
          .exclude(status__in=("cancelled", "rejected"))
          .select_related("customer", "credit_note"))
    if q:
        qs = qs.filter(Q(number__icontains=q) |
                       Q(customer__name__icontains=q) |
                       Q(credit_note__number__icontains=q))
    if status:
        qs = qs.filter(credit_note__status=status)

    batch = list(qs[:ROW_CAP + 1])
    rows = [_receivable_row("return", "Return Credit Notes", "Return Authorization",
                            rma.number, reverse("scm:returnauthorization_detail", args=[rma.pk]),
                            rma.customer.name if rma.customer_id else "",
                            rma.credit_note, rma.credit_total)
            for rma in batch[:ROW_CAP]]
    return rows, len(batch) > ROW_CAP


def _receivable_row(source, source_label, document, number, url, party, invoice, total):
    """One receivable row. ``balance`` is filled in later by :func:`_invoice_balances` — resolving it
    here would cost one aggregate query per row (``Invoice.balance_due()`` walks its allocations)."""
    return {
        "source": source,
        "source_label": source_label,
        "document": document,
        "number": number,
        "url": url,
        "party": party,
        "invoice": invoice,
        "invoice_number": invoice.number if invoice is not None else "",
        "invoice_status": invoice.status if invoice is not None else "",
        "invoice_status_label": invoice.get_status_display() if invoice is not None else "",
        "total": q2(total or ZERO),
        "balance": None,
    }


def _invoice_balances(tenant, invoice_ids):
    """``{invoice pk: outstanding Decimal}`` in ONE grouped query.

    ``Invoice.balance_due()`` is correct but issues its own aggregate over the payment allocations,
    so calling it per row is 500 queries on a full page. This annotates the same figure — total minus
    CONFIRMED allocations, because a voided payment must not keep an invoice looking settled — for
    every invoice on the page at once.
    """
    if not invoice_ids:
        return {}
    rows = (Invoice.objects.filter(tenant=tenant, pk__in=invoice_ids)
            .annotate(paid=Coalesce(
                Sum("allocations__allocated_amount",
                    filter=Q(allocations__payment__status="confirmed")),
                Value(ZERO), output_field=_MONEY))
            .values_list("pk", "total", "paid"))
    return {pk: q2((total or ZERO) - (paid or ZERO)) for pk, total, paid in rows}


@login_required
def finance_receivables(request):
    """Every SCM document that raised (or still owes) an ``accounting.Invoice``, in one list.

    Same posture as :func:`finance_payables`: the three sources — ``SalesOrder.invoice``,
    ``ClientBillingRun.invoice`` and ``ReturnAuthorization.credit_note`` — are POINTERS at
    ``accounting.Invoice``. SCM keeps no AR ledger, and an uninvoiced row is reported as uninvoiced
    (``invoice`` is ``None``, ``balance`` is ``None``) rather than as money we are owed.

    Context (frozen): ``rows``, ``totals``, ``source_choices``, ``status_choices``, ``row_cap``,
    ``truncated``.
    """
    q = (request.GET.get("q") or "").strip()
    source = _as_choice(request.GET.get("source"), RECEIVABLE_SOURCE_CHOICES)
    status = _as_choice(request.GET.get("status"), Invoice.STATUS_CHOICES)

    rows, truncated = [], False
    if request.tenant is not None:
        builders = (
            ("sales_order", _receivable_salesorder_rows),
            ("billing_run", _receivable_billingrun_rows),
            ("return", _receivable_return_rows),
        )
        for key, builder in builders:
            if source and source != key:
                continue
            found, cut = builder(request.tenant, q, status)
            rows.extend(found)
            truncated = truncated or cut

    rows.sort(key=lambda r: (-(r["total"] or ZERO), r["number"] or ""))
    if len(rows) > ROW_CAP:
        rows = rows[:ROW_CAP]
        truncated = True

    if request.tenant is not None:
        balances = _invoice_balances(
            request.tenant, [r["invoice"].pk for r in rows if r["invoice"] is not None])
        for row in rows:
            if row["invoice"] is not None:
                row["balance"] = balances.get(row["invoice"].pk, q2(row["invoice"].total or ZERO))

    total = q2(sum((r["total"] or ZERO for r in rows), ZERO))
    balance = q2(sum((r["balance"] or ZERO for r in rows), ZERO))
    uninvoiced = q2(sum((r["total"] or ZERO for r in rows if r["invoice"] is None), ZERO))
    return render(request, "scm/finance/receivables.html", {
        "rows": rows,
        "totals": {
            "count": len(rows),
            "total": total,
            "balance": balance,
            "uninvoiced": uninvoiced,
        },
        "source_choices": RECEIVABLE_SOURCE_CHOICES,
        "status_choices": Invoice.STATUS_CHOICES,
        "row_cap": ROW_CAP,
        "truncated": truncated,
    })


# ============================================================================== 4.18 Budget variance
def _budget_variance_rows(tenant, budget, period):
    """``(rows, truncated)`` — budgeted vs. committed vs. incurred, one row per ``core.OrgUnit``.

    ``accounting.BudgetLine.org_unit`` IS the supply-chain department dimension (2.13 owns it, 4.1's
    ``PurchaseRequisition.budget_check()`` already reads it); nothing new is declared here.

    FOUR GROUPED QUERIES, NEVER A PER-ROW ONE, and each reaches the org unit down the chain that
    genuinely exists on disk:

    * **budgeted** — ``BudgetLine.org_unit`` directly.
    * **committed** — ``PurchaseRequisitionLine`` through ``requisition.org_unit``, plus
      ``PurchaseOrderLine`` through ``purchase_order.requisition.org_unit``. Requisitions count only
      while ``approved``: once ``converted`` they ARE the purchase order, and counting both would
      double-count one commitment (see :data:`COMMITTED_PR_STATUSES`).
    * **incurred** — ``LandedCostVoucher.actual_total`` through
      ``goods_receipt.purchase_order.requisition.org_unit``, plus ``FreightInvoice.billed_amount``.

    THE ONE HONEST GAP, stated rather than papered over: **``FreightInvoice`` carries no org-unit and
    no GL-account dimension anywhere in this repo** (neither the header nor ``FreightInvoiceLine``
    has one), so approved freight spend lands in the ``Unassigned`` row. And when a specific budget
    or period IS selected, freight is EXCLUDED altogether rather than dumped into that budget's
    variance — attributing spend we cannot attribute is worse than reporting it separately. The same
    goes for any voucher or order whose chain to an org unit is broken by a ``SET_NULL``: it lands in
    ``Unassigned``, which is why that row always renders with a name and never a blank.
    """
    scoped = budget is not None or period is not None

    budget_lines = BudgetLine.objects.filter(tenant=tenant)
    if budget is not None:
        budget_lines = budget_lines.filter(budget=budget)
    if period is not None:
        budget_lines = budget_lines.filter(budget__fiscal_period=period)
    budgeted = _grouped_sum(budget_lines, "org_unit", "amount")

    pr_lines = PurchaseRequisitionLine.objects.filter(
        requisition__tenant=tenant, requisition__status__in=COMMITTED_PR_STATUSES)
    po_lines = PurchaseOrderLine.objects.filter(
        purchase_order__tenant=tenant, purchase_order__status__in=COMMITTED_PO_STATUSES)
    vouchers = LandedCostVoucher.objects.filter(
        tenant=tenant, status__in=INCURRED_VOUCHER_STATUSES)
    if budget is not None:
        pr_lines = pr_lines.filter(requisition__budget=budget)
        po_lines = po_lines.filter(purchase_order__requisition__budget=budget)
        vouchers = vouchers.filter(goods_receipt__purchase_order__requisition__budget=budget)
    if period is not None:
        pr_lines = pr_lines.filter(requisition__budget__fiscal_period=period)
        po_lines = po_lines.filter(purchase_order__requisition__budget__fiscal_period=period)
        vouchers = vouchers.filter(
            goods_receipt__purchase_order__requisition__budget__fiscal_period=period)

    committed_pr = _grouped_sum(pr_lines, "requisition__org_unit", "line_total")
    committed_po = _grouped_sum(
        po_lines, "purchase_order__requisition__org_unit", "line_total")
    incurred_landed = _grouped_sum(
        vouchers, "goods_receipt__purchase_order__requisition__org_unit", "actual_total")

    incurred_freight = ZERO
    if not scoped:
        incurred_freight = (FreightInvoice.objects
                            .filter(tenant=tenant, approval_status="approved")
                            .aggregate(s=Sum("billed_amount"))["s"] or ZERO)

    keys = (set(budgeted) | set(committed_pr) | set(committed_po) | set(incurred_landed))
    if incurred_freight:
        keys.add(None)
    if not keys:
        return [], False

    # ONE query for the names — never `OrgUnit.objects.get(pk=...)` inside the row loop.
    units = {unit.pk: unit for unit in
             OrgUnit.objects.filter(tenant=tenant,
                                    pk__in=[k for k in keys if k is not None])}

    rows = []
    for key in keys:
        unit = units.get(key) if key is not None else None
        # A budget line pointing at another workspace's org unit cannot happen through the UI, but a
        # key with no row in `units` would otherwise render a blank name. It falls to Unassigned.
        budgeted_amount = q2(budgeted.get(key, ZERO))
        committed = q2(committed_pr.get(key, ZERO) + committed_po.get(key, ZERO))
        incurred = incurred_landed.get(key, ZERO)
        if key is None:
            incurred += incurred_freight
        incurred = q2(incurred)
        remaining = q2(budgeted_amount - committed - incurred)
        rows.append({
            "org_unit": unit,
            "org_unit_name": unit.name if unit is not None else UNASSIGNED_LABEL,
            "budgeted": budgeted_amount,
            "committed": committed,
            "incurred": incurred,
            "remaining": remaining,
            "variance_pct": _variance_pct(remaining, budgeted_amount),
            "over_budget": remaining < ZERO,
        })

    # Biggest budget first, then the spend that has no budget at all (which sorts to the bottom on
    # `budgeted` and is exactly where a reader looks for it).
    rows.sort(key=lambda r: (-(r["budgeted"] or ZERO), r["org_unit_name"]))
    truncated = len(rows) > ROW_CAP
    return rows[:ROW_CAP], truncated


@login_required
def finance_budget_variance(request):
    """Supply-chain spend against ``accounting.Budget``, by department.

    A VIEW-TIME comparison, exactly like 4.1's ``PurchaseRequisition.budget_check()`` and for the
    same reason: the budget belongs to Module 2, and a stored encumbrance column here would be a
    second source of truth that drifts the first time accounting revised a budget. Nothing on this
    page is written anywhere.

    Context (frozen): ``rows``, ``totals``, ``budgets``, ``fiscal_periods``, ``selected_budget``,
    ``selected_period``, ``row_cap``, ``truncated``.
    """
    # L11: `?budget=abc`, `?budget=²` and a 21-digit value all become None and select nothing,
    # rather than raising out of .filter() on a URL anybody can type.
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
        # Resolved THROUGH the tenant-scoped queryset, so a pk belonging to another workspace
        # selects nothing instead of narrowing this report by a stranger's budget.
        if budget_id is not None:
            selected_budget = budgets.filter(pk=budget_id).first()
        if period_id is not None:
            selected_period = fiscal_periods.filter(pk=period_id).first()
        rows, truncated = _budget_variance_rows(request.tenant, selected_budget, selected_period)

    return render(request, "scm/finance/budget_variance.html", {
        "rows": rows,
        "totals": {
            "budgeted": q2(sum((r["budgeted"] for r in rows), ZERO)),
            "committed": q2(sum((r["committed"] for r in rows), ZERO)),
            "incurred": q2(sum((r["incurred"] for r in rows), ZERO)),
            "remaining": q2(sum((r["remaining"] for r in rows), ZERO)),
        },
        "budgets": budgets,
        "fiscal_periods": fiscal_periods,
        "selected_budget": selected_budget,
        "selected_period": selected_period,
        "row_cap": ROW_CAP,
        "truncated": truncated,
    })


# ========================================================================= 4.18 Landed-cost variance
def _landed_variance_rows(tenant, group, charge_type, date_from, date_to):
    """``(rows, truncated)`` — estimated vs. actual vs. allocated landed cost, grouped three ways.

    TWO capped scans, then all the arithmetic in Python (``q2``/``q4``), because the three groupings
    need different halves of the same join:

    * ``charge_type`` and ``shipment`` group the CHARGE rows (which carry the real
      ``estimated_amount`` / ``actual_amount``) and fold the allocation rows in for the allocated
      total and the quantity. A charge that has not been allocated yet still appears, with an
      allocated of zero — which is the finding, not a gap.
    * ``item`` can only group the ALLOCATION rows, since an item is reached through the allocation.
      Estimated and actual are PRO-RATED onto each item by its share of its charge's allocated
      amount, so the column means "this item's share of what that charge estimated/actually cost"
      rather than a repeated charge-level figure. A charge with no allocations contributes no item
      row at all — it has not touched an item yet — so the totals on the item grouping are the
      allocated population, and the template's ``truncated``/empty-state prose is what says so.
    """
    charges = (LandedCostCharge.objects
               .filter(voucher__tenant=tenant)
               .exclude(voucher__status="cancelled"))
    allocations = (LandedCostAllocation.objects
                   .filter(tenant=tenant)
                   .exclude(voucher__status="cancelled"))
    if charge_type:
        charges = charges.filter(charge_type=charge_type)
        allocations = allocations.filter(charge__charge_type=charge_type)
    if date_from:
        charges = charges.filter(voucher__cost_date__gte=date_from)
        allocations = allocations.filter(voucher__cost_date__gte=date_from)
    if date_to:
        charges = charges.filter(voucher__cost_date__lte=date_to)
        allocations = allocations.filter(voucher__cost_date__lte=date_to)

    charge_rows = list(charges.order_by("id").values(
        "id", "charge_type", "estimated_amount", "actual_amount",
        "voucher__shipment", "voucher__shipment__number")[:SCAN_CAP + 1])
    alloc_rows = list(allocations.order_by("id").values(
        "charge", "charge__charge_type", "allocated_amount", "quantity",
        "item", "item__sku", "item__name",
        "voucher__shipment", "voucher__shipment__number")[:SCAN_CAP + 1])
    truncated = len(charge_rows) > SCAN_CAP or len(alloc_rows) > SCAN_CAP
    charge_rows, alloc_rows = charge_rows[:SCAN_CAP], alloc_rows[:SCAN_CAP]

    # Each charge's TOTAL allocated amount — the denominator the item pro-rate divides by.
    allocated_by_charge = {}
    for alloc in alloc_rows:
        key = alloc["charge"]
        allocated_by_charge[key] = allocated_by_charge.get(key, ZERO) + (alloc["allocated_amount"] or ZERO)

    charge_type_labels = dict(LandedCostCharge.CHARGE_TYPE_CHOICES)
    buckets = {}

    if group == "item":
        charge_amounts = {row["id"]: ((row["estimated_amount"] or ZERO), (row["actual_amount"] or ZERO))
                          for row in charge_rows}
        for alloc in alloc_rows:
            sku, name = alloc["item__sku"], alloc["item__name"]
            label = f"{sku} · {name}" if sku and name else (sku or name or f"Item #{alloc['item']}")
            row = _bucket(buckets, alloc["item"], label)
            allocated = alloc["allocated_amount"] or ZERO
            row["allocated"] += allocated
            row["quantity"] += alloc["quantity"] or ZERO
            estimated, actual = charge_amounts.get(alloc["charge"], (ZERO, ZERO))
            denominator = allocated_by_charge.get(alloc["charge"]) or ZERO
            if denominator > ZERO:
                share = allocated / denominator
                row["estimated"] += estimated * share
                row["actual"] += actual * share
    else:
        if group == "shipment":
            def key_of(record):
                return record["voucher__shipment"]

            def label_of(record):
                return record["voucher__shipment__number"] or "No shipment"
        else:  # charge_type — the default, and what any junk ?group= falls back to
            def key_of(record):
                return record.get("charge_type") or record.get("charge__charge_type")

            def label_of(record):
                value = key_of(record)
                return charge_type_labels.get(value, (value or "").replace("_", " ").title())

        for record in charge_rows:
            row = _bucket(buckets, key_of(record), label_of(record))
            row["estimated"] += record["estimated_amount"] or ZERO
            row["actual"] += record["actual_amount"] or ZERO
        for alloc in alloc_rows:
            row = _bucket(buckets, key_of(alloc), label_of(alloc))
            row["allocated"] += alloc["allocated_amount"] or ZERO
            row["quantity"] += alloc["quantity"] or ZERO

    rows = []
    for row in buckets.values():
        estimated, actual = q2(row["estimated"]), q2(row["actual"])
        quantity, allocated = q4(row["quantity"]), q2(row["allocated"])
        variance = q2(actual - estimated)
        rows.append({
            "key": row["key"],
            "label": row["label"],
            "estimated": estimated,
            "actual": actual,
            "variance": variance,
            "allocated": allocated,
            "variance_pct": _variance_pct(variance, estimated),
            "quantity": quantity,
            # None, not zero: an unallocated group has no per-unit uplift to show, and 0.0000 would
            # read as "this cost nothing to land".
            "uplift_per_unit": q4(allocated / quantity) if quantity > ZERO else None,
        })

    rows.sort(key=lambda r: (-(r["actual"] or ZERO), r["label"]))
    if len(rows) > ROW_CAP:
        rows = rows[:ROW_CAP]
        truncated = True
    return rows, truncated


@login_required
def landed_cost_variance(request):
    """What landed cost was estimated, what it actually was, and where it was capitalised.

    The estimate-vs-actual column is the whole point of the report: a landed-cost accrual that is
    never revisited is how an importer's margin quietly drifts. ``allocated`` is what actually
    reached inventory through ``LandedCostVoucher.allocate()``; a group whose ``actual`` exceeds its
    ``allocated`` has cost that has not been capitalised yet.

    Context (frozen): ``rows``, ``totals``, ``group``, ``group_choices``, ``charge_type_choices``,
    ``date_from``, ``date_to``, ``row_cap``, ``truncated``.
    """
    # Any junk ?group= falls back to the default rather than 500ing or rendering an empty page.
    group = _as_choice(request.GET.get("group"), GROUP_CHOICES) or DEFAULT_GROUP
    charge_type = _as_choice(request.GET.get("charge_type"), LandedCostCharge.CHARGE_TYPE_CHOICES)
    date_from = _as_date(request.GET.get("date_from"))
    date_to = _as_date(request.GET.get("date_to"))

    rows, truncated = [], False
    if request.tenant is not None:
        rows, truncated = _landed_variance_rows(
            request.tenant, group, charge_type, date_from, date_to)

    return render(request, "scm/finance/landed_cost_variance.html", {
        "rows": rows,
        "totals": {
            "estimated": q2(sum((r["estimated"] for r in rows), ZERO)),
            "actual": q2(sum((r["actual"] for r in rows), ZERO)),
            "variance": q2(sum((r["variance"] for r in rows), ZERO)),
            "allocated": q2(sum((r["allocated"] for r in rows), ZERO)),
        },
        "group": group,
        "group_choices": GROUP_CHOICES,
        "charge_type_choices": LandedCostCharge.CHARGE_TYPE_CHOICES,
        # Echoed back as `date` objects so the template can render them straight into the two
        # <input type="date"> values; a junk value arrives here as None and the input renders empty.
        "date_from": date_from,
        "date_to": date_to,
        "row_cap": ROW_CAP,
        "truncated": truncated,
    })
