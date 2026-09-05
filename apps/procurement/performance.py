"""Procurement 6.16 Supplier Performance & Evaluation — the compute layer.

Every figure 6.16 renders is an aggregate over rows that belong to somebody else — SCM's
receipts, quotes and purchase orders, this app's discrepancies, returns, invoices, disputes,
delivery instalments, backorders, PO changes and suspensions. That arithmetic lives HERE, once,
so the scorecard, the KPI detail page, the benchmark board and the trend board can never hold
two answers to "how did this supplier do?".

**The flat-module precedent is ``analytics.py`` (6.14's).** Single-purpose compute sits flat at
the app root so views stay thin and every figure is unit-testable without a request. This module
does NOT touch ``analytics.py`` and ``analytics.py`` does not touch this one.

**Import direction is one-way: ``performance`` imports ``models``; a model NEVER imports
``performance``.** Inverting it would cycle at app-registry load. The 6.16 models come from their
ENTITY modules rather than ``apps.procurement.models``, because this sub-package is not added to
the package ``__init__`` re-export block until the Integrate phase; sibling-app models (``scm``,
``core``) are imported INSIDE the function that needs them, exactly as
``scm.SupplierScorecard.recompute_from_signals`` imports its own dependencies.

**No metric ever invents a zero.** A resolver with no rows in the period returns ``None``, never
``Decimal(0)`` — the same rule ``recompute_from_signals()`` follows when it leaves a dimension
untouched. A phantom zero would silently tank a supplier's score over a gap in OUR data, and a
supplier cannot argue with a number nobody can trace. Every resolver therefore returns
``(value_or_None, breakdown)`` and the breakdown says what was counted, over what window.

**Breakdowns are JSON, so every number in them is a string.** ``SupplierKpiScore.breakdown`` is a
plain ``JSONField`` with the default encoder, which cannot serialise a ``Decimal``. Values go in
through :func:`_num` / ``str()``; the detail page prints them verbatim.

**Generating a scorecard is a one-way door** — see :data:`HANDOVER_NOTE` and
:func:`generate_scorecard_lines`.
"""
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, F, Min, Q, Sum
from django.utils import timezone

# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULES directly, never
# ``apps.procurement.models`` — the package __init__ re-export block lands at Integrate.
from apps.procurement.models.SupplierPerformanceEvaluation.ScorecardKpiScores import (
    SupplierKpiScore)
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi


#: Every board query is bounded (the 6.15 precedent) — a tenant with a large supply base still
#: renders one page, and the caller reports ``truncated`` rather than silently cutting.
ROW_CAP = 500

#: How many distinct periods a picker offers, and how far back a trend series reaches.
PERIOD_CAP = 24

#: Per-list cap on a detail page.
DETAIL_ROW_CAP = 50

#: ONE constant, so the KPI detail page, the benchmark board and the trend board cannot describe
#: the benchmark data differently. There is no external feed anywhere in this system and no page
#: may imply there is.
BENCHMARK_NOTE = ("Benchmarks here are your own supply base only. "
                  "There is no external industry feed in this system.")

#: ONE constant for the one-way door. Printed by the evaluation register, the evaluation detail
#: page and the Generate button's confirm dialog — see :func:`generate_scorecard_lines`.
HANDOVER_NOTE = (
    "Generating this scorecard hands it permanently to Procurement 6.16. The four dimension "
    "scores are written from the KPI lines, manual_override is set, and SCM's signal engine "
    "(recompute_from_signals()) will skip this scorecard from then on. This cannot be undone "
    "from here.")

#: The four ``scm.SupplierScorecard`` columns a KPI can feed, mapped to the model field holding
#: each. Keys mirror ``SupplierKpi.DIMENSION_CHOICES`` exactly.
DIMENSION_FIELDS = {
    "delivery": "delivery_score",
    "quality": "quality_score",
    "price": "price_score",
    "responsiveness": "responsiveness_score",
}

#: Every column :func:`generate_scorecard_lines` writes on a score line, in one place so the
#: ``bulk_update`` field list and the values dict it is built from cannot drift apart. Note
#: ``updated_at``: **``bulk_update`` does not fire ``auto_now``** — it compiles a ``CASE … WHEN``
#: over the values already on the instances and never calls ``Field.pre_save`` — so the stamp is
#: set by hand in the loop and listed here. (``bulk_create`` DOES call ``pre_save``, so a new
#: line's ``created_at``/``updated_at`` still look after themselves.)
_LINE_FIELDS = (
    "measured_value", "score", "band", "weight_applied", "target_at_time", "direction_at_time",
    "source_at_time", "unit_at_time", "kpi_name", "kpi_category", "breakdown",
    "respondent_count", "computed_at", "computed_by", "updated_at",
)

ZERO = Decimal("0")
_HUNDRED = Decimal("100")
#: 2dp — the shape of ``SupplierKpiScore.score`` and of every percentage this module returns.
_STEP = Decimal("0.01")
#: The risk axis of the benchmark quadrant. ``scm.SupplierRiskAssessment.risk_index`` is a 1-5
#: mean, so 2.5 is its midpoint.
_LOW_RISK = Decimal("2.5")


def _num(value):
    """A number as something ``json.dumps`` accepts, or ``None``.

    ``SupplierKpiScore.breakdown`` is a JSONField with the DEFAULT encoder: a ``Decimal`` in it
    raises ``TypeError: Object of type Decimal is not JSON serializable`` at save time, which
    would take the whole generate transaction down. Stringifying at the boundary keeps the
    figure exact (unlike ``float()``) and keeps the write safe.
    """
    return None if value is None else str(value)


def _breakdown(metric, start, end, rows, **extra):
    """The shape every resolver returns as its second element."""
    data = {"metric": metric, "window": [str(start), str(end)], "rows": rows}
    data.update(extra)
    return data


def _pct(numerator, denominator):
    """``numerator / denominator * 100`` at 2dp, or ``None`` when there is nothing to divide by.

    ``None`` — never 0 — is the whole point: an empty denominator means we have no evidence, and
    0% is a claim about the supplier rather than about our data.
    """
    if not denominator:
        return None
    return (Decimal(numerator) * _HUNDRED / Decimal(denominator)).quantize(_STEP)


