"""Procurement 6.12 Goods Receipt & Inspection — the three COMPUTED receiving boards.

**Goods Receipt Note (GRN) Creation**, **Inventory Posting** and **Receipt Reversal & Audit
Trail** are the three NavERP.md bullets that describe a *view over work already in flight*, not a
new document. They are therefore rendered exactly the way 6.11's ``FulfillmentBoards.py`` renders
its two boards: read-only pages over rows that already exist, with **zero new state and zero
migration impact**. There is no ``models/GoodsReceiptInspection/ReceiptBoards.py`` — this lane
declares no table at all.

Three decisions worth recording, because a reviewer will otherwise go looking for the missing
tables and the missing verbs:

* **The receiving console books a DRAFT ``scm.GoodsReceiptNote`` and stops there.** Booking the
  stock is ``scm:goodsreceipt_receive`` and it stays SCM's verb (L36) — one writer for the
  inventory ledger and one writer for the GL. Writing a draft receipt from here is the 6.1 Quick
  Requisition Entry precedent (that page drafts into ``scm.PurchaseRequisition`` the same way).
  The console's value is the *pre-arrival* picture the dock cannot get anywhere else: what the
  supplier declared, against what was ordered, against what has already been received, judged by
  the tolerance policy and routed by the QC rule — all before anybody signs for the pallet.
* **The tolerance board FLAGS, it never BLOCKS.** ``ReceiptTolerancePolicy.action ==
  "block_flag"`` marks a line as blocking-severity; nothing in 6.12 gates
  ``scm:goodsreceipt_receive``. A second gate would give the workspace two answers to "can this be
  received?".
* **The audit board reads the append-only trail and adds nothing to it.** ``goodsreceiptnote`` is
  already in ``_helpers.PROCUREMENT_CONTENT_MODELS`` and every ``app_label="procurement"`` row is
  already included, so this page is a NARROWING of ``procurement_activity_qs`` — it does not edit
  that tuple and it does not keep a second trail.

All five views are tenant-scoped and all five open with the tenant-``None`` guard: the superuser
carries ``tenant=None`` by design, and an unexplained empty board is worse than a message saying
which workspace to pick.

**Pagination is hand-rolled here rather than delegated to ``crud_list``**, and that is the one
deliberate structural difference from the 6.11 boards. Each of these pages renders a DERIVED row
list (``rows`` / ``entries``) computed from the page's objects, and ``crud_list`` renders the
response itself — there is no seam at which the page's objects can be read back. The context keys
it would have produced (``object_list`` / ``page_obj`` / ``q``) are emitted verbatim, and search
and the int-FK guard go through the same ``apply_search`` / ``as_db_int`` helpers ``crud_list``
uses, so the pages behave identically to every other register in the app (the
``RequisitionManagement/Requisitions.py`` precedent).
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Lower, Trim
from django.urls import reverse
from django.utils.http import urlencode

from apps.core.crud import apply_search, as_db_int, paginate
from apps.core.models import AuditLog
from apps.inventory.models import QcRoutingRule, resolve_qc_routing
from apps.procurement.forms import ReceivingConsoleBookForm
from apps.procurement.models import (
    AdvancedShipmentNotice, ReceiptDiscrepancy, ReceiptTolerancePolicy, ReturnToVendor,
    evaluate_receipt_tolerance, resolve_line_item, resolve_receipt_tolerance,
)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import ACTIVITY_FEED_NOTE, procurement_activity_qs
from apps.scm.models import (
    GoodsReceiptLine, GoodsReceiptNote, Item, Location, LotSerial, PurchaseOrder,
    PurchaseOrderLine,
)

ZERO = Decimal("0")

#: Every board pages 30 rows, matching the audit-trail convention the 6.1 activity feed set.
BOARD_PER_PAGE = 30

#: Which ASNs the receiving console is ABOUT: declared and on the way, plus the ones the dock has
#: already confirmed as arrived but nobody has booked a receipt for yet. A draft ASN is not a
#: commitment and a cancelled one is not arriving, so neither belongs on an arrivals board.
CONSOLE_STATUSES = tuple(AdvancedShipmentNotice.IN_FLIGHT_STATUSES) + ("delivered",)

#: Arrival tabs. Sanitized against this list, so ``?arrival=zzz`` is ignored and echoed back empty
#: rather than 500ing on an unknown branch.
ARRIVAL_CHOICES = [
    ("today", "Arriving today"),
    ("overdue", "Overdue"),
    ("awaiting", "Awaiting arrival"),
]
_ARRIVAL_KEYS = {key for key, _label in ARRIVAL_CHOICES}

#: How far back the console's "booked" stat tile looks.
BOOKED_WINDOW_DAYS = 7

#: Exception buckets. Unknown values fall back to the first one, so the board is always a 200.
BUCKET_CHOICES = [
    ("over", "Over-receipt"),
    ("short", "Under-receipt"),
    ("early", "Early"),
    ("late", "Late"),
]
_BUCKET_KEYS = {key for key, _label in BUCKET_CHOICES}
DEFAULT_BUCKET = "over"

#: Which audit content types the receipt trail is about — the 6.12 register plus the SCM receipt
#: it hangs off. A NARROWING of procurement_activity_qs, never an edit to its whitelist.
RECEIPT_AUDIT_MODELS = (
    "goodsreceiptnote",
    "receipttolerancepolicy",
    "receiptdiscrepancy",
    "returntovendor",
)

#: Ceiling on how many distinct (sku, vendor) groups the "no policy" tile resolves. Ordered by
#: group size so the biggest configuration gaps are always counted; on a workspace with more
#: variety than this the tile reads as a LOWER BOUND, which is the safe direction for a warning.
_COVERAGE_CAP = 1000

#: Precedence used to fold a shipment's per-line verdicts into ONE headline verdict for its row.
#: Quantity breaches outrank date breaches (the same rule ``evaluate_receipt_tolerance`` applies
#: within a line), and "no policy" is the weakest signal — a covered line that came out clean is
#: better news than an uncovered one.
_VERDICT_PRECEDENCE = ("over", "short", "late", "early", "ok", "no_rule")

#: Which discrepancy kind a one-click "Raise discrepancy" link pre-fills, per verdict. Verdicts
#: with no natural kind simply omit the parameter — the create form then asks for it.
_VERDICT_KIND = {
    "over": "over_shipment",
    "short": "short_shipment",
    "late": "late_delivery",
}


# -- shared helpers --------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors @tenant_admin_required exactly, so a hidden button and a refused POST agree.

    The local-copy convention every 6.12 lane follows (``ReceiptTolerances`` and
    ``ReturnsToVendor`` each carry the same three lines).
    """
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _tenant_guard(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty board."""
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _supplier_parties(tenant):
    """Supplier/vendor-role parties for the ``?vendor=`` widgets.

    A LOCAL copy, matching the convention every other procurement sub-module follows — peer
    modules mirror this helper rather than importing each other's private names.
    """
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _purchase_orders(tenant):
    if tenant is None:
        return PurchaseOrder.objects.none()
    return PurchaseOrder.objects.filter(tenant=tenant).order_by("-order_date", "-id")[:200]


def _receipts(tenant):
    if tenant is None:
        return GoodsReceiptNote.objects.none()
    return (GoodsReceiptNote.objects.filter(tenant=tenant)
            .select_related("purchase_order").order_by("-receipt_date", "-id")[:200])


def _locations(tenant):
    if tenant is None:
        return Location.objects.none()
    return Location.objects.filter(tenant=tenant, is_active=True).order_by("code")


def _norm(value):
    """Whitespace-collapsed, case-folded key for the free-text joins this module lives on."""
    return " ".join((value or "").split()).lower()


def _tolerance_rules(tenant):
    """The active tolerance policies, fetched ONCE per request and passed to every resolve call.

    ``resolve_receipt_tolerance`` re-filters a caller-supplied list by tenant before using it, so
    handing it round is a performance decision, never a trust one.
    """
    return list(ReceiptTolerancePolicy.objects.filter(tenant=tenant, is_active=True)
                .select_related("item", "category", "vendor").order_by("priority", "id"))


def _qc_rules(tenant):
    """The active QC routing rules — same once-per-request discipline as the tolerance list."""
    return list(QcRoutingRule.objects.filter(tenant=tenant, is_active=True)
                .select_related("item", "category", "vendor", "qc_location")
                .order_by("priority", "id"))


def _item_map(tenant, skus):
    """``{normalised sku: Item}`` for the SKU hints on one page — ONE **bounded** query.

    GRN and PO lines are FREE TEXT (no item FK anywhere on the receiving spine), so every
    item-level feature in 6.12 goes through ``sku_hint``. Batched here rather than calling
    ``resolve_line_item`` per row, which is an N+1 on exactly the pages this module is about.

    The match is made in SQL — ``Lower(Trim(sku))`` against the page's ~30 keys, the shape
    ``_governed_lines`` already uses (ReceiptTolerances.py) — not by reading the whole item master
    into Python: ``tolerance_exceptions`` calls this helper twice per render, and a 20k-item
    catalogue meant 40k rows materialised for a page that needs thirty of them.

    The returned rows are still re-keyed through ``_norm``, so the dict's whitespace-collapsing
    semantics are unchanged. The one case SQL cannot reproduce is a sku with *internal* repeated
    whitespace (``"AB  C"``), which no longer matches ``"ab c"`` — that is strictly CLOSER to
    ``resolve_line_item``'s canonical ``sku__iexact``, which never collapsed it either.

    ``tenant`` is joined in because ``resolve_qc_routing`` reads ``item.tenant`` on every call —
    without it, a page of distinct SKUs costs one extra query per item.
    """
    skus = {sku for sku in skus if sku}
    if tenant is None or not skus:
        return {}
    found = {}
    for item in (Item.objects.filter(tenant=tenant)
                 .select_related("category", "tenant")
                 .annotate(lower_sku=Lower(Trim("sku")))
                 .filter(lower_sku__in=skus)):
        key = _norm(item.sku)
        if key in skus and key not in found:
            found[key] = item
    return found


def _received_by_po_line(tenant, po_line_ids):
    """``{po_line_id: accepted quantity}`` for the ordered lines on ONE page — one grouped query.

    ``PurchaseOrder.received_by_line()`` answers this for a SINGLE order, so calling it inside the
    per-shipment loop meant a console page of 30 shipments from 30 different orders issued 30
    separate GROUP BY aggregates — the dominant cost of the page, and one that grew with the page.
    Keying on the PO line pk (globally unique) rather than nesting under the order keeps the
    lookup in the loop a plain dict hit.

    Same rule as the model's version, deliberately: a cancelled receipt never counts, and a line
    with no receipts at all sums to NULL and falls back to ZERO.
    """
    if not po_line_ids:
        return {}
    rows = (PurchaseOrderLine.objects
            .filter(id__in=po_line_ids, purchase_order__tenant=tenant)
            .annotate(received=Sum(
                "receipt_lines__quantity_received",
                filter=~Q(receipt_lines__goods_receipt__status="cancelled")))
            .values_list("id", "received"))
    return {pk: (received or ZERO) for pk, received in rows}


def _console_reference(asn):
    """The delivery-note key ONE shipment books under — the single definition of that key.

    ``supplier_reference`` is ``blank=True`` on the ASN and optional on the 6.11 form, so it
    cannot be the sole key. When it was blank the book verb skipped its existing-receipt check
    entirely, wrote ``delivery_note_ref=""``, and the Booked marker (which drops blank keys) could
    never light up — so the row read "Not booked yet" for ever and every re-click minted another
    draft receipt, burning another GRN number against the same order. Falling back to the ASN
    number gives every shipment a stable key, and the verb and the marker share this one helper
    so they cannot disagree about what it is.
    """
    return (asn.supplier_reference or "").strip() or asn.number


def _receipt_by_delivery_ref(tenant, asn_qs):
    """``{normalised delivery-note ref: GoodsReceiptNote}`` for the ASNs on this board.

    The ASN -> GRN hand-off is ``AdvancedShipmentNotice.supplier_reference`` ->
    ``GoodsReceiptNote.delivery_note_ref`` — the one data hook 6.11 declared for exactly this
    purpose. Two queries total (the refs, then the receipts carrying them), regardless of how many
    shipments are on the board. A cancelled receipt does not count: its delivery note is free
    again, and the console must offer to re-book it.

    BOTH keys a shipment can be booked under are looked up — its supplier reference and its own
    number (see ``_console_reference``) — so a receipt booked while the reference was blank is
    still recognised if the reference is filled in afterwards.
    """
    refs = []
    for supplier_reference, number in asn_qs.values_list("supplier_reference", "number"):
        supplier_reference = (supplier_reference or "").strip()
        if supplier_reference:
            refs.append(supplier_reference)
        if number:
            refs.append(number)
    if not refs:
        return {}
    found = {}
    for receipt in (GoodsReceiptNote.objects
                    .filter(tenant=tenant, delivery_note_ref__in=refs)
                    .exclude(status="cancelled")
                    .select_related("purchase_order").order_by("id")):
        key = _norm(receipt.delivery_note_ref)
        # Earliest wins: that is the row the idempotent book verb would hand back.
        if key and key not in found:
            found[key] = receipt
    return found


def _fold_verdicts(verdicts):
    """The headline verdict for a shipment from its lines' verdicts (see _VERDICT_PRECEDENCE)."""
    for candidate in _VERDICT_PRECEDENCE:
        if candidate in verdicts:
            return candidate
    return "no_rule"


def _verdict_css(verdict):
    return ReceiptTolerancePolicy.VERDICT_CSS.get(verdict, "badge-muted")


# -- Receiving console ------------------------------------------------------------------------

@login_required
def receiving_console(request):
    """The dock's pre-arrival worklist — every declared shipment, judged before it lands.

    Read-only: the two write verbs (book a draft receipt, mint declared lots) are separate
    POST-only routes, each with its own row lock.
    """
    guard = _tenant_guard(request, "use the receiving console")
    if guard is not None:
        return guard

    tenant = request.tenant
    today = timezone.localdate()
    base = AdvancedShipmentNotice.objects.filter(tenant=tenant, status__in=CONSOLE_STATUSES)

    # The three arrival predicates, defined ONCE and reused for both the tabs and the stat tiles,
    # so a tile can never disagree with the list it links to.
    arrival_q = {
        "today": Q(expected_delivery_date=today),
        "overdue": Q(expected_delivery_date__lt=today),
        "awaiting": (Q(expected_delivery_date__gt=today)
                     | Q(expected_delivery_date__isnull=True)),
    }

    # ONE aggregate over the UNFILTERED tenant queryset, off the bare manager: the tiles describe
    # the workspace, not the current filter. (Built before select_related so a whole-tenant COUNT
    # does not drag joins it never reads.)
    totals = base.aggregate(
        awaiting=Count("id", filter=arrival_q["awaiting"]),
        arrived_today=Count("id", filter=arrival_q["today"]),
        overdue=Count("id", filter=arrival_q["overdue"]),
    )

    # A workspace-level COUNT, exactly like the three tiles above it — NOT a Python fold over a
    # dict of every receipt the whole board could possibly match. The old shape built that dict
    # from the unfiltered, unpaginated queryset on every page load (an unbounded IN list) purely
    # to `sum()` over it; the row marker below now builds its own map from the PAGE instead.
    booked_cutoff = timezone.now() - timedelta(days=BOOKED_WINDOW_DAYS)
    booked_7d = (GoodsReceiptNote.objects
                 .filter(tenant=tenant, created_at__gte=booked_cutoff)
                 .exclude(status="cancelled")
                 .filter(delivery_note_ref__in=Subquery(
                     base.exclude(supplier_reference="")
                         .order_by().values("supplier_reference")))
                 .count())

    qs = base.select_related("purchase_order", "purchase_order__vendor")

    # ?arrival= is date arithmetic against today, not a GET-value comparison, so it is applied
    # HERE as an ORM predicate — before pagination. A Python-side narrowing would filter the PAGE
    # and make every count and page number describe a different set of rows than the one on
    # screen (the 6.11 backorder-risk lesson).
    arrival = request.GET.get("arrival", "").strip()
    if arrival in _ARRIVAL_KEYS:
        qs = qs.filter(arrival_q[arrival])
    else:
        arrival = ""

    q = request.GET.get("q", "").strip()
    qs = apply_search(qs, q, ["number", "supplier_reference", "purchase_order__number"])

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)
    vendor_pk = as_db_int(request.GET.get("vendor", ""))
    if vendor_pk is not None:
        qs = qs.filter(purchase_order__vendor_id=vendor_pk)
    po_pk = as_db_int(request.GET.get("po", ""))
    if po_pk is not None:
        qs = qs.filter(purchase_order_id=po_pk)

    page_obj = paginate(
        request,
        qs.prefetch_related("lines", "lines__po_line").order_by("expected_delivery_date", "-id"),
        per_page=BOARD_PER_PAGE,
    )
    shipments = list(page_obj.object_list)

    # Built from the PAGE, so both queries carry an IN list of at most BOARD_PER_PAGE refs.
    # Earliest-wins keying is preserved — the map is still assembled in ``id`` order.
    receipt_by_ref = _receipt_by_delivery_ref(
        tenant, base.filter(pk__in=[asn.pk for asn in shipments]))

    return render(request, "procurement/goodsreceiptinspection/receiving_console.html", {
        "object_list": shipments,
        "page_obj": page_obj,
        "q": q,
        "rows": _console_rows(tenant, shipments, receipt_by_ref),
        # Only the statuses this board can actually show: the queryset is hard-limited to
        # CONSOLE_STATUSES, so offering Draft / Cancelled would be two options that silently
        # return an empty board.
        "status_choices": [(value, label)
                           for value, label in AdvancedShipmentNotice.STATUS_CHOICES
                           if value in CONSOLE_STATUSES],
        "vendors": _supplier_parties(tenant),
        "purchase_orders": _purchase_orders(tenant),
        "locations": _locations(tenant),
        "arrival": arrival,
        "arrival_choices": ARRIVAL_CHOICES,
        # ``receiving_console_mint_lots`` is @tenant_admin_required, so a member must not be
        # offered the button — the decorator raises PermissionDenied and the click dead-ends on a
        # hard 403 page. The BOOK form is deliberately NOT gated on this: that verb is
        # @login_required only and must stay member-visible.
        "can_mint": _is_admin(request),
        "stats": {
            "awaiting": totals["awaiting"],
            "arrived_today": totals["arrived_today"],
            "overdue": totals["overdue"],
            "booked_7d": booked_7d,
        },
    })


