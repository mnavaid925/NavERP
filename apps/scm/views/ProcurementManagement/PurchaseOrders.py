"""SCM 4.1 Procurement Management — PurchaseOrders views."""
from apps.scm.views._common import *  # noqa: F401,F403
# `import *` skips underscore-prefixed names, so private helpers need an explicit import.
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _supplier_parties
from apps.scm.models import (
    PurchaseOrder,
)
from apps.scm.forms import (
    PurchaseOrderForm,
    PurchaseOrderLineFormSet,
    PurchaseOrderAcknowledgeForm,
)


@login_required
def purchaseorder_list(request):
    qs = (PurchaseOrder.objects
          .filter(tenant=request.tenant)
          .select_related("vendor", "currency", "requisition"))
    return crud_list(
        request, qs, "scm/procurement/purchaseorder/list.html",
        search_fields=["number", "vendor__name", "notes"],
        filters=[("status", "status", False), ("vendor", "vendor_id", True)],
        extra_context={
            "status_choices": PurchaseOrder.STATUS_CHOICES,
            "vendors": _supplier_parties(request.tenant),
        },
    )


@login_required
def purchaseorder_create(request):
    return _purchaseorder_form(request, instance=None)


@login_required
def purchaseorder_edit(request, pk):
    obj = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "A dispatched order cannot be edited directly — amend it instead.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    return _purchaseorder_form(request, instance=obj)


# An amendment revises the terms of an existing commitment. Swapping who it is with, or what money
# it is in, is not an amendment — it is a different order. Locking these on the amend path also
# closes the tampering hole, since `disabled` makes Django ignore the POSTed value entirely.
AMEND_LOCKED_FIELDS = ("vendor", "currency", "requisition", "quote")


def _lock_identity_fields(form):
    for name in AMEND_LOCKED_FIELDS:
        if name in form.fields:
            form.fields[name].disabled = True


def _purchaseorder_form(request, instance, amending=False):
    if instance is None and _need_tenant(request):
        return redirect("scm:purchaseorder_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST, request.FILES, instance=instance, tenant=request.tenant)
        if amending:
            _lock_identity_fields(form)
        formset = PurchaseOrderLineFormSet(request.POST, instance=instance,
                                           form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                po = form.save(commit=False)
                po.tenant = request.tenant
                if amending:
                    po.version = (po.version or 1) + 1
                    po.amendment_reason = (request.POST.get("amendment_reason") or "").strip()[:2000]
                po.save()
                formset.instance = po
                formset.save()
                po.recalc_totals()
            action = "amend" if amending else ("update" if is_edit else "create")
            # The field-level diff is the whole point of the amendment trail — without it the
            # version bump records THAT the order changed but never WHAT changed.
            write_audit_log(request.user, po, "update" if is_edit else "create",
                            {"action": action, "version": po.version, **_changed(form)})
            messages.success(request, f"Order {po.number} saved.")
            return redirect("scm:purchaseorder_detail", pk=po.pk)
    else:
        form = PurchaseOrderForm(instance=instance, tenant=request.tenant)
        if amending:
            _lock_identity_fields(form)
        formset = PurchaseOrderLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/procurement/purchaseorder/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance,
                   "amending": amending})