def _mean(values):
    """Arithmetic mean at 2dp, or ``None`` for an empty sequence."""
    if not values:
        return None
    return (sum(Decimal(v) for v in values) / Decimal(len(values))).quantize(_STEP)


# --------------------------------------------------------------------------------------------
# Shared populations
#
# Two resolvers need "how many receipts did we book from this supplier in the window?" as their
# denominator, and one needs "did we buy from this supplier at all?". Both are defined once here
# so ncr_rate and rtv_rate can never disagree about what a receipt is.
# --------------------------------------------------------------------------------------------

def _received_notes(tenant, party, start, end):
    """Booked goods receipts against this supplier in the window (``status="received"``).

    The vendor hop is ``purchase_order__vendor`` — a receipt has no vendor FK of its own.
    """
    from apps.scm.models import GoodsReceiptNote
    return GoodsReceiptNote.objects.filter(
        tenant=tenant, purchase_order__vendor=party, status="received",
        receipt_date__range=(start, end))


def _has_activity(tenant, party, start, end):
    """Did we transact with this supplier at all in the window?

    Used only by ``suspension_incidents``, the one metric whose honest answer can be a real
    zero: a supplier we bought from and never suspended scored 0 incidents. A supplier we never
    bought from has no incident rate at all, and gets ``None``.
    """
    from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
    from apps.scm.models import PurchaseOrder

    if PurchaseOrder.objects.filter(
            tenant=tenant, vendor=party, order_date__range=(start, end)).exists():
        return True
    if _received_notes(tenant, party, start, end).exists():
        return True
    return SupplierInvoice.objects.filter(
        tenant=tenant, vendor=party, invoice_date__range=(start, end)).exists()


# --------------------------------------------------------------------------------------------
# The fourteen derived resolvers
#
# Signature is uniform: ``(tenant, party, start, end) -> (Decimal | None, dict)``.
# Every join path below was GREPPED against the as-built models (L28 — the ERD is intent, the
# grep is truth). Several are counter-intuitive and are commented where they are used.
# --------------------------------------------------------------------------------------------

def _resolve_otd(tenant, party, start, end):
    """On-time delivery %: receipts booked on or before the PO's expected date."""
    agg = (_received_notes(tenant, party, start, end)
           .filter(purchase_order__expected_date__isnull=False)
           .aggregate(datable=Count("pk"),
                      on_time=Count("pk", filter=Q(
                          receipt_date__lte=F("purchase_order__expected_date")))))
    datable, on_time = agg["datable"] or 0, agg["on_time"] or 0
    return _pct(on_time, datable), _breakdown(
        "otd", start, end, datable, on_time=on_time, datable_receipts=datable,
        note="Receipts whose PO carries an expected date; a PO with no expected date cannot be "
             "late and is excluded from both sides.")


def _resolve_otif(tenant, party, start, end):
    """On-time in-full %: on time AND every ordered line quantity actually arrived."""
    from apps.scm.models import GoodsReceiptLine

    rows = list(_received_notes(tenant, party, start, end)
                .filter(purchase_order__expected_date__isnull=False)
                .values_list("pk", "receipt_date", "purchase_order__expected_date"))
    if not rows:
        return None, _breakdown("otif", start, end, 0, on_time=0, in_full=0, datable_receipts=0)

    receipt_ids = [pk for pk, _, _ in rows]
    on_time_ids = {pk for pk, received, expected in rows if received <= expected}

    # ONE grouped query for every line of every receipt in the window — never a query per
    # receipt. GoodsReceiptLine is a plain models.Model with NO tenant column of its own, so it
    # is scoped through its parent receipt (``goods_receipt__tenant``), not by ``tenant=``.
    short_ids, seen_ids = set(), set()
    line_totals = (GoodsReceiptLine.objects
                   .filter(goods_receipt__tenant=tenant, goods_receipt_id__in=receipt_ids)
                   .values("goods_receipt_id", "po_line_id", "po_line__quantity")
                   .annotate(received=Sum("quantity_received")))
    for row in line_totals:
        seen_ids.add(row["goods_receipt_id"])
        if (row["received"] or ZERO) < (row["po_line__quantity"] or ZERO):
            short_ids.add(row["goods_receipt_id"])

    # A receipt with no lines at all is not "in full" — there is nothing to say it was complete.
    in_full = sum(1 for pk in on_time_ids if pk in seen_ids and pk not in short_ids)
    return _pct(in_full, len(rows)), _breakdown(
        "otif", start, end, len(rows), on_time=len(on_time_ids), in_full=in_full,
        datable_receipts=len(rows), short_receipts=len(short_ids),
        note="In full = every ordered line's received quantity reached the PO line quantity.")


def _resolve_defect_rate(tenant, party, start, end):
    """Reject rate %: rejected / (received + rejected) across the supplier's receipt lines."""
    from apps.scm.models import GoodsReceiptLine

    # GoodsReceiptLine carries NO tenant column (plain models.Model) — scope through the parent
    # receipt. The vendor hop is goods_receipt__purchase_order__vendor.
    agg = (GoodsReceiptLine.objects
           .filter(goods_receipt__tenant=tenant,
                   goods_receipt__purchase_order__vendor=party,
                   goods_receipt__receipt_date__range=(start, end))
           .aggregate(lines=Count("pk"), received=Sum("quantity_received"),
                      rejected=Sum("quantity_rejected")))
    received = agg["received"] or ZERO
    rejected = agg["rejected"] or ZERO
    total = received + rejected
    value = None if total <= ZERO else (rejected * _HUNDRED / total).quantize(_STEP)
    return value, _breakdown(
        "defect_rate", start, end, agg["lines"] or 0,
        received=_num(received), rejected=_num(rejected), inspected=_num(total))


def _resolve_ncr_rate(tenant, party, start, end):
    """Discrepancy (NCR) rate %: discrepancies raised / receipts booked."""
    from apps.procurement.models.GoodsReceiptInspection.ReceiptDiscrepancies import (
        ReceiptDiscrepancy)

    # ReceiptDiscrepancy has NO vendor FK and NO business date of its own — both hops go through
    # the goods receipt. Using ``supplier=`` or a local date column here is a FieldError.
    discrepancies = ReceiptDiscrepancy.objects.filter(
        tenant=tenant,
        goods_receipt__purchase_order__vendor=party,
        goods_receipt__receipt_date__range=(start, end)).count()
    receipts = _received_notes(tenant, party, start, end).count()
    return _pct(discrepancies, receipts), _breakdown(
        "ncr_rate", start, end, discrepancies,
        discrepancies=discrepancies, receipts=receipts)