def _console_rows(tenant, shipments, receipt_by_ref):
    """One derived row per shipment on the page, with its lines already judged.

    Fixed query cost regardless of page size: the tolerance rules, the QC rules, the SKU map and
    the received-per-ordered-line aggregate are each fetched ONCE for the whole page — never
    ``po_line.received_quantity()`` inside the loop (one aggregate per line), and no longer
    ``PurchaseOrder.received_by_line()`` per distinct order either, which on a page of 30
    shipments from 30 orders was 30 GROUP BYs.
    """
    if not shipments:
        return []

    rules = _tolerance_rules(tenant)
    qc_rules = _qc_rules(tenant)

    lines_by_asn = {asn.pk: list(asn.lines.all()) for asn in shipments}
    item_map = _item_map(
        tenant,
        {_norm(line.sku_hint or (line.po_line.sku_hint if line.po_line_id else ""))
         for lines in lines_by_asn.values() for line in lines},
    )
    # ONE aggregate for the whole page, not one per distinct order.
    received_map = _received_by_po_line(
        tenant,
        {line.po_line_id for lines in lines_by_asn.values() for line in lines
         if line.po_line_id},
    )

    rows = []
    for asn in shipments:
        order = asn.purchase_order
        vendor = getattr(order, "vendor", None)

        line_rows, verdicts, qc_verdicts = [], set(), []
        headline_reason, qc_reason, qc_location = "", "", None
        for line in lines_by_asn[asn.pk]:
            po_line = line.po_line if line.po_line_id else None
            sku = line.sku_hint or (po_line.sku_hint if po_line else "")
            item = item_map.get(_norm(sku))
            category = getattr(item, "category", None)

            declared = line.quantity_shipped or ZERO
            ordered = (po_line.quantity if po_line else ZERO) or ZERO
            received = received_map.get(line.po_line_id) or ZERO
            outstanding = ordered - received

            rule, reason = resolve_receipt_tolerance(
                item, vendor, tenant=tenant, category=category, rules=rules)
            # Judged on the POST-RECEIPT position: what the cumulative figure WOULD be if the
            # dock accepted everything the supplier declared. That is the question a console
            # answers — the breach has not happened yet, and saying so before the pallet is
            # signed for is the whole point of an ASN.
            verdict, verdict_reason = evaluate_receipt_tolerance(
                rule,
                ordered_quantity=ordered,
                received_quantity=received + declared,
                expected_date=getattr(order, "expected_date", None),
                receipt_date=asn.expected_delivery_date,
            )
            verdicts.add(verdict)
            if verdict != "ok" and not headline_reason:
                headline_reason = verdict_reason or reason

            qc_rule, qc_line_verdict, qc_line_location, qc_line_reason = resolve_qc_routing(
                item, vendor, rules=qc_rules, category=category)
            if qc_line_verdict:
                qc_verdicts.append(qc_line_verdict)
                if qc_line_verdict == "inspect" and qc_location is None:
                    qc_location = qc_line_location
                if not qc_reason:
                    qc_reason = qc_line_reason
            elif not qc_reason:
                qc_reason = qc_line_reason

            line_rows.append({
                "asn_line": line,
                "po_line": po_line,
                "description": line.item_description or (po_line.item_description
                                                         if po_line else ""),
                "sku_hint": sku,
                "uom_hint": line.uom_hint or (po_line.uom_hint if po_line else ""),
                "declared": declared,
                "ordered": ordered,
                "received": received,
                "outstanding": outstanding,
                "verdict": verdict,
                "verdict_reason": verdict_reason,
                "verdict_css": _verdict_css(verdict),
                "lot_number": line.lot_number,
                "serial_number": line.serial_number,
                "expiry_date": line.expiry_date,
            })

        headline = _fold_verdicts(verdicts) if verdicts else "no_rule"
        if headline == "ok":
            headline_reason = headline_reason or "Every declared line is within tolerance."
        elif headline == "no_rule":
            headline_reason = headline_reason or "No policy covers this shipment."

        # One shipment inspects if ANY of its lines does — a pallet cannot half-detour through
        # the QC zone.
        qc_verdict = ("inspect" if "inspect" in qc_verdicts
                      else ("bypass" if qc_verdicts else None))

        # Either key: the supplier's own reference, or — for a shipment that declared none — the
        # ASN number the book verb falls back to.
        existing_receipt = (receipt_by_ref.get(_norm(asn.supplier_reference))
                            or receipt_by_ref.get(_norm(asn.number)))
        rows.append({
            "asn": asn,
            "order": order,
            "vendor": vendor,
            "lines": line_rows,
            "tolerance_verdict": headline,
            "tolerance_reason": headline_reason,
            "tolerance_css": _verdict_css(headline),
            "qc_verdict": qc_verdict,
            "qc_reason": qc_reason,
            "qc_location": qc_location,
            "existing_receipt": existing_receipt,
            "is_booked": existing_receipt is not None,
        })
    return rows


