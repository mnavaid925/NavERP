"""SCM 4.1 Procurement Management — GoodsReceiptNotes views (incl. the three-way match)."""
from apps.scm.views._common import *  # noqa: F401,F403
# `import *` skips underscore-prefixed names, so private helpers need an explicit import.
from apps.scm.views._common import _changed
from apps.scm.views._helpers import (_need_tenant, _supplier_parties,
                                     _post_grn_receipt, _reverse_grn_receipt)
from apps.scm.models import (
    GoodsReceiptNote,
)
from apps.scm.forms import (
    GoodsReceiptNoteForm,
    GoodsReceiptLineFormSet,
)


@login_required
def goodsreceipt_list(request):
    qs = (GoodsReceiptNote.objects
          .filter(tenant=request.tenant)
          .select_related("purchase_order", "purchase_order__vendor", "bill", "received_by"))
    return crud_list(
        request, qs, "scm/procurement/goodsreceipt/list.html",
        search_fields=["number", "delivery_note_ref", "purchase_order__number",
                       "purchase_order__vendor__name"],
        filters=[
            ("status", "status", False),
            ("match_status", "match_status", False),
            ("vendor", "purchase_order__vendor_id", True),
        ],
        extra_context={
            "status_choices": GoodsReceiptNote.STATUS_CHOICES,
            "match_status_choices": GoodsReceiptNote.MATCH_STATUS_CHOICES,
            "vendors": _supplier_parties(request.tenant),
        },
    )


@login_required
def goodsreceipt_create(request):
    return _goodsreceipt_form(request, instance=None)