def _resolve_rtv_rate(tenant, party, start, end):
    """Return-to-vendor rate %: RTVs raised / receipts booked."""
    from apps.procurement.models.GoodsReceiptInspection.ReturnsToVendor import ReturnToVendor

    # ``shipped_on`` is editable=False and blank on every RTV that has not shipped yet, so the
    # window rides ``created_at`` — when the return was RAISED, which is the event being counted.
    returns = ReturnToVendor.objects.filter(
        tenant=tenant, vendor=party, created_at__date__range=(start, end)).count()
    receipts = _received_notes(tenant, party, start, end).count()
    return _pct(returns, receipts), _breakdown(
        "rtv_rate", start, end, returns, returns=returns, receipts=receipts,
        note="Windowed on when the return was raised (created_at) — shipped_on is blank until "
             "the return actually ships.")


def _resolve_invoice_accuracy(tenant, party, start, end):
    """Invoice accuracy %: matched (or within tolerance) / invoices that were actually matched."""
    from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice

    # SupplierInvoice's party FK is ``vendor`` — NOT ``supplier`` (that is InvoiceDispute's).
    agg = (SupplierInvoice.objects
           .filter(tenant=tenant, vendor=party, invoice_date__range=(start, end))
           .exclude(match_status="not_run")
           .aggregate(matched_run=Count("pk"),
                      clean=Count("pk", filter=Q(
                          match_status__in=("matched", "within_tolerance")))))
    run, clean = agg["matched_run"] or 0, agg["clean"] or 0
    return _pct(clean, run), _breakdown(
        "invoice_accuracy", start, end, run, clean=clean, matched_invoices=run,
        note="Invoices whose match was never run are excluded — they say nothing about the "
             "supplier's paperwork.")


def _resolve_dispute_rate(tenant, party, start, end):
    """Dispute rate %: disputes raised / invoices received."""
    from apps.procurement.models.InvoiceVoucherManagement.InvoiceDisputes import InvoiceDispute
    from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice

    # InvoiceDispute's party FK IS ``supplier``; SupplierInvoice's is ``vendor``. They differ,
    # and swapping them is a FieldError at the first call.
    disputes = InvoiceDispute.objects.filter(
        tenant=tenant, supplier=party, raised_at__date__range=(start, end)).count()
    invoices = SupplierInvoice.objects.filter(
        tenant=tenant, vendor=party, invoice_date__range=(start, end)).count()
    return _pct(disputes, invoices), _breakdown(
        "dispute_rate", start, end, disputes, disputes=disputes, invoices=invoices)


def _resolve_dispute_days(tenant, party, start, end):
    """Mean days to resolve a dispute — over the disputes that actually closed."""
    from apps.procurement.models.InvoiceVoucherManagement.InvoiceDisputes import InvoiceDispute

    pairs = InvoiceDispute.objects.filter(
        tenant=tenant, supplier=party, raised_at__date__range=(start, end),
        resolved_at__isnull=False).values_list("raised_at", "resolved_at")
    days = [(resolved - raised).days for raised, resolved in pairs]
    return _mean(days), _breakdown(
        "dispute_days", start, end, len(days), resolved_disputes=len(days),
        note="Open disputes are excluded — an unresolved dispute has no resolution time yet.")


def _resolve_promise_adherence(tenant, party, start, end):
    """Delivery-promise adherence %: instalments promised on or before the date we needed them."""
    from apps.procurement.models.OrderFulfillment.DeliverySchedule import DeliverySchedule

    # DeliverySchedule carries no supplier FK — the only hop is po_line__purchase_order__vendor.
    agg = (DeliverySchedule.objects
           .filter(tenant=tenant, po_line__purchase_order__vendor=party,
                   need_by_date__range=(start, end), promised_date__isnull=False)
           .aggregate(promised=Count("pk"),
                      kept=Count("pk", filter=Q(promised_date__lte=F("need_by_date")))))
    promised, kept = agg["promised"] or 0, agg["kept"] or 0
    return _pct(kept, promised), _breakdown(
        "promise_adherence", start, end, promised, kept=kept, promised=promised,
        note="An instalment the supplier never promised a date for is excluded from both sides.")


def _resolve_backorder_rate(tenant, party, start, end):
    """Backorder rate %: backorders raised / PO lines ordered."""
    from apps.procurement.models.OrderFulfillment.Backorder import Backorder
    from apps.scm.models import PurchaseOrderLine

    # Backorder reaches the supplier through po_line__purchase_order__vendor, and is windowed on
    # the date first committed to. PurchaseOrderLine is a plain models.Model with NO tenant
    # column, so the denominator is scoped through its purchase order.
    backorders = Backorder.objects.filter(
        tenant=tenant, po_line__purchase_order__vendor=party,
        original_promise_date__range=(start, end)).count()
    lines = PurchaseOrderLine.objects.filter(
        purchase_order__tenant=tenant, purchase_order__vendor=party,
        purchase_order__order_date__range=(start, end)).count()
    return _pct(backorders, lines), _breakdown(
        "backorder_rate", start, end, backorders, backorders=backorders, po_lines=lines)


def _resolve_po_change_rate(tenant, party, start, end):
    """PO change rate %: change requests raised / purchase orders placed."""
    from apps.procurement.models.PurchaseOrderManagement.PurchaseOrderChanges import (
        PurchaseOrderChange)
    from apps.scm.models import PurchaseOrder

    # PurchaseOrderChange has no business date of its own (only created_at / decided_at /
    # applied_at), so BOTH sides of the ratio are windowed on the purchase order's order_date —
    # which keeps a change and the PO it amends in the same period by construction.
    changes = PurchaseOrderChange.objects.filter(
        tenant=tenant, purchase_order__vendor=party,
        purchase_order__order_date__range=(start, end)).count()
    orders = PurchaseOrder.objects.filter(
        tenant=tenant, vendor=party, order_date__range=(start, end)).count()
    return _pct(changes, orders), _breakdown(
        "po_change_rate", start, end, changes, changes=changes, purchase_orders=orders,
        note="Both sides ride the purchase order's order_date — a change row carries no "
             "business date of its own.")