@login_required
@require_POST
def receiving_console_book(request, pk):
    """Draft a ``scm.GoodsReceiptNote`` from one ASN's declaration. IDEMPOTENT.

    Idempotency is keyed on the delivery-note reference, not on a flag we keep: if a live receipt
    already carries this shipment's key — its ``supplier_reference``, or its own number when it
    declared none (``_console_reference``) — the verb returns THAT receipt instead of minting a
    second one. A double-submitted console row therefore lands on the same document twice rather
    than creating two receipts against one delivery note.

    The receipt is created as a **draft**. Booking the stock (and everything that hangs off it) is
    ``scm:goodsreceipt_receive`` — one writer for the inventory ledger, and it is not this one.
    """
    guard = _tenant_guard(request, "book receipts")
    if guard is not None:
        return guard

    with transaction.atomic():
        asn = get_object_or_404(
            AdvancedShipmentNotice.objects.select_for_update(), pk=pk, tenant=request.tenant)

        # The status guard lives HERE, not only in the template: hiding a button does not stop a
        # direct POST, and a cancelled or still-draft notice is not an arrival.
        if asn.status not in CONSOLE_STATUSES:
            messages.error(
                request,
                f"{asn.number} is {asn.get_status_display().lower()} — only a declared shipment "
                "can be booked.")
            return redirect("procurement:receiving_console")

        order = asn.purchase_order
        if order.status in PurchaseOrder.CLOSED_STATUSES:
            messages.error(
                request,
                f"Order {order.number} is {order.get_status_display().lower()} — reopen it in "
                "SCM before booking a receipt against it.")
            return redirect("procurement:receiving_console")

        # ALWAYS keyed, never skipped: a shipment that declared no supplier reference falls back
        # to its own number, so the check below runs for every ASN. Guarding this on a non-blank
        # supplier_reference is what let a re-click mint a second draft receipt (and burn a second
        # GRN number) for the same delivery.
        reference = _console_reference(asn)
        existing = (GoodsReceiptNote.objects
                    .filter(tenant=request.tenant, delivery_note_ref__iexact=reference)
                    .exclude(status="cancelled").order_by("id").first())
        if existing is not None:
            messages.info(
                request,
                f"Receipt {existing.number} already covers delivery note {reference}.")
            return redirect("scm:goodsreceipt_detail", pk=existing.pk)

        form = ReceivingConsoleBookForm(request.POST, asn=asn, tenant=request.tenant)
        if not form.is_valid():
            messages.error(request, _form_errors(form))
            return redirect("procurement:receiving_console")

        receipt = GoodsReceiptNote(
            tenant=request.tenant,
            purchase_order=order,
            location=form.cleaned_data.get("location"),
            receipt_date=form.cleaned_data["receipt_date"],
            status="draft",
            delivery_note_ref=reference[:64],
            received_by=request.user,
            notes=form.cleaned_data.get("notes") or "",
        )
        receipt.save()

        booked = 0
        for line in form.asn_lines:
            quantity = form.quantity_for(line)
            if not quantity or quantity <= ZERO or not line.po_line_id:
                continue
            GoodsReceiptLine.objects.create(
                goods_receipt=receipt,
                po_line=line.po_line,
                quantity_received=quantity,
                notes=f"Declared on {asn.number}"[:255],
            )
            booked += 1

        write_audit_log(request.user, receipt, "create", {
            "action": "console_book",
            "asn": asn.number,
            "lines": booked,
        })

    messages.success(
        request,
        f"Draft receipt {receipt.number} created from {asn.number} ({booked} line"
        f"{'' if booked == 1 else 's'}). Book the stock from the receipt itself.")
    return redirect("scm:goodsreceipt_detail", pk=receipt.pk)


