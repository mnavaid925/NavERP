"""Procurement 6.12 Goods Receipt & Inspection — ReturnToVendor views.

**Return to Vendor (RTV) Processing** bullet: raise the return, get it authorized, ship it back,
and close it when the credit or replacement lands.

Gating: recording and moving a return is open to any workspace member (a buyer or a receiving
clerk is exactly who knows the goods are wrong). AUTHORIZING one and DELETING one are
tenant-admin gated — authorization is the signature the supplier is shown, and deletion removes
the trail entirely rather than leaving a cancelled record with a reason on it.

Every status guard is enforced HERE as well as in the template — hiding a button does not stop a
direct POST — and again inside the model's verb methods, which run under a row lock so a
double-submitted authorize cannot re-stamp who signed it.

**Writes nothing to stock and nothing to the ledger** (see ``ReturnToVendor``'s class docstring).
Tests assert exactly that: authorizing, shipping and closing an RTV must produce ZERO new
``StockMove`` and ZERO new ``JournalEntry`` rows.
"""
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q

from apps.core.crud import _changed, as_db_int
from apps.procurement.forms import (
    ReturnToVendorForm,
    ReturnToVendorLineFormSet,
    RtvCancelForm,
    RtvCloseForm,
    RtvShipForm,
)
from apps.procurement.models import ReceiptDiscrepancy, ReturnToVendor, ReturnToVendorLine
from apps.procurement.views._common import *  # noqa: F401,F403

#: Rendered on rtv/detail.html so the non-posting decision is visible where it matters, not only
#: in a docstring a reviewer has to go looking for.
NON_POSTING_NOTE = (
    "A return to vendor records the commercial claim only — it posts no stock movement and no "
    "journal entry. Quantity rejected on the dock never entered stock (the goods receipt books "
    "only what was accepted), and stock that was accepted and later failed inspection is removed "
    "by a quarantine scrap or a stock adjustment. Any credit note is raised in Accounts Payable "
    "and referenced here."
)

#: A receiving finding maps onto a return reason only where the two vocabularies genuinely agree.
#: A short shipment or a paperwork problem has nothing to send back, so those prefill no reason
#: rather than guessing one the buyer would have to correct.
_KIND_TO_REASON = {
    "damaged": "damaged",
    "wrong_item": "wrong_item",
    "over_shipment": "over_shipment",
    "quality_failure": "not_to_spec",
}