def _resolve_price_competitiveness(tenant, party, start, end):
    """Price competitiveness %: how close this supplier quoted to the best price on each RFQ."""
    from apps.scm.models import RFQQuote

    quotes = list(RFQQuote.objects
                  .filter(tenant=tenant, party=party, received_date__range=(start, end))
                  .values_list("rfq_id", "total"))
    if not quotes:
        return None, _breakdown("price_competitiveness", start, end, 0, compared=0)

    # The cheapest quote per RFQ in ONE grouped query — never a subquery per quote (the
    # recompute_from_signals precedent).
    rfq_ids = {rfq_id for rfq_id, _ in quotes}
    best_by_rfq = dict(RFQQuote.objects
                       .filter(tenant=tenant, rfq_id__in=rfq_ids).exclude(total__lte=ZERO)
                       .values("rfq_id").annotate(best=Min("total"))
                       .values_list("rfq_id", "best"))
    ratios = []
    for rfq_id, total in quotes:
        best = best_by_rfq.get(rfq_id)
        if best and total and total > ZERO:
            ratios.append(min(Decimal(1), best / total))
    if not ratios:
        return None, _breakdown("price_competitiveness", start, end, len(quotes), compared=0)
    average = sum(ratios) / Decimal(len(ratios))
    return (average * _HUNDRED).quantize(_STEP), _breakdown(
        "price_competitiveness", start, end, len(quotes), compared=len(ratios),
        rfqs=len(rfq_ids),
        note="100% means this supplier WAS the cheapest quote on every RFQ compared.")


def _resolve_quote_turnaround(tenant, party, start, end):
    """Quote turnaround days: mean days from RFQ issue to quote received."""
    from apps.scm.models import RFQQuote

    pairs = RFQQuote.objects.filter(
        tenant=tenant, party=party, received_date__range=(start, end),
        rfq__issue_date__isnull=False).values_list("received_date", "rfq__issue_date")
    days = [(received - issued).days for received, issued in pairs]
    return _mean(days), _breakdown(
        "quote_turnaround", start, end, len(days), quotes=len(days),
        note="Quotes whose RFQ was never issue-dated are excluded — there is nothing to measure "
             "the turnaround from.")


def _resolve_suspension_incidents(tenant, party, start, end):
    """Suspension incidents: blocks that came into force in the window.

    The ONE metric whose honest answer can be a real zero — but only for a supplier we actually
    transacted with. A supplier we never bought from has no incident rate at all, and gets
    ``None`` rather than a flattering 0.
    """
    from apps.procurement.models.VendorManagement.VendorSuspensions import VendorSuspension

    incidents = VendorSuspension.objects.filter(
        tenant=tenant, supplier=party, status="active",
        starts_on__range=(start, end)).count()
    if not incidents and not _has_activity(tenant, party, start, end):
        return None, _breakdown(
            "suspension_incidents", start, end, 0, incidents=0, had_activity=False,
            note="No procurement activity with this supplier in the period — a supplier you did "
                 "not buy from has no incident rate.")
    return Decimal(incidents).quantize(_STEP), _breakdown(
        "suspension_incidents", start, end, incidents, incidents=incidents, had_activity=True)


#: The CLOSED resolver registry. One key per ``SupplierKpi.DERIVED_METRIC_CHOICES`` value — the
#: assertion below is what keeps the promise that model module makes.
DERIVED_RESOLVERS = {
    "otd": _resolve_otd,
    "otif": _resolve_otif,
    "defect_rate": _resolve_defect_rate,
    "ncr_rate": _resolve_ncr_rate,
    "rtv_rate": _resolve_rtv_rate,
    "invoice_accuracy": _resolve_invoice_accuracy,
    "dispute_rate": _resolve_dispute_rate,
    "dispute_days": _resolve_dispute_days,
    "promise_adherence": _resolve_promise_adherence,
    "backorder_rate": _resolve_backorder_rate,
    "po_change_rate": _resolve_po_change_rate,
    "price_competitiveness": _resolve_price_competitiveness,
    "quote_turnaround": _resolve_quote_turnaround,
    "suspension_incidents": _resolve_suspension_incidents,
}

# Import-time honesty check. ``DERIVED_METRIC_CHOICES`` is documented as a CLOSED registry whose
# every key is a promise that a reviewed resolver exists; this is the cheapest way to keep the
# two lists the same length and the same keys, and it fails LOUDLY at startup rather than
# shipping a KPI that silently measures nothing.
assert set(DERIVED_RESOLVERS) == {key for key, _ in SupplierKpi.DERIVED_METRIC_CHOICES}, (
    "DERIVED_RESOLVERS and SupplierKpi.DERIVED_METRIC_CHOICES have drifted apart — every metric "
    "key must have a reviewed resolver and every resolver must have a metric key.")


# --------------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------------

def applicable_kpis(tenant, party):
    """Active KPIs that apply to this supplier, in ``display_order, code``.

    Every ``applies_to="all"`` KPI, plus the ``applies_to="tier"`` ones whose tier matches the
    supplier's ``scm.SupplierProfile.tier``. **A party with no profile gets only the ``all``
    KPIs** — guessing a tier for an unprofiled supplier would measure it against a standard
    nobody agreed to. Two queries, never one per KPI.
    """
    from apps.scm.models import SupplierProfile

    tier = (SupplierProfile.objects.filter(tenant=tenant, party=party)
            .values_list("tier", flat=True).first() or "")
    applies = Q(applies_to="all")
    if tier:
        applies |= Q(applies_to="tier", applies_to_tier=tier)
    return list(SupplierKpi.objects.filter(tenant=tenant, is_active=True).filter(applies)
                .order_by("display_order", "code"))


def resolve_derived(tenant, party, metric, start, end):
    """Dispatch into :data:`DERIVED_RESOLVERS`. An unknown key returns ``(None, {...})``.

    It does not raise: a KPI naming a metric this module has never heard of is a definition
    problem, and it must not take a whole generate run down with it.
    """
    resolver = DERIVED_RESOLVERS.get(metric)
    if resolver is None:
        return None, {"metric": metric, "error": "no resolver",
                      "window": [str(start), str(end)], "rows": 0}
    return resolver(tenant, party, start, end)