def _form_errors(form):
    """Flatten a form's errors into one message — the console has nowhere to render a bound form."""
    parts = []
    for field, errors in form.errors.items():
        label = "" if field == "__all__" else f"{field}: "
        parts.append(f"{label}{'; '.join(errors)}")
    return "Could not book this arrival — " + (" ".join(parts) or "check the figures posted.")


@login_required
@tenant_admin_required
@require_POST
def receiving_console_mint_lots(request, pk):
    """Mint the shipment's DECLARED lot/serial text into real ``scm.LotSerial`` rows.

    6.11 deliberately kept lot / serial / expiry on an ASN line as plain text: minting a
    traceability record for goods that have not arrived would put unreceived stock into the
    chain. Receipt is where that becomes true, which is why the verb lives here.

    ``get_or_create`` is keyed on ``(tenant, item, number)`` — the model's own unique_together —
    so a re-run adopts the existing lot instead of failing. A line whose free-text SKU matches no
    item is REPORTED, never fatal: that is the ``_post_grn_receipt`` posture, and refusing the
    whole shipment because one hint is unmatched would make the console unusable on exactly the
    workspaces that need it.

    Admin-gated: a lot number is a traceability identifier the whole workspace then reads.
    """
    guard = _tenant_guard(request, "mint declared lots")
    if guard is not None:
        return guard

    with transaction.atomic():
        asn = get_object_or_404(
            AdvancedShipmentNotice.objects.select_for_update(), pk=pk, tenant=request.tenant)
        if asn.status not in CONSOLE_STATUSES:
            messages.error(request, f"{asn.number} is not a declared shipment.")
            return redirect("procurement:receiving_console")

        minted, adopted, unresolved, skipped = 0, 0, [], 0
        for line in asn.lines.select_related("po_line").order_by("id"):
            serial = (line.serial_number or "").strip()
            number = serial or (line.lot_number or "").strip()
            if not number:
                skipped += 1
                continue
            # Bounded by ONE shipment's lines, so the per-line lookup here is not the N+1 the
            # board-level pages have to batch away.
            item = resolve_line_item(request.tenant, line.po_line) if line.po_line_id else None
            if item is None:
                unresolved.append(line.sku_hint or line.item_description or f"line {line.pk}")
                continue
            lot, created = LotSerial.objects.get_or_create(
                tenant=request.tenant, item=item, number=number[:64],
                defaults={
                    "kind": "serial" if serial else "lot",
                    "expiry_date": line.expiry_date,
                    "notes": f"Declared on {asn.number}"[:255],
                },
            )
            if created:
                minted += 1
                write_audit_log(request.user, lot, "create", {
                    "action": "console_mint_lot",
                    "asn": asn.number,
                    "item": item.sku,
                })
            else:
                adopted += 1

    if minted or adopted:
        messages.success(
            request,
            f"{minted} lot/serial record{'' if minted == 1 else 's'} created from {asn.number}"
            + (f", {adopted} already existed." if adopted else "."))
    elif not unresolved:
        messages.info(request, f"{asn.number} declares no lot or serial numbers to mint.")
    if unresolved:
        messages.warning(
            request,
            "No item matches the SKU on: " + ", ".join(unresolved[:10])
            + (f" (+{len(unresolved) - 10} more)" if len(unresolved) > 10 else "")
            + " — add the SKU to the item master to capture their lots.")
    return redirect("procurement:receiving_console")