def _is_admin(request):
    """Mirrors @tenant_admin_required exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _supplier_parties(tenant):
    """Supplier/vendor-role parties for the filter widget — the local-copy convention (peer
    sub-modules mirror this helper rather than importing each other's private names)."""
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _tenant_orders(tenant):
    """Recent purchase orders for the ``?po=`` dropdown. Capped: the filter widget is a
    convenience, not a browsable index of every order this workspace has ever raised."""
    from apps.scm.models import PurchaseOrder

    if tenant is None:
        return PurchaseOrder.objects.none()
    return PurchaseOrder.objects.filter(tenant=tenant).order_by("-order_date", "-id")[:200]


def _scoped(tenant):
    """The register queryset: tenant-scoped, with every relation a ROW (or a row's ``__str__``)
    touches already joined, the lines prefetched for the expected-credit column, and the
    duplicate-RMA badge resolved as ONE ``Exists`` subquery instead of one query per row.

    ``ReturnToVendor.__str__`` walks ``vendor``, the origin column reads ``goods_receipt`` and
    ``discrepancy``, and ``expected_credit_value`` folds every line's ``po_line.unit_price`` —
    without the joins and the prefetch a page of 15 rows costs dozens of queries.
    """
    line_qs = (ReturnToVendorLine.objects
               .select_related("po_line", "goods_receipt_line", "goods_receipt_line__po_line")
               .order_by("id"))
    # Another LIVE return of this workspace quoting the same non-blank RMA number. Blank is never
    # a duplicate: the ``supplier_rma_number=""`` exclusion means a row with no RMA matches
    # nothing, so the badge stays off instead of firing on every un-numbered return.
    peers = (ReturnToVendor.objects
             .exclude(status="cancelled")
             .exclude(supplier_rma_number="")
             .filter(tenant_id=OuterRef("tenant_id"),
                     supplier_rma_number=OuterRef("supplier_rma_number"))
             .filter(~Q(pk=OuterRef("pk"))))
    return (ReturnToVendor.objects.filter(tenant=tenant)
            .select_related("vendor", "purchase_order", "goods_receipt", "discrepancy")
            .prefetch_related(Prefetch("lines", queryset=line_qs))
            .annotate(rma_duplicate_flag=Exists(peers))
            .order_by("-created_at", "-id"))


def _rtv_stats(tenant):
    """The four stat cards, in ONE aggregate query rather than four ``.count()`` round trips.

    Deliberately computed over the WHOLE workspace, not the filtered page: a stat card answers
    "how is the returns pipeline doing?", which must not change because someone typed a search.
    """
    return ReturnToVendor.objects.filter(tenant=tenant).aggregate(
        draft=Count("id", filter=Q(status="draft")),
        authorized=Count("id", filter=Q(status="authorized")),
        shipped=Count("id", filter=Q(status="shipped")),
        closed=Count("id", filter=Q(status="closed")),
    )


@login_required
def rtv_list(request):
    """The returns register. Every filter is applied BEFORE pagination, so the page counts and
    the stat cards tell the same story the rows do."""
    return crud_list(
        request, _scoped(request.tenant), "procurement/goodsreceiptinspection/rtv/list.html",
        search_fields=["number", "supplier_rma_number", "tracking_number", "vendor__name",
                       "purchase_order__number"],
        # (get_param, orm_lookup, is_int) — the int ones go through crud_list's as_db_int guard,
        # so ?vendor=abc / ?po=999999999999999999999 skip the filter instead of 500ing (L11).
        filters=[
            ("status", "status", False),
            ("reason", "reason", False),
            ("remedy", "remedy", False),
            ("vendor", "vendor_id", True),
            ("po", "purchase_order_id", True),
        ],
        extra_context={
            "status_choices": ReturnToVendor.STATUS_CHOICES,
            "reason_choices": ReturnToVendor.REASON_CHOICES,
            "remedy_choices": ReturnToVendor.REMEDY_CHOICES,
            "vendors": _supplier_parties(request.tenant),
            "purchase_orders": _tenant_orders(request.tenant),
            "stats": _rtv_stats(request.tenant),
        },
    )


@login_required
def rtv_detail(request, pk):
    obj = get_object_or_404(
        ReturnToVendor.objects.select_related(
            "vendor", "purchase_order", "purchase_order__vendor", "goods_receipt",
            "goods_receipt__purchase_order", "discrepancy", "discrepancy__goods_receipt",
            "authorized_by", "created_by"),
        pk=pk, tenant=request.tenant,
    )
    # The model's memoized fetch, joined through to every relation the credit fold reads — the
    # table and the total then walk the SAME instances rather than re-querying per column.
    lines = obj.line_rows()
    line_rows = [{
        "line": line,
        "description": line.item_description,
        "sku_hint": line.sku_hint,
        "uom_hint": line.uom_hint,
        "quantity": line.quantity_returned,
        "unit_price": line.unit_price,
        "expected_credit": line.expected_credit,
    } for line in lines]

    is_admin = _is_admin(request)
    return render(request, "procurement/goodsreceiptinspection/rtv/detail.html", {
        "obj": obj,
        "lines": lines,
        "line_rows": line_rows,
        "expected_credit_value": obj.expected_credit_value,
        "vendor": obj.vendor,
        "order": obj.purchase_order,
        "receipt": obj.goods_receipt,
        "discrepancy": obj.discrepancy,
        "ship_form": RtvShipForm(),
        "close_form": RtvCloseForm(),
        "cancel_form": RtvCancelForm(),
        # ADVISORY badge — a supplier legitimately issues one RMA covering several shipments, so
        # this warns and never blocks.
        "has_duplicate_rma": obj.has_duplicate_rma,
        "non_posting_note": NON_POSTING_NOTE,
        # The Actions sidebar gates on these booleans; every one is re-enforced in the view that
        # performs the action, and again in the model verb.
        "can_edit": obj.is_editable,
        # Authorize and delete are admin-only — don't offer a button that would 403.
        "can_authorize": is_admin and obj.status == "draft",
        "can_ship": obj.status == "authorized",
        "can_close": obj.status == "shipped",
        "can_cancel": obj.status in ReturnToVendor.CANCELLABLE_STATUSES,
        "can_delete": is_admin and obj.is_editable,
    })


def _create_initial(request):
    """Tenant-checked ``?discrepancy=<pk>`` prefill for the create form.

    The link comes off a receiving finding's detail page ("Raise RTV"), and everything the return
    needs — supplier, order, receipt — is already known there, so re-typing it is a chance to get
    it wrong. It is CONVENIENCE ONLY: the referenced row is re-checked against this tenant and
    dropped if it does not belong. A query string is never an authorization path, and the form's
    own querysets plus ``ReturnToVendor.clean()`` refuse a foreign pk again on POST.

    A ModelChoiceField preselects by PK — handing it an instance silently matches nothing — so
    the validated pks go in as integers.
    """
    initial = {}
    pk = as_db_int(request.GET.get("discrepancy"))
    if pk is None:
        return initial

    discrepancy = (ReceiptDiscrepancy.objects
                   .filter(pk=pk, tenant=request.tenant)
                   .select_related("goods_receipt", "goods_receipt__purchase_order")
                   .first())
    if discrepancy is None:
        return initial

    initial["discrepancy"] = discrepancy.pk
    reason = _KIND_TO_REASON.get(discrepancy.kind)
    if reason:
        initial["reason"] = reason
    if discrepancy.goods_receipt_id:
        receipt = discrepancy.goods_receipt
        initial["goods_receipt"] = receipt.pk
        if receipt.purchase_order_id:
            initial["purchase_order"] = receipt.purchase_order_id
            initial["vendor"] = receipt.purchase_order.vendor_id
    return initial


@login_required
def rtv_create(request):
    """Raise a return. Hand-rolled rather than ``crud_create`` for two reasons the generic helper
    cannot cover: stamping ``created_by``, and the discrepancy hand-off prefill.

    Lines are declared on the EDIT page: the receipt-line dropdown can only be narrowed once the
    goods receipt is known, so offering it here would mean offering every receipt line in the
    workspace.
    """
    if request.tenant is None:
        # The superuser carries tenant=None; without this guard a create would either orphan the
        # row or fail deep inside save() with nothing the user can act on.
        messages.error(request, "Select a tenant workspace before raising returns.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = ReturnToVendorForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create", {
                "vendor": str(obj.vendor)[:120],
                "reason": obj.reason,
                "remedy": obj.remedy,
            })
            messages.success(
                request, f"Return {obj.number} raised — add the lines going back below.")
            return redirect("procurement:rtv_detail", pk=obj.pk)
    else:
        form = ReturnToVendorForm(tenant=request.tenant, initial=_create_initial(request))

    return render(request, "procurement/goodsreceiptinspection/rtv/form.html", {
        "form": form,
        "is_edit": False,
        "obj": None,
        "formset": None,
        "receipt": None,
    })


@login_required
def rtv_edit(request, pk):
    """Correct the header and declare the lines going back.

    DRAFTS ONLY, refused server-side: once the return is authorized the supplier has been told
    what is coming, and re-writing the lines under an issued RMA is how a disputed credit starts.
    """
    obj = get_object_or_404(
        ReturnToVendor.objects.select_related("vendor", "purchase_order", "goods_receipt"),
        pk=pk, tenant=request.tenant,
    )
    if not obj.is_editable:
        messages.error(
            request,
            f"Return {obj.number} is {obj.get_status_display().lower()} and can no longer be "
            f"edited.")
        return redirect("procurement:rtv_detail", pk=pk)

    if request.method == "POST":
        form = ReturnToVendorForm(request.POST, instance=obj, tenant=request.tenant)
        # The formset narrows each row's receipt-line dropdown from ``instance.goods_receipt``,
        # and ``form.is_valid()`` is evaluated FIRST — so by the time the formset builds its rows
        # the header already carries whichever receipt this same submit chose.
        formset = ReturnToVendorLineFormSet(request.POST, instance=obj)
        if form.is_valid() and formset.is_valid():
            # Header + line rows are one logical write; a half-saved return would quote a credit
            # for goods that are not on the despatch.
            with transaction.atomic():
                obj = form.save()
                formset.instance = obj
                formset.save()
            # WHICH header fields moved, not just "the header moved" — a disputed credit is later
            # argued over vendor / remedy / supplier_rma_number. The shared helper keeps the
            # redaction policy in one place rather than duplicating a sensitive-field list here.
            changes = _changed(form)
            changes["lines"] = obj.lines.count()
            write_audit_log(request.user, obj, "update", changes)
            messages.success(request, f"Return {obj.number} updated.")
            return redirect("procurement:rtv_detail", pk=obj.pk)
    else:
        form = ReturnToVendorForm(instance=obj, tenant=request.tenant)
        formset = ReturnToVendorLineFormSet(instance=obj)

    return render(request, "procurement/goodsreceiptinspection/rtv/form.html", {
        "form": form,
        "is_edit": True,
        "obj": obj,
        "formset": formset,
        "receipt": obj.goods_receipt,
    })


@login_required
@tenant_admin_required
@require_POST
def rtv_delete(request, pk):
    """Drafts only. An authorized return has been declared to the supplier — cancel it instead,
    which keeps the record and its reason. Admin-gated because deletion removes the trail."""
    obj = get_object_or_404(ReturnToVendor, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request,
                       f"Only a draft return can be deleted — cancel {obj.number} instead.")
        return redirect("procurement:rtv_detail", pk=pk)
    return crud_delete(request, model=ReturnToVendor, pk=pk,
                       success_url="procurement:rtv_list")


@login_required
@tenant_admin_required
@require_POST
def rtv_authorize(request, pk):
    """Approve the return so it can be shipped. Admin-gated: this is the signature the supplier
    is shown, and it freezes the lines."""
    with transaction.atomic():
        obj = get_object_or_404(ReturnToVendor.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.authorize(request.user):
            # Already authorized (a double-submit), shipped, closed or cancelled. Never re-stamp
            # who signed it or when.
            messages.info(request,
                          f"Return {obj.number} is already "
                          f"{obj.get_status_display().lower()}.")
            return redirect("procurement:rtv_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "authorize", "status": obj.status})
    messages.success(request, f"Return {obj.number} authorized.")
    return redirect("procurement:rtv_detail", pk=pk)


@login_required
@require_POST
def rtv_ship(request, pk):
    """Record the despatch. The only writer of ``shipped_on``."""
    with transaction.atomic():
        obj = get_object_or_404(ReturnToVendor.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        form = RtvShipForm(request.POST)
        if not form.is_valid():
            messages.error(request,
                           "Check the despatch details — the shipment could not be recorded.")
            return redirect("procurement:rtv_detail", pk=pk)
        data = form.cleaned_data
        if not obj.mark_shipped(request.user,
                                carrier_name=data.get("carrier_name") or "",
                                tracking_number=data.get("tracking_number") or "",
                                shipped_on=data.get("shipped_on")):
            messages.info(request,
                          f"Return {obj.number} is {obj.get_status_display().lower()} — only an "
                          f"authorized return can be shipped.")
            return redirect("procurement:rtv_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {
        "action": "ship",
        "shipped_on": str(obj.shipped_on),
        "carrier": obj.carrier_name[:120],
        "tracking": obj.tracking_number[:64],
    })
    messages.success(request, f"Return {obj.number} marked shipped.")
    return redirect("procurement:rtv_detail", pk=pk)


@login_required
@require_POST
def rtv_close(request, pk):
    """Close the return once the remedy lands. ``credit_note_ref`` is a REFERENCE — this posts
    nothing to the ledger and nothing to stock."""
    with transaction.atomic():
        obj = get_object_or_404(ReturnToVendor.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        form = RtvCloseForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the credit note reference — the return was not closed.")
            return redirect("procurement:rtv_detail", pk=pk)
        if not obj.close(request.user,
                         credit_note_ref=form.cleaned_data.get("credit_note_ref") or ""):
            messages.info(request,
                          f"Return {obj.number} is {obj.get_status_display().lower()} — only a "
                          f"shipped return can be closed.")
            return redirect("procurement:rtv_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {
        "action": "close",
        "credit_note_ref": obj.credit_note_ref[:64],
        # Recorded so the trail says what we expected back, without ever storing it as a balance.
        "expected_credit": str(obj.expected_credit_value),
    })
    messages.success(request, f"Return {obj.number} closed.")
    return redirect("procurement:rtv_detail", pk=pk)


@login_required
@require_POST
def rtv_cancel(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(ReturnToVendor.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        form = RtvCancelForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Give a reason when cancelling a return.")
            return redirect("procurement:rtv_detail", pk=pk)
        if not obj.cancel(request.user, form.cleaned_data["cancellation_reason"]):
            messages.info(request,
                          f"Return {obj.number} is {obj.get_status_display().lower()} and cannot "
                          f"be cancelled.")
            return redirect("procurement:rtv_detail", pk=pk)
    write_audit_log(request.user, obj, "update",
                    {"action": "cancel", "reason": obj.cancellation_reason[:200]})
    messages.success(request, f"Return {obj.number} cancelled.")
    return redirect("procurement:rtv_detail", pk=pk)