@login_required
def goodsreceipt_edit(request, pk):
    obj = get_object_or_404(GoodsReceiptNote, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft receipt can be edited.")
        return redirect("scm:goodsreceipt_detail", pk=pk)
    return _goodsreceipt_form(request, instance=obj)


def _goodsreceipt_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("scm:goodsreceipt_list")
    is_edit = instance is not None
    # The line formset's `po_line` dropdown must be scoped to the receipt's own order. On a fresh
    # create there is no order chosen yet, so the lines are added on a second pass (edit) once the
    # header names the PO — the formset falls back to an empty queryset rather than every tenant's.
    purchase_order = instance.purchase_order if instance is not None else None
    if request.method == "POST":
        form = GoodsReceiptNoteForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            purchase_order = form.cleaned_data.get("purchase_order") or purchase_order
        formset = GoodsReceiptLineFormSet(request.POST, instance=instance,
                                          purchase_order=purchase_order,
                                          form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                grn = form.save(commit=False)
                grn.tenant = request.tenant
                if not is_edit:
                    grn.received_by = request.user
                grn.save()
                formset.instance = grn
                formset.save()
                grn.recompute_match()
            write_audit_log(request.user, grn, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Receipt {grn.number} saved.")
            return redirect("scm:goodsreceipt_detail", pk=grn.pk)
    else:
        form = GoodsReceiptNoteForm(instance=instance, tenant=request.tenant)
        formset = GoodsReceiptLineFormSet(instance=instance, purchase_order=purchase_order,
                                          form_kwargs={"tenant": request.tenant})
    return render(request, "scm/procurement/goodsreceipt/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance,
                   "purchase_order": purchase_order})


@login_required
def goodsreceipt_detail(request, pk):
    obj = get_object_or_404(
        GoodsReceiptNote.objects.select_related(
            "purchase_order", "purchase_order__vendor", "bill", "received_by"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "scm/procurement/goodsreceipt/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("po_line"),
        # Both are NET of tax so the page shows the same like-for-like pair the match itself uses.
        "received_value": obj.received_value(),
        "billed_total": obj.billed_value() if obj.bill_id else None,
    })


@login_required
@require_POST
def goodsreceipt_delete(request, pk):
    obj = get_object_or_404(GoodsReceiptNote, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft receipt can be deleted — cancel it instead.")
        return redirect("scm:goodsreceipt_detail", pk=pk)
    return crud_delete(request, model=GoodsReceiptNote, pk=pk, success_url="scm:goodsreceipt_list")


@tenant_admin_required
@require_POST
def goodsreceipt_receive(request, pk):
    """Book the receipt: draft -> received, post the inbound stock, re-derive status and the match.

    Tenant-admin gated since 4.4: this now MOVES STOCK (it raises on-hand), which puts it in the
    same class as transfer-complete and adjustment-post. The row is locked and its status re-read
    inside the transaction so two concurrent bookings can't both post the inbound moves.
    """
    try:
        with transaction.atomic():
            obj = get_object_or_404(
                GoodsReceiptNote.objects.select_for_update().select_related("purchase_order", "location"),
                pk=pk, tenant=request.tenant)
            if obj.status != "draft":
                messages.info(request, "This receipt has already been booked.")
                return redirect("scm:goodsreceipt_detail", pk=pk)
            if not obj.lines.exists():
                messages.error(request, "Add at least one line before booking the receipt.")
                return redirect("scm:goodsreceipt_detail", pk=pk)
            obj.status = "received"
            obj.save(update_fields=["status", "updated_at"])
            # The inventory effect — receipts raise on-hand at the receiving location.
            posted, unmatched, blocked = _post_grn_receipt(obj, request.user)
            # Re-match every receipt on the order, not just this one: this booking changes the
            # per-line received aggregate that the siblings' verdicts are derived from.
            obj.purchase_order.rematch_receipts()
            obj.purchase_order.recompute_receipt_status()
            obj.refresh_from_db(fields=["match_status", "match_notes"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:goodsreceipt_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "receive", "moves_posted": posted})
    messages.success(request, f"Receipt {obj.number} booked — {posted} stock movement(s) posted.")
    if blocked:
        # A workspace-level reason nothing could post, kept separate from the per-line SKU misses
        # below so the two don't read as the same problem.
        messages.warning(request, f"No stock was posted for this receipt — {blocked}.")
    if unmatched:
        # Surfaced rather than swallowed: 4.1 lines are free text, so a line whose SKU matches no
        # item master row cannot post a move. The buyer needs to know stock did NOT rise for it.
        messages.warning(request, (
            f"No stock posted for {len(unmatched)} line(s) — no item matches their SKU: "
            f"{', '.join(unmatched[:3])}{'…' if len(unmatched) > 3 else ''}."))
    return redirect("scm:goodsreceipt_detail", pk=pk)


@tenant_admin_required
@require_POST
def goodsreceipt_cancel(request, pk):
    """Reverse a booked receipt, including the stock it brought in.

    Tenant-admin gated, matching purchaseorder_cancel: cancelling drops the receipt out of the
    per-line received aggregate, walks the order's status backward, and re-derives the three-way
    match verdict on every sibling — i.e. it directly moves the control that decides whether a
    vendor bill should be paid. That is not a plain @login_required action.

    Since 4.4 it also unwinds the inventory effect by posting COMPENSATING moves — the ledger is
    append-only, so a cancellation never deletes the originals. The reversal is guarded: if the
    received stock has already been put away into a bin, cancelling is REFUSED (the whole
    transaction rolls back, so the receipt stays 'received') rather than driving the staging
    location negative. Un-picking that stock is a putaway decision, not a receipt one.
    """
    try:
        with transaction.atomic():
            obj = get_object_or_404(
                GoodsReceiptNote.objects.select_for_update().select_related("purchase_order"),
                pk=pk, tenant=request.tenant)
            if obj.status == "cancelled":
                messages.info(request, "This receipt is already cancelled.")
                return redirect("scm:goodsreceipt_detail", pk=pk)
            was_received = obj.status == "received"
            obj.status = "cancelled"
            obj.save(update_fields=["status", "updated_at"])
            # Only a receipt that actually posted stock has anything to reverse.
            reversed_count = _reverse_grn_receipt(obj, request.user) if was_received else 0
            # Cancelling drops this receipt out of the received aggregate, so the siblings' verdicts
            # need re-deriving too.
            obj.purchase_order.rematch_receipts()
            obj.purchase_order.recompute_receipt_status()
            obj.refresh_from_db(fields=["match_status", "match_notes"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:goodsreceipt_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "cancel", "moves_reversed": reversed_count})
    if reversed_count:
        messages.success(request, f"Receipt {obj.number} cancelled — {reversed_count} stock movement(s) reversed.")
    else:
        messages.success(request, f"Receipt {obj.number} cancelled.")
    return redirect("scm:goodsreceipt_detail", pk=pk)


@login_required
@require_POST
def goodsreceipt_rematch(request, pk):
    """Re-run the three-way match — used after the linked bill changes."""
    obj = get_object_or_404(GoodsReceiptNote.objects.select_related("bill"), pk=pk, tenant=request.tenant)
    status = obj.recompute_match()
    write_audit_log(request.user, obj, "update", {"action": "rematch", "match_status": status})
    messages.success(request, f"Match re-checked: {obj.get_match_status_display()}.")
    return redirect("scm:goodsreceipt_detail", pk=pk)