def survey_aggregate(tenant, party, kpi, start, end):
    """``(Decimal | None, int, dict)`` — the importance-weighted mean of the 360 responses.

    Only **submitted, internal** responses against this KPI, this supplier and a ``period_end``
    inside the window count. Weight is the respondent's ``importance``: a rating filed with
    importance 0 contributes NOTHING to the mean but is still counted as a respondent, so the
    page can say "8 people answered" honestly while only 6 of them moved the number.

    Returns ``(None, 0, …)`` when nothing qualifies — never a phantom zero.
    """
    # Forward reference to this sub-module's Entity-3 model module. Imported here rather than at
    # module top for the same reason as the sibling-app reads: this package's __init__ re-export
    # block lands at Integrate, and the entity modules land one at a time before it.
    from apps.procurement.models.SupplierPerformanceEvaluation.SupplierFeedback import (
        SupplierFeedback)

    rows = list(SupplierFeedback.objects.filter(
        tenant=tenant, supplier=party, kpi=kpi, status="submitted",
        respondent_kind="internal", period_end__range=(start, end)))
    if not rows:
        return None, 0, {"source": "360 survey", "window": [str(start), str(end)],
                         "respondents": 0, "weighted_respondents": 0,
                         "note": "No submitted internal responses for this KPI in the period."}

    weighted_sum, weight_total, counted = ZERO, 0, 0
    for row in rows:
        value = row.score_value()
        if value is None:
            continue
        weighted_sum += value * row.importance
        weight_total += row.importance
        counted += 1
    breakdown = {"source": "360 survey", "window": [str(start), str(end)],
                 "respondents": len(rows), "weighted_respondents": counted,
                 "weight_total": weight_total,
                 "note": "Ratings converted to 0-100 (1 = 0 … 5 = 100) and weighted by each "
                         "respondent's importance."}
    if not weight_total:
        # Everybody who answered was filed at importance 0. There is no weighted mean to take,
        # and averaging them unweighted would silently invent a weighting nobody chose.
        breakdown["note"] = ("Every response was filed at importance 0 — there is no weighted "
                             "mean to take.")
        return None, len(rows), breakdown
    value = (weighted_sum / Decimal(weight_total)).quantize(_STEP)
    breakdown["weighted_mean"] = _num(value)
    return value, len(rows), breakdown


def period_choices(tenant):
    """Distinct scorecard ``period_end`` dates for this tenant, newest first, capped."""
    from apps.scm.models import SupplierScorecard
    return list(SupplierScorecard.objects.filter(tenant=tenant)
                .order_by("-period_end").values_list("period_end", flat=True)
                .distinct()[:PERIOD_CAP])