# -- Tolerance exceptions ---------------------------------------------------------------------

def _cumulative_received():
    """Correlated subquery: accepted quantity across EVERY live receipt for a line's PO line.

    Over- and under-receipt are CUMULATIVE facts about an ordered line, not about one receipt —
    two receipts of 60 against an order of 100 is an over-receipt even though neither row exceeds
    it on its own. Expressing that in the ORM is what lets the buckets narrow BEFORE pagination.
    """
    quantity = DecimalField(max_digits=14, decimal_places=4)
    return Coalesce(
        Subquery(
            GoodsReceiptLine.objects
            .filter(po_line=OuterRef("po_line"))
            .exclude(goods_receipt__status="cancelled")
            .values("po_line")
            .annotate(total=Sum("quantity_received"))
            .values("total")[:1],
            output_field=quantity,
        ),
        Value(ZERO, output_field=quantity),
    )


def _bucket_conditions():
    """The four bucket predicates as ORM ``Q`` objects, defined ONCE.

    These are ZERO-TOLERANCE candidate predicates — every real breach is inside them, because a
    policy band only ever WIDENS what is acceptable. The governing policy then refines each row's
    verdict on the page, and a candidate the policy forgives is shown as "within tolerance"
    rather than dropped: nothing disappears after pagination, so the tiles and the page numbers
    always describe the rows on screen.
    """
    ordered = F("po_line__quantity")
    # An order with no promised date compares NULL and drops out of both date buckets on its own,
    # which is the right answer: nothing was promised, so nothing was missed.
    expected = F("goods_receipt__purchase_order__expected_date")
    return {
        "over": Q(cumulative_received__gt=ordered),
        "short": Q(cumulative_received__lt=ordered),
        "early": Q(goods_receipt__receipt_date__lt=expected),
        "late": Q(goods_receipt__receipt_date__gt=expected),
    }


