"""Procurement 6.12 Goods Receipt & Inspection — ReceiptDiscrepancy views.

**Discrepancy Reporting** bullet: raise a claim about what arrived, tell the supplier, agree a
remedy, close it. Raising and working a finding is open to any workspace member (the person on
the dock is the person who saw it); DELETING one is tenant-admin gated, because a discrepancy is
part of the receiving trail the audit board reads and withdrawing it should normally be
``cancel`` — which keeps the record and its reason.

Every status guard is enforced HERE as well as in the template — hiding a button does not stop a
direct POST — and again inside the model's verb methods, which run under a row lock so a
double-submitted notification cannot re-stamp the date we told the supplier.

**Writes nothing but its own row.** No StockMove, no JournalEntry, no write to the SCM spine
(L36): ``scm:goodsreceipt_receive`` remains the single stock writer, and the vendor credit rides
on the linked RTV's free-text reference because ``accounting.Bill`` has no vendor-credit kind
(L29).
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.crud import as_db_int
# The house upload limits, read straight from core so the hint this page PRINTS and the check the
# form ENFORCES can never disagree. Deliberately not taken from the procurement forms package,
# where CatalogManagement defines a different, smaller MAX_UPLOAD_BYTES of its own.
from apps.core.forms import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES
from apps.core.models import Party
from apps.procurement.forms import (
    DiscrepancyCancelForm,
    DiscrepancyNotifyForm,
    DiscrepancyResolveForm,
    ReceiptDiscrepancyForm,
)
from apps.procurement.models import (
    ReceiptDiscrepancy,
    ReceiptTolerancePolicy,
    evaluate_receipt_tolerance,
    resolve_line_item,
    resolve_receipt_tolerance,
)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import GoodsReceiptLine, GoodsReceiptNote

ZERO = Decimal("0")

#: Every hop a row (or a row's ``__str__``, or the ``vendor``/``order`` properties) walks. The
#: vendor property is TWO hops from the discrepancy, so without this a page of rows costs 2N
#: queries on top of the receipt fetch itself.
_ROW_RELATIONS = (
    "goods_receipt",
    "goods_receipt__purchase_order",
    "goods_receipt__purchase_order__vendor",
    "goods_receipt_line",
    "goods_receipt_line__po_line",
    "nonconformance",
    "quarantine_order",
    "return_to_vendor",
)


def _supplier_parties(tenant):
    """Parties this workspace buys from — local mirror of the helper the forms package keeps
    (peer modules don't import each other's internals). ``core.PartyRole`` distinguishes
    ``supplier`` from ``vendor``; BOTH are accepted so the filter never hides half the
    counterparties."""
    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _tenant_receipts(request):
    """Recent receipts for the ``?grn=`` dropdown and the form's "choose the receipt" hint.
    Capped: the widget is a convenience, not a browsable index of every receipt ever booked."""
    return (GoodsReceiptNote.objects.filter(tenant=request.tenant)
            .select_related("purchase_order")
            .order_by("-receipt_date", "-id")[:200])


def _upload_hint():
    """What the form page prints about evidence uploads, from the same constants the form
    enforces."""
    return {
        "allowed_extensions": ", ".join(sorted(ALLOWED_DOC_EXTENSIONS)),
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
    }


@login_required
def discrepancy_list(request):
    """The discrepancy register. Every filter is applied BEFORE pagination, so the page counts
    and the stat cards tell the same story the rows do."""
    qs = (ReceiptDiscrepancy.objects.filter(tenant=request.tenant)
          .select_related(*_ROW_RELATIONS))
    return crud_list(
        request, qs, "procurement/goodsreceiptinspection/discrepancy/list.html",
        search_fields=["number", "description", "item_description", "sku_hint",
                       "goods_receipt__number", "vendor_reference"],
        # (get_param, orm_lookup, is_int) — the int ones go through crud_list's as_db_int guard,
        # so ?grn=abc / ?vendor=999999999999999999999 skip the filter instead of 500ing (L11).
        filters=[
            ("status", "status", False),
            ("kind", "kind", False),
            ("severity", "severity", False),
            ("remedy", "remedy", False),
            ("grn", "goods_receipt_id", True),
            ("vendor", "goods_receipt__purchase_order__vendor_id", True),
        ],
        extra_context={
            "status_choices": ReceiptDiscrepancy.STATUS_CHOICES,
            "kind_choices": ReceiptDiscrepancy.KIND_CHOICES,
            "severity_choices": ReceiptDiscrepancy.SEVERITY_CHOICES,
            "remedy_choices": ReceiptDiscrepancy.REMEDY_CHOICES,
            "receipts": _tenant_receipts(request),
            "vendors": _supplier_parties(request.tenant),
            "stats": _discrepancy_stats(request),
        },
    )


def _discrepancy_stats(request):
    """The four stat cards, in ONE aggregate query rather than four ``.count()`` round trips.

    Computed over the WHOLE workspace, not the filtered page: a stat card answers "how much is
    outstanding?", which must not change because someone typed a search. Each bucket matches
    EXACTLY the filter its card links to (``?status=open`` … ``?severity=critical``), so a card
    can never disagree with the list it opens.
    """
    return ReceiptDiscrepancy.objects.filter(tenant=request.tenant).aggregate(
        open=Count("id", filter=Q(status="open")),
        notified=Count("id", filter=Q(status="vendor_notified")),
        resolved=Count("id", filter=Q(status="resolved")),
        critical=Count("id", filter=Q(severity="critical")),
    )


def _tolerance_snapshot(obj):
    """``(rule, verdict, reason, css)`` for the finding's own receipt line.

    Advisory ONLY (the 6.12 posture): a tolerance policy colours a page, it never blocks
    ``scm:goodsreceipt_receive``. Shown on the detail so the reviewer can see whether the claim
    is actually outside the band this workspace agreed with the supplier, or inside it and
    therefore a conversation rather than a breach.

    A HEADER-level finding (no receipt line) has no ordered/received pair to judge, so it is put
    through the evaluator with zero quantities: the quantity bands cannot fire, and what remains
    is the date arithmetic — which is exactly the right judgement for a ``late_delivery`` or
    ``documentation`` finding raised against the receipt as a whole.
    """
    line = obj.goods_receipt_line
    po_line = line.po_line if line is not None else None
    order = obj.order
    item = resolve_line_item(obj.tenant, po_line) if po_line is not None else None

    rule, match_reason = resolve_receipt_tolerance(
        item=item,
        vendor=order.vendor if order is not None else None,
        tenant=obj.tenant,
    )
    verdict, verdict_reason = evaluate_receipt_tolerance(
        rule,
        ordered_quantity=(po_line.quantity if po_line is not None else ZERO),
        received_quantity=(line.quantity_received if line is not None else ZERO),
        expected_date=(order.expected_date if order is not None else None),
        receipt_date=obj.goods_receipt.receipt_date,
    )
    # With no rule the evaluator can only say "no policy"; the RESOLVER is the one that explains
    # why nothing matched, which is the answer a configuration gap needs.
    reason = match_reason if rule is None else verdict_reason
    return rule, verdict, reason, ReceiptTolerancePolicy.VERDICT_CSS.get(verdict, "badge-slate")


@login_required
def discrepancy_detail(request, pk):
    obj = get_object_or_404(
        # ``tenant`` joins the list because _tolerance_snapshot() resolves the governing policy
        # against it — without it the detail page pays an extra query for a row it already has.
        ReceiptDiscrepancy.objects.select_related(*_ROW_RELATIONS, "created_by", "resolved_by",
                                                  "tenant"),
        pk=pk, tenant=request.tenant,
    )
    is_admin = bool(request.user.is_superuser
                    or getattr(request.user, "is_tenant_admin", False))
    rule, verdict, reason, verdict_css = _tolerance_snapshot(obj)
    return render(request, "procurement/goodsreceiptinspection/discrepancy/detail.html", {
        "obj": obj,
        "receipt": obj.goods_receipt,
        "receipt_line": obj.goods_receipt_line,
        "order": obj.order,
        "vendor": obj.vendor,
        "notify_form": DiscrepancyNotifyForm(),
        "resolve_form": DiscrepancyResolveForm(initial={"remedy": obj.remedy}),
        "cancel_form": DiscrepancyCancelForm(),
        "tolerance_rule": rule,
        "tolerance_verdict": verdict,
        "tolerance_reason": reason,
        "tolerance_css": verdict_css,
        # The label comes from VERDICT_CHOICES, the single source for it — hand-copying the six
        # labels into a template {% if %} chain is how three of them drifted into rendering an
        # unrecognised verdict as "No policy".
        "tolerance_label": dict(ReceiptTolerancePolicy.VERDICT_CHOICES).get(verdict, verdict),
        "evidence_is_image": obj.evidence_is_image,
        # One-click hand-off into the RTV lane, carrying this finding so the return does not have
        # to be re-typed. The target re-validates the pk against the tenant regardless.
        "rtv_prefill_url": f"{reverse('procurement:rtv_create')}?discrepancy={obj.pk}",
        # The Actions sidebar gates on these booleans; every one of them is re-enforced in the
        # view that performs the action, and again in the model verb.
        "can_edit": obj.is_open,
        "can_notify": obj.status == "open",
        "can_resolve": obj.is_open,
        "can_cancel": obj.is_open,
        "can_raise_rtv": obj.is_open and obj.return_to_vendor_id is None,
        # Mirrors @tenant_admin_required exactly — don't offer a button that would 403.
        "can_delete": is_admin,
    })


#: Largest magnitude ``quantity_affected`` can physically hold, derived from the field so it
#: cannot drift if max_digits/decimal_places ever change: max_digits 14 with 4 decimal places
#: leaves 10 integer digits, i.e. everything strictly below 10**10.
_QTY_PREFILL_CEILING = Decimal(10) ** (
    ReceiptDiscrepancy._meta.get_field("quantity_affected").max_digits
    - ReceiptDiscrepancy._meta.get_field("quantity_affected").decimal_places
)


def _create_initial(request):
    """Tenant-checked ``?goods_receipt=&goods_receipt_line=&kind=&quantity_affected=`` prefill.

    This is the tolerance-exceptions board's "Raise discrepancy" hand-off, and it is CONVENIENCE
    ONLY: every referenced pk is re-validated against this workspace and simply left out when it
    is not ours. A ModelChoiceField preselects by PK — handing it an instance silently matches
    nothing — so the validated pks go in as integers.
    """
    initial = {}

    receipt_pk = as_db_int(request.GET.get("goods_receipt"))
    if receipt_pk is not None and not GoodsReceiptNote.objects.filter(
            pk=receipt_pk, tenant=request.tenant).exists():
        receipt_pk = None

    line_pk = as_db_int(request.GET.get("goods_receipt_line"))
    if line_pk is not None:
        # GoodsReceiptLine has no tenant column — scope it through its header. When a receipt was
        # named too, the line must be ITS line; otherwise the line names the receipt itself, so a
        # single ``?goods_receipt_line=`` is enough to fill both fields consistently.
        rows = GoodsReceiptLine.objects.filter(pk=line_pk,
                                               goods_receipt__tenant=request.tenant)
        if receipt_pk is not None:
            rows = rows.filter(goods_receipt_id=receipt_pk)
        owner_pk = rows.values_list("goods_receipt_id", flat=True).first()
        if owner_pk is None:
            line_pk = None
        else:
            receipt_pk = owner_pk

    if receipt_pk is not None:
        initial["goods_receipt"] = receipt_pk
    if line_pk is not None:
        initial["goods_receipt_line"] = line_pk

    kind = (request.GET.get("kind") or "").strip()
    if kind in dict(ReceiptDiscrepancy.KIND_CHOICES):
        initial["kind"] = kind

    raw_quantity = (request.GET.get("quantity_affected") or "").strip()
    if raw_quantity:
        try:
            quantity = Decimal(raw_quantity)
            # L11, decimal edition: "nan" and "Infinity" both PARSE cleanly, and it is the
            # COMPARISON that then raises (NaN) or the save that dies (Infinity). is_finite()
            # covers both, and the whole thing sits inside the try because `> 0` is itself the
            # operation that throws — a hand-typed ?quantity_affected=nan must not 500 the page.
            # The ceiling catches the other end: "1e400" and a 32-digit integer are finite and
            # positive, but neither fits max_digits.
            if quantity.is_finite() and ZERO < quantity < _QTY_PREFILL_CEILING:
                initial["quantity_affected"] = quantity
        except (InvalidOperation, ValueError, ArithmeticError):
            pass

    return initial


@login_required
def discrepancy_create(request):
    """Raise a finding. Hand-rolled rather than ``crud_create`` for two reasons: it stamps
    ``created_by`` (system authorship, never a form field), and it accepts the exceptions board's
    prefill."""
    if request.tenant is None:
        messages.error(request,
                       "Select a tenant workspace before raising receipt discrepancies.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = ReceiptDiscrepancyForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create", {
                "goods_receipt": obj.goods_receipt.number,
                "kind": obj.kind,
                "severity": obj.severity,
                "quantity_affected": str(obj.quantity_affected),
            })
            messages.success(
                request,
                f"Discrepancy {obj.number} raised against receipt {obj.goods_receipt.number}.")
            return redirect("procurement:discrepancy_detail", pk=obj.pk)
    else:
        form = ReceiptDiscrepancyForm(tenant=request.tenant, initial=_create_initial(request))

    ctx = {
        "form": form,
        "is_edit": False,
        "obj": None,
        "receipts": _tenant_receipts(request),
    }
    ctx.update(_upload_hint())
    return render(request, "procurement/goodsreceiptinspection/discrepancy/form.html", ctx)


@login_required
def discrepancy_edit(request, pk):
    """Correct a live finding. Refused once resolved or cancelled: a closed discrepancy is the
    record of what was agreed with the supplier, and re-writing it after the fact is what makes
    a trail untrustworthy. Correct it by raising a new finding instead."""
    obj = get_object_or_404(ReceiptDiscrepancy, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(
            request,
            f"Discrepancy {obj.number} is {obj.get_status_display().lower()} — a closed finding "
            f"is a record of what was agreed and can no longer be edited.")
        return redirect("procurement:discrepancy_detail", pk=pk)

    ctx = {"receipts": _tenant_receipts(request)}
    ctx.update(_upload_hint())
    return crud_edit(
        request, model=ReceiptDiscrepancy, pk=pk, form_class=ReceiptDiscrepancyForm,
        template="procurement/goodsreceiptinspection/discrepancy/form.html",
        success_url=reverse("procurement:discrepancy_detail", args=[obj.pk]),
        extra_context=ctx,
    )


@login_required
@tenant_admin_required
@require_POST
def discrepancy_delete(request, pk):
    """Admin-gated: deleting removes the finding from the receiving trail entirely. The everyday
    way to withdraw one is ``cancel``, which keeps the row and its reason."""
    return crud_delete(request, model=ReceiptDiscrepancy, pk=pk,
                       success_url="procurement:discrepancy_list")


@login_required
@require_POST
def discrepancy_notify_vendor(request, pk):
    """Stamp that the supplier has been told.

    Under a row lock: without it a double-submitted button would re-stamp ``vendor_notified_on``
    to a later date, quietly resetting the clock a supplier SLA is measured from.
    """
    with transaction.atomic():
        obj = get_object_or_404(ReceiptDiscrepancy.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        form = DiscrepancyNotifyForm(request.POST)
        if not form.is_valid():
            messages.error(request,
                           "Check the notification details — nothing was recorded.")
            return redirect("procurement:discrepancy_detail", pk=pk)
        data = form.cleaned_data
        if not obj.notify_vendor(request.user,
                                 reference=data.get("vendor_reference") or "",
                                 notified_on=data.get("vendor_notified_on")):
            messages.info(
                request,
                f"Discrepancy {obj.number} is {obj.get_status_display().lower()} — the supplier "
                f"has already been notified.")
            return redirect("procurement:discrepancy_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "notify_vendor",
        "status": obj.status,
        "vendor_notified_on": str(obj.vendor_notified_on),
        "vendor_reference": obj.vendor_reference,
    })
    messages.success(request, f"Supplier notified of discrepancy {obj.number}.")
    return redirect("procurement:discrepancy_detail", pk=pk)


@login_required
@require_POST
def discrepancy_resolve(request, pk):
    """Close the finding with an agreed remedy. The remedy is required by the form and
    re-validated by the model verb, which also refuses a second call — so a double-submit cannot
    reassign who resolved it."""
    with transaction.atomic():
        obj = get_object_or_404(ReceiptDiscrepancy.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        form = DiscrepancyResolveForm(request.POST)
        if not form.is_valid():
            messages.error(
                request,
                "Choose a remedy and say what was agreed — the discrepancy was not closed.")
            return redirect("procurement:discrepancy_detail", pk=pk)
        data = form.cleaned_data
        if not obj.resolve(request.user, data["remedy"], data["resolution_notes"]):
            messages.info(
                request,
                f"Discrepancy {obj.number} is already {obj.get_status_display().lower()}.")
            return redirect("procurement:discrepancy_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "resolve",
        "status": obj.status,
        "remedy": obj.remedy,
        "notes": obj.resolution_notes[:200],
    })
    messages.success(request, f"Discrepancy {obj.number} resolved.")
    return redirect("procurement:discrepancy_detail", pk=pk)


@login_required
@require_POST
def discrepancy_cancel(request, pk):
    """Withdraw the finding — a mis-count, or one folded into another claim. Refused once
    resolved: that is a record of what was agreed, not a decision to take back."""
    with transaction.atomic():
        obj = get_object_or_404(ReceiptDiscrepancy.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        form = DiscrepancyCancelForm(request.POST)
        if not form.is_valid():
            messages.error(request, "That reason could not be recorded — nothing was changed.")
            return redirect("procurement:discrepancy_detail", pk=pk)
        if not obj.cancel(request.user, form.cleaned_data.get("resolution_notes") or ""):
            messages.info(
                request,
                f"Discrepancy {obj.number} is {obj.get_status_display().lower()} and cannot be "
                f"cancelled.")
            return redirect("procurement:discrepancy_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "cancel",
        "status": obj.status,
        "reason": obj.resolution_notes[:200],
    })
    messages.success(request, f"Discrepancy {obj.number} cancelled.")
    return redirect("procurement:discrepancy_detail", pk=pk)