@transaction.atomic
def generate_scorecard_lines(scorecard, user):
    """Write one ``SupplierKpiScore`` per applicable KPI onto this scorecard. THE one-way door.

    **Generating hands the scorecard permanently to Procurement 6.16.** The four dimension
    scores are written from the KPI lines, ``manual_override`` is set, and SCM's signal engine
    (``scm.SupplierScorecard.recompute_from_signals()``) returns immediately on any row carrying
    that flag from then on. This is deliberate — two engines writing the same four columns would
    fight, and the one with an auditable KPI line behind every figure should win — but it CANNOT
    be undone from here. See :data:`HANDOVER_NOTE`, which the view, the button and the page all
    print.

    **Safe to press twice.** ``SupplierKpiScore`` is unique on ``(tenant, scorecard, kpi)`` and
    the run reuses the ``existing`` lines it already fetched, so a second press refreshes the
    figures in place instead of doubling them.

    **Two write round-trips, not four per line** — one ``bulk_update`` and one ``bulk_create``,
    whatever the size of the KPI catalogue.

    **Refuses on anything but a draft**, writing nothing: a published or archived scorecard is a
    closed period, and silently rewriting one would change a number somebody has already acted
    on.

    **Refuses an empty run too**, writing nothing: with no applicable KPI there is no measurement
    to hand over, and setting ``manual_override`` on the strength of nothing would take SCM's
    signal engine off a scorecard it was scoring perfectly well.

    **History is frozen at write time.** ``weight_applied``, ``target_at_time``,
    ``direction_at_time``, ``source_at_time``, ``unit_at_time``, ``kpi_name`` and
    ``kpi_category`` are copied onto the line, so re-tuning or renaming a KPI later changes the
    next period and leaves closed ones exactly as they were read.

    Returns ``{"refused", "refusal_reason", "written", "skipped", "dimensions", "alerts"}``. The
    VIEW — not this function — writes the audit log and emits the messages.
    """
    from apps.procurement.models.DashboardPortal.ProcurementAlerts import ProcurementAlert

    if scorecard.status != "draft":
        return {"refused": True,
                "refusal_reason": (f"A {scorecard.get_status_display().lower()} scorecard is "
                                   "closed — only a draft may be generated onto."),
                "written": 0, "skipped": 0, "dimensions": {}, "alerts": 0}

    tenant = scorecard.tenant
    start, end = scorecard.period_start, scorecard.period_end
    kpis = applicable_kpis(tenant, scorecard.party)

    # REFUSES an empty run, and this guard is load-bearing. Setting ``manual_override`` below
    # stops ``recompute_from_signals()`` for good, so a run that writes NO line would hand the
    # scorecard to 6.16 with zero evidence AND take SCM's engine off it — a card that graded
    # A/93.70 from signals becomes permanently unscoreable by either engine, and the operator is
    # told it worked. Two paths reach here with no applicable KPI and neither needs an empty
    # library: a supplier with no ``scm.SupplierProfile`` while the KPIs are tier-scoped, and a
    # library mid-retune with everything deactivated. Refusing writes nothing at all, which is
    # the same answer a published scorecard gets.
    if not kpis:
        return {"refused": True,
                "refusal_reason": (
                    "No active KPI applies to this supplier, so there is nothing to generate. "
                    "Generating an empty scorecard would hand it to Procurement with no "
                    "measurement behind it and stop SCM's signal engine from scoring it at all. "
                    "Activate a KPI — or one that applies to this supplier's tier — first."),
                "written": 0, "skipped": 0, "dimensions": {}, "alerts": 0}

    # Snapshot the bands already on the scorecard BEFORE anything is rewritten. This is what
    # makes "a NEW critical crossing" mean something — a KPI that was already critical last run
    # must not raise the same alert again every time somebody presses the button.
    existing = {row.kpi_id: row for row in
                SupplierKpiScore.objects.filter(tenant=tenant, scorecard=scorecard)}
    previous = {kpi_id: row.band for kpi_id, row in existing.items()}

    author = user if getattr(user, "is_authenticated", False) else None
    now = timezone.now()
    written, skipped, crossings = 0, 0, []
    dimension_parts = defaultdict(list)
    # TWO round-trips for the whole run instead of four PER LINE. ``update_or_create`` was
    # costing a SAVEPOINT + SELECT + UPDATE + RELEASE each time round — 39 of the 54 queries a
    # 9-KPI run made were write plumbing, and it grew at ~7 queries per extra KPI. ``existing``
    # is already fetched above, so the loop knows which lines exist without asking again.
    to_create, to_update = [], []

    for kpi in kpis:
        respondents = 0
        if kpi.source == "derived":
            measured, breakdown = resolve_derived(
                tenant, scorecard.party, kpi.derived_metric, start, end)
        elif kpi.source == "survey":
            measured, respondents, breakdown = survey_aggregate(
                tenant, scorecard.party, kpi, start, end)
        else:
            # Manual: the figure is a human's, so generate NEVER overwrites it. Re-use whatever
            # is on the existing line; a brand-new manual line is written empty and waits.
            prior = existing.get(kpi.pk)
            measured = prior.measured_value if prior is not None else None
            breakdown = (dict(prior.breakdown) if prior is not None and prior.breakdown
                         else {"source": "manual entry",
                               "note": "awaiting a hand-entered value"})

        score, band = kpi.score_and_band(measured)
        if measured is None:
            skipped += 1

        values = {
            "measured_value": measured,
            "score": score,
            "band": band,
            # Frozen-at-time columns — a later retune or rename must not rewrite history.
            "weight_applied": kpi.weight,
            "target_at_time": kpi.target_value,
            "direction_at_time": kpi.direction,
            "source_at_time": kpi.source,
            "unit_at_time": kpi.unit,
            "kpi_name": kpi.name,
            "kpi_category": kpi.category,
            "breakdown": breakdown,
            "respondent_count": respondents,
            "computed_at": now,
            "computed_by": author,
            # Stamped by hand because bulk_update skips auto_now — see :data:`_LINE_FIELDS`.
            "updated_at": now,
        }

        line = existing.get(kpi.pk)
        if line is None:
            line = SupplierKpiScore(tenant=tenant, scorecard=scorecard, kpi=kpi, **values)
            to_create.append(line)
        else:
            for column, value in values.items():
                setattr(line, column, value)
            to_update.append(line)
        written += 1

        if kpi.maps_to_dimension and score is not None:
            dimension_parts[kpi.maps_to_dimension].append((score, kpi.weight))
        if band == "critical" and previous.get(kpi.pk) != "critical":
            crossings.append(line)

    # One UPDATE and one INSERT for the whole run. ``unique_together`` still guards the second
    # press: an existing line is UPDATED in place because it came out of ``existing``, so
    # nothing here can double a scorecard.
    if to_update:
        SupplierKpiScore.objects.bulk_update(to_update, _LINE_FIELDS)
    if to_create:
        SupplierKpiScore.objects.bulk_create(to_create)

    # The four scm columns: a weighted mean by the frozen weight where several KPIs feed one
    # dimension. A dimension whose mapped KPIs all came back unscored is LEFT UNTOUCHED — never
    # overwritten with a phantom zero, the same rule recompute_from_signals follows.
    dimensions = {}
    written_fields = []
    for name, field in DIMENSION_FIELDS.items():
        parts = dimension_parts.get(name) or []
        weight_total = sum(weight for _, weight in parts)
        if not weight_total:
            dimensions[name] = None
            continue
        blended = (sum(score * weight for score, weight in parts)
                   / Decimal(weight_total)).quantize(_STEP)
        dimensions[name] = blended
        setattr(scorecard, field, blended)
        written_fields.append(field)

    scorecard.manual_override = True
    scorecard.save(update_fields=[*written_fields, "manual_override", "updated_at"])
    # Default save=True — overall_score and grade follow the four columns just written.
    scorecard.recompute_overall()

    # One INSERT for every crossing rather than one per alert — same shape as the score lines
    # above, and crossings are usually few but are not bounded.
    new_alerts = [
        ProcurementAlert(
            tenant=tenant, kind="task", severity="critical",
            title=f"{scorecard.party.name} — {line.kpi_name} is critical",
            message=(f"{line.kpi_name} came back at "
                     f"{line.measured_value if line.measured_value is not None else '—'} for "
                     f"the period ending {end}, crossing the critical line on scorecard "
                     f"{scorecard.number}."),
            # An INTERNAL path with a single leading slash — ProcurementAlert.clean() rejects
            # anything else, and an absolute URL here would make the alert card an open redirect.
            link_url=f"/procurement/supplier-evaluations/{scorecard.pk}/",
            created_by=author)
        for line in crossings
    ]
    if new_alerts:
        ProcurementAlert.objects.bulk_create(new_alerts)
    alerts = len(new_alerts)

    return {"refused": False, "refusal_reason": "", "written": written, "skipped": skipped,
            "dimensions": dimensions, "alerts": alerts}