@login_required
def tolerance_exceptions(request):
    """Receipt lines that fall outside the ordered quantity or the promised date.

    Every bucket narrows in the ORM before pagination. Each row then carries the verdict its
    governing :class:`ReceiptTolerancePolicy` actually reaches, plus a one-click link that
    pre-fills a discrepancy claim from it.
    """
    guard = _tenant_guard(request, "review receipt tolerances")
    if guard is not None:
        return guard

    tenant = request.tenant
    base = (GoodsReceiptLine.objects
            .filter(goods_receipt__tenant=tenant)
            .exclude(goods_receipt__status="cancelled"))
    annotated = base.annotate(cumulative_received=_cumulative_received())
    conditions = _bucket_conditions()

    bucket = request.GET.get("bucket", "").strip()
    if bucket not in _BUCKET_KEYS:
        bucket = DEFAULT_BUCKET

    # Counted per bucket rather than in one conditional aggregate: the over/short predicates read
    # a correlated-subquery annotation, and a Subquery inside a ``Count(filter=...)`` is not
    # portable across the backends this project runs on. Four cheap COUNTs, same numbers.
    stats = {key: annotated.filter(condition).count() for key, condition in conditions.items()}
    stats["no_policy"] = _uncovered_line_count(tenant, base)

    qs = (annotated.filter(conditions[bucket])
          .select_related("goods_receipt", "goods_receipt__purchase_order",
                          "goods_receipt__purchase_order__vendor", "po_line"))

    q = request.GET.get("q", "").strip()
    qs = apply_search(qs, q, ["goods_receipt__number", "po_line__item_description",
                              "po_line__sku_hint"])
    vendor_pk = as_db_int(request.GET.get("vendor", ""))
    if vendor_pk is not None:
        qs = qs.filter(goods_receipt__purchase_order__vendor_id=vendor_pk)

    page_obj = paginate(request, qs.order_by("-goods_receipt__receipt_date", "-id"),
                        per_page=BOARD_PER_PAGE)

    return render(request, "procurement/goodsreceiptinspection/tolerance_exceptions.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "rows": _exception_rows(tenant, list(page_obj.object_list)),
        "bucket": bucket,
        "bucket_choices": BUCKET_CHOICES,
        "vendors": _supplier_parties(tenant),
        "stats": stats,
    })