@tenant_admin_required
def purchaseorder_amend(request, pk):
    """Edit an already-dispatched order, bumping its version and recording why.

    A dispatched PO is a commitment to the vendor, so it is not silently editable — the amendment
    trail (version + reason + the AuditLog field diff) is what makes the change defensible later.

    Tenant-admin gated, like approve and cancel. This is the one path that re-opens the line
    formset — quantity, unit price, tax, GL account — on an order that has ALREADY cleared the
    approval gate, and it leaves the order in its dispatched status without re-approval. Leaving it
    at @login_required let any employee inflate the committed total of a live vendor commitment,
    which is strictly more dangerous than the cancel it sits next to.
    """
    obj = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if obj.is_editable:
        return redirect("scm:purchaseorder_edit", pk=pk)
    if obj.is_closed:
        messages.error(request, "A cancelled or closed order cannot be amended.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    if request.method == "POST" and not (request.POST.get("amendment_reason") or "").strip():
        messages.error(request, "Give a reason for the amendment.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    return _purchaseorder_form(request, instance=obj, amending=True)


@login_required
def purchaseorder_detail(request, pk):
    obj = get_object_or_404(
        PurchaseOrder.objects.select_related(
            "vendor", "currency", "payment_terms", "requisition", "quote", "ship_to", "approved_by"),
        pk=pk, tenant=request.tenant,
    )
    lines = list(obj.lines.select_related("gl_account"))
    # Resolve every line's received quantity in ONE query and prime each line's memo, so neither
    # the fully_received check below nor the template's per-row {{ line.received_quantity }} pays
    # for its own aggregate. Without this a PO with N lines costs ~2N extra queries to render.
    received_map = obj.received_by_line()
    for line in lines:
        line._received_qty_cache = received_map.get(line.pk, Decimal("0"))
    return render(request, "scm/procurement/purchaseorder/detail.html", {
        "obj": obj,
        "lines": lines,
        "receipts": obj.receipts.select_related("bill").only(
            "id", "number", "receipt_date", "status", "match_status", "bill__number"),
        "ack_form": PurchaseOrderAcknowledgeForm(),
        "fully_received": bool(lines) and all(l.received_quantity() >= l.quantity for l in lines),
    })


@login_required
@require_POST
def purchaseorder_delete(request, pk):
    obj = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft order can be deleted — cancel it instead.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    if obj.receipts.exists():
        messages.error(request, "This order has goods receipts booked against it and cannot be deleted.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    return crud_delete(request, model=PurchaseOrder, pk=pk, success_url="scm:purchaseorder_list")


@login_required
@require_POST
def purchaseorder_submit(request, pk):
    obj = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, "This order has already been submitted.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    if not obj.lines.exists():
        messages.error(request, "Add at least one line before submitting.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    obj.recalc_totals()
    obj.status = "pending_approval"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "submit"})
    messages.success(request, f"Order {obj.number} submitted for approval.")
    return redirect("scm:purchaseorder_detail", pk=pk)


@tenant_admin_required
@require_POST
def purchaseorder_approve(request, pk):
    """Approve a pending order. Tenant-admin gated — this commits tenant money to a vendor."""
    obj = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.info(request, "This order is not awaiting approval.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    obj.recalc_totals()
    obj.status = "approved"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve"})
    messages.success(request, f"Order {obj.number} approved.")
    return redirect("scm:purchaseorder_detail", pk=pk)


@login_required
@require_POST
def purchaseorder_send(request, pk):
    obj = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved order can be sent to the vendor.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    obj.status = "sent"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "send"})
    messages.success(request, f"Order {obj.number} marked as sent to {obj.vendor}.")
    return redirect("scm:purchaseorder_detail", pk=pk)


@login_required
@require_POST
def purchaseorder_acknowledge(request, pk):
    """Record the vendor's acknowledgement of an order.

    STAFF-side by design. NavERP 4.1's "Vendor Portal" bullet asks for suppliers to acknowledge
    orders and give a ship date; lesson L32 bars a staff sidebar bullet from pointing at a
    login-gated portal page, so the buyer records the acknowledgement here instead. A real supplier
    self-service portal is deferred — these are the fields it would write.
    """
    obj = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if obj.status != "sent":
        messages.error(request, "Only a sent order can be acknowledged.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    form = PurchaseOrderAcknowledgeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Could not record the acknowledgement — check the ship date.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    obj.status = "acknowledged"
    obj.acknowledged_at = timezone.now()
    obj.acknowledgement_note = form.cleaned_data.get("acknowledgement_note") or ""
    obj.promised_ship_date = form.cleaned_data.get("promised_ship_date")
    obj.save(update_fields=["status", "acknowledged_at", "acknowledgement_note",
                            "promised_ship_date", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
    messages.success(request, f"Order {obj.number} acknowledged by {obj.vendor}.")
    return redirect("scm:purchaseorder_detail", pk=pk)


@tenant_admin_required
@require_POST
def purchaseorder_cancel(request, pk):
    """Cancel an order. Tenant-admin gated and reason-required — this is a commitment being broken."""
    obj = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if obj.is_closed:
        messages.info(request, "This order is already cancelled or closed.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    reason = (request.POST.get("cancellation_reason") or "").strip()
    if not reason:
        messages.error(request, "Give a reason when cancelling an order.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    if obj.receipts.exclude(status="cancelled").exists():
        messages.error(request, "Goods have been received against this order — it cannot be cancelled.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    obj.status = "cancelled"
    obj.cancelled_at = timezone.now()
    obj.cancellation_reason = reason[:2000]
    obj.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Order {obj.number} cancelled.")
    return redirect("scm:purchaseorder_detail", pk=pk)


@login_required
@require_POST
def purchaseorder_close(request, pk):
    obj = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if obj.status != "received":
        messages.error(request, "Only a fully received order can be closed.")
        return redirect("scm:purchaseorder_detail", pk=pk)
    obj.status = "closed"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "close"})
    messages.success(request, f"Order {obj.number} closed.")
    return redirect("scm:purchaseorder_detail", pk=pk)
