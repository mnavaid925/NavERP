"""Procurement 6.14 Spend Analytics & Reporting - the compute layer.

Every figure the 6.14 pages render is an aggregate over rows that belong to somebody else. This
module is where that arithmetic lives, ONCE, so the dashboard, the category page, the export, the
classification workbench, the maverick board and the saved report builder can never hold two
answers to "what is spend?".

**Where the numbers come from.**

* recognised (invoiced) spend  -> ``procurement.SupplierInvoiceLine`` (6.13 owns it)
* committed (PO) spend         -> ``scm.PurchaseOrderLine`` (SCM 4.1 owns it)
* the category axis            -> ``scm.ItemCategory`` via ``item.category`` passthrough, then
  ``procurement.SpendClassificationRule``, then ``(Unclassified)``
* the maverick rate            -> ``procurement.MaverickSpendFinding``

**Import direction is one-way and must stay that way**: ``analytics`` imports ``models``; a model
NEVER imports ``analytics``. The two population definitions (``RECOGNISED_INVOICE_STATUSES`` /
``SPEND_PO_STATUSES``) and the two line windows are therefore declared in
``models/SpendAnalyticsReporting/SpendClassificationRules.py`` and re-exported from here rather
than the other way round - a model-level import of this module would invert the direction and
cycle at app-registry load.

**No money is written and no ledger is touched (L29).** Nothing in this module saves a row. 6.14
posts no ``accounting.Bill``, no ``JournalEntry``, no ``Budget`` and no ``Payment``.

**Money is summed AT FACE VALUE PER CURRENCY.** There is no FX rate table anywhere in this
repository, so a window holding more than one currency sets ``mixed_currency=True`` and the caller
renders ``currency_split``'s rows instead of one bogus total. No rate is ever invented.

**The classification engine is a set of explicit, auditable rules.** It is not, and must never be
labelled, "AI" or "ML"; ``ENGINE_NOTE`` is the wording every page prints.

This module was assembled by the Integrate phase from the compute layer the 6.14 build lane wrote
inline in ``views/SpendAnalyticsReporting/SpendDashboards.py`` (that lane owns no app-root file,
so it could not create this one). The block below is that section verbatim; ``csv_safe`` was the
one name lifted out of it instead, into ``views/_helpers.py``, because it is a view-layer concern
shared with 6.1.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.core.models import OrgUnit
# Entity MODULES, not the package: ``models/__init__`` imports these same modules, so going
# through the package here could re-enter a partially-initialised module at URLconf import time.
from apps.procurement.models.SpendAnalyticsReporting.MaverickFindings import MaverickSpendFinding
from apps.procurement.models.SpendAnalyticsReporting.SpendClassificationRules import (
    RECOGNISED_INVOICE_STATUSES,  # noqa: F401  (re-exported: part of the analytics vocabulary)
    SPEND_PO_STATUSES,  # noqa: F401
    SpendClassificationRule,
    committed_line_window,
    invoiced_line_window,
    money,
)
from apps.procurement.models.SpendAnalyticsReporting.SpendReports import (
    BASIS_CHOICES,
    DATE_RANGE_CHOICES,
    DIMENSION_CHOICES,
    MEASURE_CHOICES,
)

ZERO = Decimal("0")

# COMPUTE LAYER  —  lift this whole section verbatim into apps/procurement/analytics.py
# =================================================================================================

#: Contract statuses that count as cover for on/off-contract spend. Copied from
#: ``apps/scm/analytics.py`` so 4.11 and 6.14 can never disagree; ``renewed`` is excluded because
#: the successor contract is its own row and is the one that should be covering the order.
COVERING_CONTRACT_STATUSES = ("active", "expiring")

#: How many rows a grouped breakdown will render on a page. A bar chart with 200 bars is not a
#: chart; anything past the cut is folded into the totals but not drawn.
MAX_GROUP_ROWS = 25

#: Hard ceiling on a CSV download. Stated on the export page and in the filename when it bites.
MAX_EXPORT_ROWS = 5000

#: The department bucket for spend whose 3-hop chain resolves to NULL — every PO-less invoice.
#: Rendered explicitly; never dropped.
UNASSIGNED_LABEL = "(unassigned)"

#: The category bucket for spend no ``item.category`` passthrough and no rule could classify.
UNCLASSIFIED_LABEL = "(Unclassified)"

#: Ceiling on the Python-side classification pass. The category axis cannot be a pure DB GROUP BY:
#: the passthrough half can (``item__category``), but the remainder has to be walked line by line
#: against the rule list. That walk is bounded here; whatever is left beyond the cap is added to
#: ``(Unclassified)`` by VALUE (an exact aggregate, not an estimate), so the totals stay correct
#: even when the detail is truncated. NOT in the frozen contract — a lane addition, recorded here.
MAX_CLASSIFY_LINES = 5000

#: Ceiling on the per-item price-spread scan behind Category Spend Analysis. Same reasoning.
ITEM_SCAN_CAP = 500

#: The largest date a custom window may name. ``date.max`` is 9999-12-31 and ``SpendReport.clean()``
#: explicitly permits it, but ``range_bounds`` pushes an inclusive ``date_to`` out by one day to get
#: its exclusive stop — and ``date(9999, 12, 31) + timedelta(days=1)`` raises ``OverflowError``.
#: Clamping the INPUT (rather than catching the overflow) keeps the +1 total for every caller.
_MAX_BOUND = date(9999, 12, 30)

#: Maverick-rate bands, printed on the page next to the number so the colour means something.
MAVERICK_BAND_LOW = Decimal("10")
MAVERICK_BAND_HIGH = Decimal("20")

_BASIS_KEYS = {key for key, _label in BASIS_CHOICES}
_RANGE_KEYS = {key for key, _label in DATE_RANGE_CHOICES}
_DIMENSION_KEYS = {key for key, _label in DIMENSION_CHOICES}

DEFAULT_BASIS = "invoiced"
DEFAULT_RANGE = "last_90"
DEFAULT_DIMENSION = "supplier"

#: Printed on every page that renders a department breakdown. One constant, so the three pages
#: cannot explain the same caveat three different ways.
DEPARTMENT_CAVEAT = (
    "There is no department column on a supplier invoice. The department axis is derived from the "
    "purchase order behind the spend — the requisition's cost centre, falling back to the order's "
    "ship-to. Spend with no purchase order (PO-less and service invoices) therefore has no "
    f"department and is shown as {UNASSIGNED_LABEL}, never dropped."
)

#: Printed on Category Spend Analysis whenever the committed basis is selected.
COMMITTED_CATEGORY_NOTE = (
    "On the committed (PO) basis the category axis is resolved by classification rules only: a "
    "purchase order line records a description, an SKU hint and a GL account, but no item, so "
    "there is no item category to read through. Lines no rule claims are shown as "
    f"{UNCLASSIFIED_LABEL}."
)

#: Printed under the per-item price-spread table.
ITEM_FALLBACK_NOTE = (
    "Items are grouped by the stock item where the line carries one, and otherwise by its SKU hint "
    "or its description — which is what a line keyed from a paper invoice has. Two spellings of "
    "the same part therefore read as two items until the line is coded to an item."
)

#: VERBATIM on the export page. There is no BI connector; never claim one in a label.
BI_NOTE = "CSV download today; a live BI / PowerBI feed is not implemented"

#: How the rules engine describes itself. The rules are explicit and auditable — this sub-module
#: ships no machine learning, and no label anywhere may imply that it does.
ENGINE_NOTE = (
    "Spend is classified by explicit, ordered rules you can read and change: the item's own "
    "category first, then the first matching rule by priority, and otherwise "
    f"{UNCLASSIFIED_LABEL}. Every figure can be traced back to the rule that produced it."
)


# -- display helpers -------------------------------------------------------------------------

def _money(value):
    """A money figure as a display string. Face value — no currency conversion happens anywhere."""
    return "{:,.2f}".format(float(value or 0))


def _num(value):
    return "{:,}".format(int(value or 0))


def _pct(value):
    return "{:.1f}%".format(float(value or 0))


def _share(part, whole):
    """``part`` as a percentage of ``whole``, 1dp, and 0 when the denominator is zero/negative.

    Credit memos are already signed negative on ``SupplierInvoiceLine``, so a window CAN net to
    zero or below; dividing by it would raise, and reporting a share of a negative total would be
    meaningless rather than merely wrong.
    """
    whole = Decimal(whole or 0)
    if whole <= 0:
        return ZERO
    return (Decimal(part or 0) / whole * Decimal("100")).quantize(Decimal("0.1"))


def _scalar(value, display, *, max_value=None):
    """The pinned scalar result shape — ``{kind, value, display, max, pct}``.

    Mirrors ``apps/crm/analytics.py``'s widget contract so a template that renders a CRM KPI tile
    renders one of these unchanged. ``value`` may be ``None`` (meaning "not computable on this
    basis"), in which case ``pct`` is 0 and the display string says so.
    """
    ceiling = Decimal(max_value) if max_value is not None else Decimal(value or 0)
    pct = 0
    if value is not None and ceiling > 0:
        pct = int(min(Decimal("100"), Decimal(value) / ceiling * Decimal("100")))
    return {
        "kind": "scalar",
        "value": value,
        "display": display,
        "max": ceiling,
        "pct": pct,
    }


def _series(labels, data):
    """The pinned series result shape — ``{kind, labels, data}``."""
    return {"kind": "series", "labels": list(labels), "data": list(data)}


def _table(columns, rows):
    """The pinned table result shape — ``{kind, columns, rows}``."""
    return {"kind": "table", "columns": list(columns), "rows": list(rows)}


# -- windows ------------------------------------------------------------------------------------

def range_bounds(key, date_from=None, date_to=None):
    """A ``DATE_RANGE_CHOICES`` key as ``(start, end)`` dates, ``end`` EXCLUSIVE.

    Built on ``timezone.localdate()`` rather than ``date.today()`` (L16) so the window follows the
    workspace's timezone, not the server's. ``end`` is TOMORROW, so today's documents are inside
    the window rather than permanently just missing it — the single most confusing thing a spend
    report can do.

    ``custom`` takes the caller's two dates; ``date_to`` is inclusive to the user (they typed a
    day, not a boundary) and is therefore pushed out by one day here. A reversed or half-filled
    custom range degrades to the 90-day default rather than raising: these come off a query string.
    """
    today = timezone.localdate()
    end = today + timedelta(days=1)
    if key == "last_30":
        return end - timedelta(days=30), end
    if key == "last_90":
        return end - timedelta(days=90), end
    if key == "quarter":
        return date(today.year, 3 * ((today.month - 1) // 3) + 1, 1), end
    if key == "year":
        return date(today.year, 1, 1), end
    if key == "all":
        # A floor rather than None: every caller does ``>= start``, and a sentinel keeps the two
        # branches identical instead of sprinkling ``if start is not None`` through the cube.
        return date(1900, 1, 1), end
    if key == "custom" and date_from is not None:
        # Clamp BEFORE the +1. Both dates come off a query string or off a saved report whose
        # own clean() permits date(9999, 12, 31), and adding a day to date.max raises
        # OverflowError — a 500 on the dashboard, the category page, the export and the CSV.
        date_from = min(date_from, _MAX_BOUND)
        stop = (min(date_to, _MAX_BOUND) + timedelta(days=1)) if date_to is not None else end
        if stop <= date_from:
            stop = date_from + timedelta(days=1)
        return date_from, stop
    return end - timedelta(days=90), end


def invoiced_lines(tenant, start, end):
    """Recognised invoice lines for one tenant inside ``[start, end)``.

    Delegates to the model-layer window so this and ``SpendClassificationRule.preview()`` can never
    describe different populations. Credit memos are ALREADY signed negative on
    ``SupplierInvoiceLine``, so a plain ``Sum("line_total")`` nets — nothing here special-cases
    them, and nothing downstream should either.
    """
    return invoiced_line_window(tenant, start, end)


def committed_lines(tenant, start, end):
    """Committed (PO) lines for one tenant inside ``[start, end)``.

    ``PurchaseOrder.order_date`` is NULLABLE, so the model-layer window takes the range over
    ``Coalesce(order_date, TruncDate(created_at))`` and annotates it as ``doc_date``. Dropping the
    un-stamped orders instead would silently shrink committed spend.
    """
    return committed_line_window(tenant, start, end)


def basis_lines(tenant, basis, start, end):
    """The line window for whichever basis is selected."""
    return (invoiced_lines(tenant, start, end) if basis == "invoiced"
            else committed_lines(tenant, start, end))


# -- axis plumbing --------------------------------------------------------------------------

def _order_prefix(basis):
    """The lookup prefix that reaches ``scm.PurchaseOrder`` from a line of this basis."""
    return "invoice__purchase_order" if basis == "invoiced" else "purchase_order"


def _department_expression(basis):
    """The department axis as ONE expression: the requisition's cost centre, else the ship-to.

    ``Coalesce`` over two FK names resolves to their id columns, which is exactly the grouping key
    we want. NULL survives as NULL — that is the ``(unassigned)`` bucket, and it is rendered.
    """
    prefix = _order_prefix(basis)
    return Coalesce(f"{prefix}__requisition__org_unit", f"{prefix}__ship_to")


def _date_field(basis):
    """The column a spend line is dated by, per basis."""
    return "invoice__invoice_date" if basis == "invoiced" else "doc_date"


def _vendor_field(basis):
    return "invoice__vendor" if basis == "invoiced" else "purchase_order__vendor"


def _currency_field(basis):
    return "invoice__currency" if basis == "invoiced" else "purchase_order__currency"


def _document_field(basis):
    """The document a line belongs to — what ``invoice_count`` actually counts."""
    return "invoice" if basis == "invoiced" else "purchase_order"


def _classify_select_related(basis):
    """Every hop ``SpendClassificationRule.matches()`` walks, so the pass costs no extra query.

    ``matches()`` reads the vendor off the invoice/order, the org unit off
    ``order.requisition``, the invoice type off the invoice, and the GL account id off the line
    itself. Without these the classification pass would be four queries PER LINE.
    """
    if basis == "invoiced":
        return ("invoice", "invoice__vendor", "invoice__purchase_order",
                "invoice__purchase_order__requisition")
    return ("purchase_order", "purchase_order__requisition")


def active_rules(tenant):
    """This workspace's active rules in ``(priority, id)`` order — ONE query, fetched once.

    Handed to ``SpendClassificationRule.resolve()`` for every line so classifying ten thousand
    lines costs one query rather than ten thousand. ``resolve()`` re-filters the list against each
    line's own workspace, so passing it is safe as well as fast.
    """
    if tenant is None:
        return []
    return list(SpendClassificationRule.objects
                .filter(tenant=tenant, is_active=True)
                .select_related("category")
                .order_by("priority", "id"))


def category_filter_q(tenant, basis, category_id):
    """A ``Q`` selecting the lines that belong to ONE category, in classification order.

    The passthrough leg (``item.category``) wins outright; the rules leg applies only to lines with
    no item category of their own, which is precisely the order
    ``item.category -> rule -> (Unclassified)`` that the cube uses. On the committed basis there is
    no item FK at all, so only the rules leg exists.

    Returns an always-false ``Q`` when nothing can select the category — never an empty ``Q()``,
    which would be always-TRUE and would silently report the whole workspace as that category.
    """
    rules_q = None
    for rule in SpendClassificationRule.objects.filter(
            tenant=tenant, is_active=True, category_id=category_id):
        predicate = rule.line_filter(basis)
        if predicate is not None:
            rules_q = predicate if rules_q is None else (rules_q | predicate)

    if basis != "invoiced":
        return rules_q if rules_q is not None else Q(pk__in=[])

    passthrough = Q(item__category_id=category_id)
    if rules_q is None:
        return passthrough
    unclassified_leg = Q(item__isnull=True) | Q(item__category__isnull=True)
    return passthrough | (rules_q & unclassified_leg)


def apply_axis_filters(lines, basis, tenant, *, vendor_id=None, category_id=None,
                       org_unit_id=None, gl_account_id=None):
    """The four cross-page GET filters, applied to a line window BEFORE anything aggregates it.

    Every pk arrives already through ``as_db_int`` (L11), so a hand-edited ``?vendor=abc`` is
    ``None`` here and the filter is skipped rather than raising. A pk from ANOTHER workspace is
    harmless without a second check: the window is tenant-scoped before these run, so a foreign pk
    matches nothing instead of leaking anything.
    """
    if vendor_id:
        lines = lines.filter(**{f"{_vendor_field(basis)}_id": vendor_id})
    if gl_account_id:
        lines = lines.filter(gl_account_id=gl_account_id)
    if org_unit_id:
        prefix = _order_prefix(basis)
        # The SQL mirror of the Coalesce walk: the requisition's unit when there is one, otherwise
        # the order's ship-to. Same predicate ``SpendClassificationRule.line_filter`` uses.
        lines = lines.filter(
            Q(**{f"{prefix}__requisition__org_unit_id": org_unit_id})
            | (Q(**{f"{prefix}__requisition__org_unit_id__isnull": True})
               & Q(**{f"{prefix}__ship_to_id": org_unit_id})))
    if category_id:
        lines = lines.filter(category_filter_q(tenant, basis, category_id))
    return lines


# -- the cube -------------------------------------------------------------------------------

def _rows_from_groups(groups, *, total, top_n):
    """Group tuples ``(pk, label, value, count)`` -> the pinned row dicts, biggest first.

    Row shape is pinned: ``{label, pk, value, display, pct, count}``. ``pk`` is ``None`` for the
    ``(unassigned)`` / ``(Unclassified)`` buckets, which is why every link a template draws off one
    of these rows has to be wrapped in ``{% if row.pk %}``.
    """
    ordered = sorted(groups, key=lambda row: (-(row[2] or ZERO), str(row[1])))
    return [{
        "label": label,
        "pk": pk,
        "value": money(value or ZERO),
        "display": _money(value),
        "pct": _share(value, total),
        "count": count or 0,
    } for pk, label, value, count in ordered[:top_n]]


def _category_groups(tenant, basis, lines, rules):
    """``(groups, unclassified_value)`` for the category axis — the one axis SQL cannot group.

    Two passes, in classification order:

    1. **Passthrough (invoiced basis only).** ``item.category`` is a real column, so the lines that
       have one are grouped in the DATABASE — one query, no ceiling.
    2. **Rules.** The remainder (no item, or an item with no category — and on the committed basis,
       everything, because ``PurchaseOrderLine`` has no item FK) is walked line by line against the
       pre-fetched rule list, capped at :data:`MAX_CLASSIFY_LINES`.

    The remainder's exact total is aggregated FIRST, so whatever the capped walk did not reach is
    added to ``(Unclassified)`` by value. The detail can be truncated; the totals never are.
    """
    buckets = defaultdict(lambda: [ZERO, 0])  # (pk, label) -> [value, count]

    remainder = lines
    if basis == "invoiced":
        for row in (lines.filter(item__category__isnull=False)
                    .values("item__category_id", "item__category__name")
                    .annotate(v=Sum("line_total"), n=Count("id"))):
            key = (row["item__category_id"], row["item__category__name"])
            buckets[key][0] += row["v"] or ZERO
            buckets[key][1] += row["n"] or 0
        remainder = lines.filter(Q(item__isnull=True) | Q(item__category__isnull=True))

    totals = remainder.aggregate(v=Sum("line_total"), n=Count("id"))
    remainder_value = totals["v"] or ZERO
    remainder_count = totals["n"] or 0

    walked_value = ZERO
    walked_count = 0
    if rules and remainder_count:
        for line in (remainder.select_related(*_classify_select_related(basis))
                     [:MAX_CLASSIFY_LINES]):
            category = SpendClassificationRule.resolve(line, basis, rules)
            key = ((category.pk, category.name) if category is not None
                   else (None, UNCLASSIFIED_LABEL))
            value = line.line_total or ZERO
            buckets[key][0] += value
            buckets[key][1] += 1
            walked_value += value
            walked_count += 1

    # Everything the walk did not reach — no rules at all, or past the cap — is unclassified by
    # definition. Added by exact aggregate difference, so the bars still sum to the KPI strip.
    leftover_value = remainder_value - walked_value
    leftover_count = remainder_count - walked_count
    if leftover_count or leftover_value:
        key = (None, UNCLASSIFIED_LABEL)
        buckets[key][0] += leftover_value
        buckets[key][1] += leftover_count

    groups = [(pk, label, value, count) for (pk, label), (value, count) in buckets.items()]
    unclassified = buckets.get((None, UNCLASSIFIED_LABEL), [ZERO, 0])[0]
    return groups, money(unclassified)


def spend_cube(tenant, basis, start, end, dimension, top_n=MAX_GROUP_ROWS, lines=None):
    """Spend grouped on one axis — ``[{label, pk, value, display, pct, count}, …]``.

    ``lines`` lets a page that has already built and filtered its window pass it in rather than
    have the cube rebuild it (the dashboard runs four axes over ONE window). ``rules`` for the
    category axis are fetched here when needed; a caller running several category cubes should
    prefer :func:`_category_groups` with its own pre-fetched list.
    """
    if tenant is None or dimension == "none":
        return []
    if lines is None:
        lines = basis_lines(tenant, basis, start, end)

    total = lines.aggregate(v=Sum("line_total"))["v"] or ZERO

    if dimension == "category":
        groups, _unclassified = _category_groups(tenant, basis, lines, active_rules(tenant))
        return _rows_from_groups(groups, total=total, top_n=top_n)

    if dimension == "department":
        rows = (lines.annotate(_dept=_department_expression(basis))
                .values("_dept").annotate(v=Sum("line_total"), n=Count("id")))
        rows = list(rows)
        names = dict(OrgUnit.objects.filter(
            tenant=tenant, pk__in=[r["_dept"] for r in rows if r["_dept"]]
        ).values_list("id", "name"))
        groups = [(r["_dept"], names.get(r["_dept"], UNASSIGNED_LABEL) if r["_dept"]
                   else UNASSIGNED_LABEL, r["v"], r["n"]) for r in rows]
        return _rows_from_groups(groups, total=total, top_n=top_n)

    if dimension == "supplier":
        field = _vendor_field(basis)
        rows = (lines.values(f"{field}_id", f"{field}__name")
                .annotate(v=Sum("line_total"), n=Count("id")))
        groups = [(r[f"{field}_id"], r[f"{field}__name"] or UNASSIGNED_LABEL, r["v"], r["n"])
                  for r in rows]
        return _rows_from_groups(groups, total=total, top_n=top_n)

    if dimension == "gl_account":
        rows = (lines.values("gl_account_id", "gl_account__code", "gl_account__name")
                .annotate(v=Sum("line_total"), n=Count("id")))
        groups = []
        for row in rows:
            if row["gl_account_id"]:
                label = f"{row['gl_account__code']} — {row['gl_account__name']}"
            else:
                label = UNASSIGNED_LABEL
            groups.append((row["gl_account_id"], label, row["v"], row["n"]))
        return _rows_from_groups(groups, total=total, top_n=top_n)

    if dimension == "currency":
        field = _currency_field(basis)
        rows = (lines.values(f"{field}__code").annotate(v=Sum("line_total"), n=Count("id")))
        groups = [(None, r[f"{field}__code"] or UNASSIGNED_LABEL, r["v"], r["n"]) for r in rows]
        return _rows_from_groups(groups, total=total, top_n=top_n)

    if dimension in ("month", "quarter"):
        rows = (lines.annotate(_bucket=TruncMonth(_date_field(basis)))
                .values("_bucket").annotate(v=Sum("line_total"), n=Count("id")))
        groups = []
        for row in rows:
            bucket = row["_bucket"]
            if bucket is None:
                label = UNASSIGNED_LABEL
            elif dimension == "quarter":
                label = f"Q{(bucket.month - 1) // 3 + 1} {bucket.year}"
            else:
                label = bucket.strftime("%b %Y")
            groups.append((None, label, row["v"], row["n"]))
        if dimension == "quarter":
            # TruncMonth then fold: three month buckets collapse into one quarter label.
            folded = defaultdict(lambda: [ZERO, 0])
            for _pk, label, value, count in groups:
                folded[label][0] += value or ZERO
                folded[label][1] += count or 0
            groups = [(None, label, v, n) for label, (v, n) in folded.items()]
        return _rows_from_groups(groups, total=total, top_n=top_n)

    if dimension == "invoice_type":
        if basis != "invoiced":
            # A purchase order has no invoice type. Returning an empty axis is the honest answer;
            # inventing one would classify committed spend off a field that does not exist.
            return []
        # Deferred import: 6.13's entity module must not be pulled in at this module's import time
        # while the 6.14 sub-package is still being initialised.
        from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import (
            SupplierInvoice)

        rows = lines.values("invoice__invoice_type").annotate(v=Sum("line_total"), n=Count("id"))
        labels = dict(SupplierInvoice.INVOICE_TYPE_CHOICES)
        groups = [(None, labels.get(r["invoice__invoice_type"], r["invoice__invoice_type"]
                                    or UNASSIGNED_LABEL), r["v"], r["n"]) for r in rows]
        return _rows_from_groups(groups, total=total, top_n=top_n)

    return []


def monthly_trend(tenant, basis, start, end, lines=None):
    """``{labels, data}`` — spend by month across the window, oldest first."""
    if tenant is None:
        return {"labels": [], "data": []}
    if lines is None:
        lines = basis_lines(tenant, basis, start, end)
    rows = (lines.annotate(_bucket=TruncMonth(_date_field(basis)))
            .values("_bucket").annotate(v=Sum("line_total")).order_by("_bucket"))
    labels, data = [], []
    for row in rows:
        if row["_bucket"] is None:
            continue
        labels.append(row["_bucket"].strftime("%b %Y"))
        data.append(float(row["v"] or 0))
    return {"labels": labels, "data": data}


def currency_split(tenant, basis, start, end, lines=None):
    """``{rows, mixed_currency}`` — spend at FACE VALUE per currency.

    There is no FX rate table anywhere in this repository, so there is no honest single total for a
    multi-currency window. When more than one currency carries spend, ``mixed_currency`` is True
    and the page renders these rows INSTEAD of one number. No rate is ever invented.
    """
    if tenant is None:
        return {"rows": [], "mixed_currency": False}
    if lines is None:
        lines = basis_lines(tenant, basis, start, end)
    field = _currency_field(basis)
    rows = []
    for row in (lines.values(f"{field}__code", f"{field}__name")
                .annotate(v=Sum("line_total"), n=Count("id")).order_by("-v")):
        code = row[f"{field}__code"] or ""
        total = money(row["v"] or ZERO)
        rows.append({
            "code": code or UNASSIGNED_LABEL,
            "label": row[f"{field}__name"] or code or UNASSIGNED_LABEL,
            "total": total,
            "display": _money(total),
            "count": row["n"] or 0,
        })
    carrying = [row for row in rows if row["total"]]
    return {"rows": rows, "mixed_currency": len(carrying) > 1}


def classified_pct(tenant, basis, start, end, lines=None, rules=None):
    """``(pct, unclassified_value, category_rows)`` — how much spend the taxonomy actually reaches.

    Returned together because all three come out of ONE category pass; computing the percentage
    separately would run the classification walk twice for the same page.
    """
    if tenant is None:
        return ZERO, ZERO, []
    if lines is None:
        lines = basis_lines(tenant, basis, start, end)
    if rules is None:
        rules = active_rules(tenant)
    total = lines.aggregate(v=Sum("line_total"))["v"] or ZERO
    groups, unclassified = _category_groups(tenant, basis, lines, rules)
    rows = _rows_from_groups(groups, total=total, top_n=MAX_GROUP_ROWS)
    pct = _share(Decimal(total) - Decimal(unclassified), total)
    return pct, unclassified, rows


def maverick_rate(tenant, start, end):
    """``{maverick_value, addressable_value, pct, txn_pct, band}`` for the window.

    The numerator is every ADDRESSABLE maverick finding that has not been dismissed as a false
    positive — a dismissed finding is the workspace saying "this was never off-contract", so
    counting it would make the rate un-improvable. The denominator is recognised spend over the
    same window, which is what ``is_addressable`` is a flag against.

    ``band`` is one of low / medium / high off the 10% / 20% thresholds the page prints beside it,
    so the colour on the tile always has its own legend.
    """
    empty = {"maverick_value": ZERO, "addressable_value": ZERO, "pct": ZERO, "txn_pct": ZERO,
             "band": "low"}
    if tenant is None:
        return empty

    findings = MaverickSpendFinding.objects.filter(
        tenant=tenant, is_addressable=True,
        document_date__gte=start, document_date__lt=end,
    ).exclude(status="dismissed")
    found = findings.aggregate(v=Sum("amount"), n=Count("id", distinct=True))
    maverick_value = money(found["v"] or ZERO)

    lines = invoiced_lines(tenant, start, end)
    spend = lines.aggregate(v=Sum("line_total"), n=Count(_document_field("invoiced"),
                                                         distinct=True))
    addressable_value = money(spend["v"] or ZERO)

    documents = spend["n"] or 0
    flagged_documents = findings.filter(supplier_invoice__isnull=False).values(
        "supplier_invoice_id").distinct().count()

    pct = _share(maverick_value, addressable_value)
    band = "low"
    if pct > MAVERICK_BAND_HIGH:
        band = "high"
    elif pct >= MAVERICK_BAND_LOW:
        band = "medium"
    return {
        "maverick_value": maverick_value,
        "addressable_value": addressable_value,
        "pct": pct,
        "txn_pct": _share(flagged_documents, documents),
        "band": band,
    }


def spend_kpis(tenant, basis, start, end, lines=None, *, by_supplier=None, classified=None):
    """The eight pinned KPI tiles, each a scalar result dict.

    ``by_supplier`` / ``classified`` are passed in by a page that already computed them, so the
    strip costs no extra pass over the same window.
    """
    keys = ("net_spend", "invoice_count", "supplier_count", "avg_invoice",
            "classified_pct", "maverick_pct", "top5_share_pct", "po_less_share_pct")
    if tenant is None:
        return {key: _scalar(None, "—") for key in keys}

    if lines is None:
        lines = basis_lines(tenant, basis, start, end)

    document_field = _document_field(basis)
    totals = lines.aggregate(
        value=Sum("line_total"),
        documents=Count(document_field, distinct=True),
        suppliers=Count(f"{_vendor_field(basis)}", distinct=True),
    )
    net = money(totals["value"] or ZERO)
    documents = totals["documents"] or 0
    suppliers = totals["suppliers"] or 0
    average = money(Decimal(net) / documents) if documents else ZERO

    top5 = ZERO
    if by_supplier:
        top5 = _share(sum((row["value"] for row in by_supplier[:5]), ZERO), net)

    classified_share = classified if classified is not None else classified_pct(
        tenant, basis, start, end, lines)[0]

    if basis == "invoiced":
        po_less = lines.filter(invoice__purchase_order__isnull=True).aggregate(
            v=Sum("line_total"))["v"] or ZERO
        po_less_tile = _scalar(_share(po_less, net), _pct(_share(po_less, net)), max_value=100)
    else:
        # A purchase order cannot be "PO-less". Reported as not-computable rather than as zero —
        # a zero here would read as "no off-PO spend", which is a different and false claim.
        po_less_tile = _scalar(None, "—", max_value=100)

    maverick = maverick_rate(tenant, start, end)

    return {
        "net_spend": _scalar(net, _money(net)),
        "invoice_count": _scalar(documents, _num(documents)),
        "supplier_count": _scalar(suppliers, _num(suppliers)),
        "avg_invoice": _scalar(average, _money(average)),
        "classified_pct": _scalar(classified_share, _pct(classified_share), max_value=100),
        "maverick_pct": _scalar(maverick["pct"], _pct(maverick["pct"]), max_value=100),
        "top5_share_pct": _scalar(top5, _pct(top5), max_value=100),
        "po_less_share_pct": po_less_tile,
    }


# =================================================================================================
# THE SAVED REPORT  -  one SpendReport row turned into a JSON-serialisable result
# =================================================================================================

_MEASURE_LABELS = dict(MEASURE_CHOICES)
_DIMENSION_LABELS = dict(DIMENSION_CHOICES)


def _measure_value(measure, lines, tenant, basis, start, end):
    """The single-figure answer for a ``dimension_1 == "none"`` report - ``(value, display)``."""
    total = lines.aggregate(v=Sum("line_total"))["v"] or ZERO
    count = lines.count()
    if measure == "transaction_count":
        return count, _num(count)
    if measure == "avg_transaction":
        avg = (Decimal(total) / Decimal(count)) if count else ZERO
        return money(avg), _money(avg)
    if measure == "supplier_count":
        field = _vendor_field(basis)
        n = lines.values(f"{field}_id").distinct().count()
        return n, _num(n)
    if measure in ("maverick_spend", "maverick_pct"):
        rate = maverick_rate(tenant, start, end)
        if measure == "maverick_spend":
            return rate["maverick_value"], _money(rate["maverick_value"])
        return rate["pct"], _pct(rate["pct"])
    if measure == "classified_pct":
        pct, _unclassified, _rows = classified_pct(tenant, basis, start, end, lines=lines)
        return pct, _pct(pct)
    if measure == "leakage":
        value = money(MaverickSpendFinding.objects.filter(
            tenant=tenant, document_date__gte=start, document_date__lt=end,
        ).exclude(status="dismissed").aggregate(v=Sum("leakage_amount"))["v"] or ZERO)
        return value, _money(value)
    return money(total), _money(total)


def _row_measure(measure, row):
    """The measure cell for ONE grouped row, straight off the cube row's own aggregate.

    Only the measures a grouped cube can answer PER ROW are answered per row; the workspace-wide
    ones (maverick / classified / leakage) fall back to the row's spend value, because a per-row
    maverick share would need one extra scan per row, and a report that issues a query per row is
    exactly the defect this module exists to avoid.
    """
    if measure == "transaction_count":
        return row["count"], _num(row["count"])
    if measure == "avg_transaction":
        count = row["count"] or 0
        avg = (Decimal(row["value"]) / Decimal(count)) if count else ZERO
        return money(avg), _money(avg)
    return row["value"], row["display"]


def _narrow_to_row(lines, basis, tenant, dimension, row):
    """The line window narrowed to ONE cube row, for the second axis.

    Only an axis that carries a real pk can be narrowed by pk; a label-only axis (month, quarter,
    currency, invoice type) returns the window unchanged, which makes its second axis a breakdown
    of the whole window rather than a wrong one. ``pk`` is ``None`` for every ``(unassigned)`` /
    ``(Unclassified)`` bucket - which is precisely when "cannot narrow" is the honest answer.
    """
    pk = row.get("pk")
    if not pk:
        return lines
    if dimension == "supplier":
        return lines.filter(**{f"{_vendor_field(basis)}_id": pk})
    if dimension == "gl_account":
        return lines.filter(gl_account_id=pk)
    if dimension == "category":
        return lines.filter(category_filter_q(tenant, basis, pk))
    if dimension == "department":
        prefix = _order_prefix(basis)
        return lines.filter(
            Q(**{f"{prefix}__requisition__org_unit_id": pk})
            | (Q(**{f"{prefix}__requisition__org_unit_id__isnull": True})
               & Q(**{f"{prefix}__ship_to_id": pk})))
    return lines


def compute_report(report):
    """One saved ``SpendReport`` -> ``{summary, columns, rows, chart_type, chart_labels,
    chart_data}``.

    **Everything returned is JSON-serialisable** - that is what lets ``spendreport_snapshot``
    store the payload verbatim and ``spendreportsnapshot_detail`` re-render it with NO recompute.
    Money therefore leaves here as a ``float`` in ``chart_data`` and as a formatted STRING in a
    table cell; a raw ``Decimal`` never crosses the boundary.

    Never raises on a report whose saved filters point at deleted rows: every filter FK is
    SET_NULL, so a missing one is simply not applied.
    """
    tenant = report.tenant
    if tenant is None:
        return {"summary": [], "columns": [], "rows": [], "chart_type": report.chart_type,
                "chart_labels": [], "chart_data": []}

    start, end = range_bounds(report.date_range, report.date_from, report.date_to)
    lines = basis_lines(tenant, report.basis, start, end)
    lines = apply_axis_filters(
        lines, report.basis, tenant,
        vendor_id=report.vendor_id, category_id=report.category_id,
        org_unit_id=report.org_unit_id, gl_account_id=report.gl_account_id,
    )
    if report.min_amount is not None:
        lines = lines.filter(line_total__gte=report.min_amount)

    # The model validates 1-100; re-clamped here so a row written before that validator existed
    # (or by a fixture) can never ask for an unbounded cube.
    top_n = max(1, min(int(report.top_n or 20), 100))
    measure_label = _MEASURE_LABELS.get(report.measure, "Value")

    # -- the KPI strip ---------------------------------------------------------------------------
    total = lines.aggregate(v=Sum("line_total"))["v"] or ZERO
    count = lines.count()
    split = currency_split(tenant, report.basis, start, end, lines=lines)
    summary = [
        {"label": "Net spend", "value": _money(total)},
        {"label": "Lines", "value": _num(count)},
        {"label": "Window", "value": f"{start:%d %b %Y} - {end - timedelta(days=1):%d %b %Y}"},
    ]
    if split["mixed_currency"]:
        summary.append({"label": "Currencies",
                        "value": ", ".join(row["code"] for row in split["rows"] if row["total"])})

    # -- the single-figure report -----------------------------------------------------------------
    if report.dimension_1 in ("", "none"):
        _value, display = _measure_value(report.measure, lines, tenant, report.basis, start, end)
        summary.insert(0, {"label": measure_label, "value": display})
        return {"summary": summary, "columns": [measure_label], "rows": [[display]],
                "chart_type": "table", "chart_labels": [], "chart_data": []}

    # -- the grouped report -----------------------------------------------------------------------
    primary = spend_cube(tenant, report.basis, start, end, report.dimension_1,
                         top_n=top_n, lines=lines)
    dim1_label = _DIMENSION_LABELS.get(report.dimension_1, "Group")
    chart_labels = [row["label"] for row in primary]
    chart_data = [float(row["value"] or 0) for row in primary]

    if report.dimension_2 in ("", "none"):
        columns = [dim1_label, measure_label, "Share", "Lines"]
        rows = []
        for row in primary:
            _value, display = _row_measure(report.measure, row)
            rows.append([row["label"], display, _pct(row["pct"]), _num(row["count"])])
        return {"summary": summary, "columns": columns, "rows": rows,
                "chart_type": report.chart_type, "chart_labels": chart_labels,
                "chart_data": chart_data}

    # Two axes: the second is cut INSIDE each row the first axis kept. One cube per kept row, and
    # the kept rows are bounded by ``top_n`` (<= 100 by the model's own validator) - never by how
    # many suppliers the workspace happens to have.
    dim2_label = _DIMENSION_LABELS.get(report.dimension_2, "Group")
    columns = [dim1_label, dim2_label, measure_label, "Share", "Lines"]
    rows = []
    for row in primary:
        inner_lines = _narrow_to_row(lines, report.basis, tenant, report.dimension_1, row)
        inner = spend_cube(tenant, report.basis, start, end, report.dimension_2,
                           top_n=top_n, lines=inner_lines)
        if not inner:
            _value, display = _row_measure(report.measure, row)
            rows.append([row["label"], UNASSIGNED_LABEL, display, _pct(row["pct"]),
                         _num(row["count"])])
            continue
        for sub in inner:
            _value, display = _row_measure(report.measure, sub)
            rows.append([row["label"], sub["label"], display, _pct(sub["pct"]),
                         _num(sub["count"])])
    return {"summary": summary, "columns": columns, "rows": rows,
            "chart_type": report.chart_type, "chart_labels": chart_labels,
            "chart_data": chart_data}