def _uncovered_line_count(tenant, base):
    """How many live receipt lines NO active tolerance policy covers.

    A silent configuration gap is the failure mode a tolerance board exists to surface: with no
    catch-all rule, every "clean" line on the other tiles is really an unjudged one. Counted over
    DISTINCT (sku hint, vendor) groups rather than per line — resolution depends on nothing else,
    so one grouped query plus one pass over the groups answers it exactly, whatever the row count.
    """
    rules = _tolerance_rules(tenant)
    groups = list(
        base.values("po_line__sku_hint", "goods_receipt__purchase_order__vendor_id")
        .annotate(n=Count("id")).order_by("-n")[:_COVERAGE_CAP]
    )
    if not groups:
        return 0
    items = _item_map(tenant, {_norm(group["po_line__sku_hint"]) for group in groups})

    uncovered = 0
    for group in groups:
        item = items.get(_norm(group["po_line__sku_hint"]))
        rule, _reason = resolve_receipt_tolerance(
            item, group["goods_receipt__purchase_order__vendor_id"], tenant=tenant,
            category=getattr(item, "category", None), rules=rules)
        if rule is None:
            uncovered += group["n"]
    return uncovered


def _exception_rows(tenant, lines):
    """One derived row per receipt line on the page, judged against its governing policy."""
    if not lines:
        return []

    rules = _tolerance_rules(tenant)
    items = _item_map(tenant, {_norm(line.po_line.sku_hint) for line in lines if line.po_line_id})
    # Resolved once per request: a NoReverseMatch here means the discrepancy lane is not wired,
    # which is a wiring bug worth seeing rather than hiding behind a fallback link.
    create_url = reverse("procurement:discrepancy_create")

    rows = []
    for line in lines:
        po_line = line.po_line if line.po_line_id else None
        receipt = line.goods_receipt
        order = receipt.purchase_order
        vendor = getattr(order, "vendor", None)
        item = items.get(_norm(po_line.sku_hint)) if po_line else None

        ordered = (po_line.quantity if po_line else ZERO) or ZERO
        received = getattr(line, "cumulative_received", None) or ZERO
        rule, resolve_reason = resolve_receipt_tolerance(
            item, vendor, tenant=tenant, category=getattr(item, "category", None), rules=rules)
        verdict, reason = evaluate_receipt_tolerance(
            rule, ordered_quantity=ordered, received_quantity=received,
            expected_date=getattr(order, "expected_date", None),
            receipt_date=receipt.receipt_date,
        )

        params = {"goods_receipt": receipt.pk, "goods_receipt_line": line.pk}
        kind = _VERDICT_KIND.get(verdict)
        if kind:
            params["kind"] = kind
        gap = abs(received - ordered)
        if kind in ("over_shipment", "short_shipment") and gap > ZERO:
            params["quantity_affected"] = gap

        rows.append({
            "receipt": receipt,
            "receipt_line": line,
            "po_line": po_line,
            "order": order,
            "vendor": vendor,
            "description": po_line.item_description if po_line else "",
            "sku_hint": po_line.sku_hint if po_line else "",
            "ordered": ordered,
            "received": received,
            "rejected": line.quantity_rejected or ZERO,
            "rule": rule,
            "verdict": verdict,
            "reason": reason if rule is not None else resolve_reason,
            "verdict_css": _verdict_css(verdict),
            "receipt_date": receipt.receipt_date,
            "expected_date": getattr(order, "expected_date", None),
            "prefill_url": f"{create_url}?{urlencode(params)}",
        })
    return rows