def trend_series(tenant, party, kpi=None):
    """``(composite_series, kpi_series, truncated)`` — how this supplier moved, period by period.

    Two queries regardless of how many periods are in the window: one for the scorecards, one
    for every KPI line across all of them (``scorecard_id__in=…``), never one query per period.
    """
    from apps.scm.models import SupplierScorecard

    cards = list(SupplierScorecard.objects.filter(tenant=tenant, party=party)
                 .order_by("-period_end", "-id")[:PERIOD_CAP + 1])
    truncated = len(cards) > PERIOD_CAP
    cards = list(reversed(cards[:PERIOD_CAP]))          # oldest -> newest, as a trend reads
    if not cards:
        return [], [], False

    lines_qs = (SupplierKpiScore.objects
                .filter(tenant=tenant, scorecard_id__in=[card.pk for card in cards])
                .select_related("kpi"))
    if kpi is not None:
        lines_qs = lines_qs.filter(kpi=kpi)
    by_card = defaultdict(list)
    for line in lines_qs:
        by_card[line.scorecard_id].append(line)

    series, previous_composite = [], None
    for card in cards:
        lines = by_card.get(card.pk, [])
        composite = _composite(lines)
        delta = (composite - previous_composite
                 if composite is not None and previous_composite is not None else None)
        series.append({"period_end": card.period_end, "period_start": card.period_start,
                       "scorecard_id": card.pk, "scorecard_number": card.number,
                       "composite": composite, "overall": card.overall_score,
                       "grade": card.grade, "delta": delta, "line_count": len(lines)})
        if composite is not None:
            previous_composite = composite

    # Per-KPI series, in the same period order. Points are appended card by card, so a KPI that
    # only appears in some periods still reads left to right.
    buckets, order = {}, []
    for card in cards:
        for line in by_card.get(card.pk, []):
            if line.kpi_id not in buckets:
                buckets[line.kpi_id] = {
                    "kpi_id": line.kpi_id,
                    "kpi_code": line.kpi.code if line.kpi_id else "",
                    "kpi_name": line.kpi_name or (line.kpi.name if line.kpi_id else ""),
                    "kpi_category": line.kpi_category,
                    "unit": line.unit_at_time,
                    "direction": line.direction_at_time,
                    "points": []}
                order.append(line.kpi_id)
            bucket = buckets[line.kpi_id]
            prior = next((point["measured_value"] for point in reversed(bucket["points"])
                          if point["measured_value"] is not None), None)
            delta = (line.measured_value - prior
                     if line.measured_value is not None and prior is not None else None)
            bucket["points"].append({
                "period_end": card.period_end,
                "measured_value": line.measured_value,
                "score": line.score,
                "band": line.band,
                "band_css": line.band_css,
                "target_at_time": line.target_at_time,
                "meets_target": meets_target(line),
                "delta": delta})
    return series, [buckets[kpi_id] for kpi_id in order], truncated


def _composite(lines):
    """The weighted mean of ``score`` by ``weight_applied``, or ``None`` when nothing scored.

    Weights are re-weighted over the lines that ACTUALLY scored, so a KPI with no data in the
    period does not quietly drag the composite down — the same rule
    ``SupplierScorecard.recompute_overall()`` applies to its four dimensions.
    """
    scored = [(line.score, line.weight_applied) for line in lines if line.score is not None]
    weight_total = sum(weight for _, weight in scored)
    if not weight_total:
        return None
    return (sum(score * weight for score, weight in scored)
            / Decimal(weight_total)).quantize(_STEP)


def meets_target(line):
    """``True`` / ``False`` / ``None`` — did the measured value reach the target it was read at?

    ``None`` when either side is missing: a KPI with no target has nothing to meet, and saying
    "False" would read as a failure the definition never asked for. Read through the FROZEN
    ``direction_at_time`` / ``target_at_time``, so flipping a KPI's direction later cannot
    re-judge a closed period.
    """
    if line.measured_value is None or line.target_at_time is None:
        return None
    if line.direction_at_time == "lower_is_better":
        return line.measured_value <= line.target_at_time
    return line.measured_value >= line.target_at_time


def _composite_from_sums(weighted_score, weight_total):
    """:func:`_composite`'s arithmetic over two SQL ``SUM``s instead of over fetched rows.

    Same inputs, same rounding, same ``None`` — the cohort's composites are aggregated in the
    database because a 500-scorecard cohort times a large KPI catalogue is a lot of rows to
    stream just to average them, but the division stays in Python so the result is Decimal-exact
    and identical to what the trend board publishes for the same scorecard.
    """
    if not weight_total or weighted_score is None:
        return None
    return (Decimal(weighted_score) / Decimal(weight_total)).quantize(_STEP)