# -- Receipt audit trail ----------------------------------------------------------------------

@login_required
def receipt_audit(request):
    """**Receipt Reversal & Audit Trail** — the append-only trail, narrowed to receiving.

    There is deliberately no create/edit/delete here and no second log: the trail is
    ``core.AuditLog``, written by the shared CRUD helpers on every mutation across every app.
    A reversal shows up as what it is — a later entry — which is exactly what makes the sequence
    trustworthy.

    ``?grn=`` widens from "the receipt itself" to "everything raised ABOUT that receipt": its own
    rows plus the discrepancies and returns that point at it. Chasing a receipt means chasing its
    consequences, and they live on three different tables.
    """
    guard = _tenant_guard(request, "review the receipt audit trail")
    if guard is not None:
        return guard

    tenant = request.tenant
    base = procurement_activity_qs(tenant).filter(content_type__model__in=RECEIPT_AUDIT_MODELS)

    # ONE aggregate over the UNFILTERED trail — the tiles describe the workspace's receiving
    # history, not whatever the filter bar currently narrows it to.
    totals = base.aggregate(
        total=Count("id"),
        creates=Count("id", filter=Q(action="create")),
        updates=Count("id", filter=Q(action="update")),
        deletes=Count("id", filter=Q(action="delete")),
    )

    qs = base
    grn = None
    grn_pk = as_db_int(request.GET.get("grn", ""))
    if grn_pk is not None:
        grn = (GoodsReceiptNote.objects.filter(pk=grn_pk, tenant=tenant)
               .select_related("purchase_order").first())
    if grn is not None:
        scoped = Q(content_type__model="goodsreceiptnote", object_id=grn.pk)
        discrepancy_ids = list(ReceiptDiscrepancy.objects
                               .filter(tenant=tenant, goods_receipt=grn)
                               .values_list("id", flat=True))
        if discrepancy_ids:
            scoped |= Q(content_type__model="receiptdiscrepancy", object_id__in=discrepancy_ids)
        rtv_ids = list(ReturnToVendor.objects.filter(tenant=tenant, goods_receipt=grn)
                       .values_list("id", flat=True))
        if rtv_ids:
            scoped |= Q(content_type__model="returntovendor", object_id__in=rtv_ids)
        qs = qs.filter(scoped)

    q = request.GET.get("q", "").strip()
    qs = apply_search(qs, q, ["target"])

    # Resolved against the CLOSED vocabulary — a junk token narrows nothing instead of rendering
    # an empty page while the select still reads "All".
    action = request.GET.get("action", "").strip()
    if action in {value for value, _label in AuditLog.ACTION_CHOICES}:
        qs = qs.filter(action=action)
    else:
        action = ""

    page_obj = paginate(request, qs, per_page=BOARD_PER_PAGE)

    return render(request, "procurement/goodsreceiptinspection/receipt_audit.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "entries": page_obj.object_list,
        "grn": grn,
        "receipts": _receipts(tenant),
        "action": action,
        "action_choices": AuditLog.ACTION_CHOICES,
        "stats": {
            "total": totals["total"],
            "creates": totals["creates"],
            "updates": totals["updates"],
            "deletes": totals["deletes"],
        },
        "feed_note": ACTIVITY_FEED_NOTE,
    })