def benchmark_rows(tenant, period_end, tier=None, category=None):
    """``(rows, cohort, truncated)`` — every supplier's composite for one period, ranked.

    Three queries total: the scorecards (with their line count and composite aggregated), the
    supplier profiles, and the risk assessments. Ranks and percentiles are one Python pass over
    the already-fetched rows — a window function per row would be one query per supplier.

    **The composite is the KPI lines' weighted mean, not ``overall_score``.** The two are
    different numbers on purpose — ``overall_score`` is SCM's blend of the four dimension
    columns, and only dimension-mapped KPIs reach it — so publishing one under the other's name
    made this board and the trend board disagree about the same supplier in the same period, and
    took rank, percentile and quadrant with it. ``overall`` rides the row beside it, exactly as
    it does on a trend point.
    """
    from apps.scm.models import SupplierProfile, SupplierRiskAssessment, SupplierScorecard

    scored = Q(procurement_kpi_scores__score__isnull=False)
    cohort_qs = (SupplierScorecard.objects
                 .filter(tenant=tenant, period_end=period_end)
                 .select_related("party")
                 .annotate(
                     line_count=Count("procurement_kpi_scores"),
                     scored_weight=Sum("procurement_kpi_scores__weight_applied", filter=scored),
                     weighted_score=Sum(
                         F("procurement_kpi_scores__score")
                         * F("procurement_kpi_scores__weight_applied"),
                         output_field=DecimalField(max_digits=20, decimal_places=4))))

    # The tier/category narrowing happens HERE, before the cap — not in the loop below. Applied
    # after the slice it filtered a truncated population: a 13-supplier cohort averaging 55.14
    # (best 95.00) displayed as 6 suppliers averaging 10.00 with a best of 10.00, because
    # ``benchmark_rows`` slices by ``party__name`` and every top performer sorted past the cut.
    # The rank, the percentile and every cohort statistic are computed over these rows, so the
    # cap must truncate the FILTERED cohort rather than the filter narrow a truncated one.
    # ``scm_supplier_profile`` is a reverse OneToOne, so joining it cannot fan the rows out and
    # the aggregates above are unaffected.
    if tier:
        cohort_qs = cohort_qs.filter(party__scm_supplier_profile__tenant=tenant,
                                     party__scm_supplier_profile__tier=tier)
    if category:
        cohort_qs = cohort_qs.filter(party__scm_supplier_profile__tenant=tenant,
                                     party__scm_supplier_profile__category=category)

    cards = list(cohort_qs.order_by("party__name", "-id")[:ROW_CAP + 1])
    truncated = len(cards) > ROW_CAP
    cards = cards[:ROW_CAP]
    if not cards:
        return [], {"count": 0, "scored": 0, "average": None, "best": None, "worst": None}, False

    party_ids = {card.party_id for card in cards}
    profiles = {party_id: (profile_tier, profile_category) for party_id, profile_tier,
                profile_category in SupplierProfile.objects
                .filter(tenant=tenant, party_id__in=party_ids)
                .values_list("party_id", "tier", "category")}

    # The most recent assessment at or before the period end, for the WHOLE cohort in ONE query.
    risk = {}
    for party_id, index in (SupplierRiskAssessment.objects
                            .filter(tenant=tenant, party_id__in=party_ids,
                                    assessment_date__lte=period_end)
                            .order_by("party_id", "-assessment_date", "-id")
                            .values_list("party_id", "risk_index")):
        risk.setdefault(party_id, index)

    tier_labels = dict(SupplierKpi.TIER_CHOICES)
    rows = []
    for card in cards:
        # No tier/category test here — the queryset above already did it, before the cap.
        card_tier, card_category = profiles.get(card.party_id, ("", ""))
        composite = _composite_from_sums(card.weighted_score, card.scored_weight)
        risk_index = risk.get(card.party_id)
        rows.append({
            "supplier_id": card.party_id,
            "supplier_name": card.party.name,
            "tier": card_tier,
            "tier_label": tier_labels.get(card_tier, ""),
            "category": card_category,
            "scorecard_id": card.pk,
            "scorecard_number": card.number,
            "composite": composite,
            # SCM's own blend, carried beside the composite rather than instead of it — the same
            # pair a trend point publishes, so a reader can see the two engines agree or not.
            "overall": card.overall_score,
            "grade": card.grade,
            "rank": 0,
            "percentile": None,
            "risk_index": risk_index,
            "quadrant": quadrant_for(composite, risk_index),
            "line_count": card.line_count,
        })

    # Best first; an unscored supplier sorts last rather than pretending to a zero.
    rows.sort(key=lambda row: (row["composite"] is None,
                               -(row["composite"] or ZERO), row["supplier_name"]))
    scored = [row for row in rows if row["composite"] is not None]
    total = len(scored)
    for index, row in enumerate(scored):
        row["rank"] = index + 1
        # Percentile rank: the share of the scored cohort this supplier is at or above.
        row["percentile"] = (Decimal(total - index) * _HUNDRED / Decimal(total)).quantize(_STEP)

    composites = [row["composite"] for row in scored]
    cohort = {"count": len(rows), "scored": total,
              "average": _mean(composites) if composites else None,
              "best": max(composites) if composites else None,
              "worst": min(composites) if composites else None}
    return rows, cohort, truncated


def quadrant_for(composite, risk_index):
    """The performance/risk segment a supplier falls in. ``""`` when either axis is missing."""
    if composite is None or risk_index is None:
        return ""
    low_risk = risk_index <= _LOW_RISK
    if composite >= 70:
        return "strategic" if low_risk else "hidden"
    return "development" if low_risk else "underperforming"


def perception_gap_rows(tenant, party, start, end):
    """``(gap_rows, truncated)`` — what the buyer thinks against what the supplier thinks.

    ONE query over the window's submitted responses, bucketed in Python by KPI and respondent
    kind. ``delta = self_avg - internal_avg``, so a POSITIVE delta means the supplier rates
    itself higher than we do — the conversation worth having.
    """
    from apps.procurement.models.SupplierPerformanceEvaluation.SupplierFeedback import (
        SupplierFeedback)

    rows = list(SupplierFeedback.objects
                .filter(tenant=tenant, supplier=party, status="submitted",
                        period_end__range=(start, end))
                .select_related("kpi")[:ROW_CAP + 1])
    truncated = len(rows) > ROW_CAP
    rows = rows[:ROW_CAP]

    buckets, order = {}, []
    for row in rows:
        key = row.kpi_id
        if key not in buckets:
            buckets[key] = {
                "kpi_id": key,
                "kpi_code": row.kpi.code if key else "—",
                "kpi_name": row.kpi.name if key else "General commentary",
                "internal": [], "self": []}
            order.append(key)
        side = "self" if row.respondent_kind == "supplier_self" else "internal"
        value = row.score_value()
        if value is not None:
            buckets[key][side].append((value, row.importance))

    gap_rows = []
    for key in order:
        bucket = buckets[key]
        internal_avg, internal_count = _weighted(bucket["internal"])
        self_avg, self_count = _weighted(bucket["self"])
        delta = (self_avg - internal_avg
                 if self_avg is not None and internal_avg is not None else None)
        gap_rows.append({"kpi_id": bucket["kpi_id"], "kpi_code": bucket["kpi_code"],
                         "kpi_name": bucket["kpi_name"],
                         "internal_avg": internal_avg, "internal_count": internal_count,
                         "self_avg": self_avg, "self_count": self_count,
                         "delta": delta, "delta_css": _delta_css(delta)})
    return gap_rows, truncated


def _weighted(pairs):
    """``(weighted_mean | None, respondent_count)`` over ``[(value, importance), …]``."""
    if not pairs:
        return None, 0
    weight_total = sum(weight for _, weight in pairs)
    if not weight_total:
        return None, len(pairs)
    total = sum(value * weight for value, weight in pairs)
    return (total / Decimal(weight_total)).quantize(_STEP), len(pairs)


def _delta_css(delta):
    """Colour-named theme classes ONLY (L33) — badge-success/-warning/-danger do not exist."""
    if delta is None:
        return "badge-slate"
    if delta >= 20:
        return "badge-red"
    if delta >= 10:
        return "badge-amber"
    if delta <= -10:
        return "badge-info"
    return "badge-green"
