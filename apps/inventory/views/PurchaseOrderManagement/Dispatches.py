"""Inventory 5.3 Purchase Order (PO) Management — PurchaseOrderDispatch views.

**PO Dispatch bullet** — the transmission log over spine orders. There is deliberately NO
edit view: a dispatch record is proof of what left, and rewriting it would falsify the
proof. A mistaken entry is corrected by recording the real transmission as another row;
deleting a bogus row stays possible (POST + confirm) with its provenance in core.AuditLog.
"""
from django.db import transaction

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import PurchaseOrderDispatchForm
from apps.inventory.forms.PurchaseOrderManagement.Dispatches import _dispatchable_orders
from apps.inventory.models import PurchaseOrderDispatch
from apps.scm.models import PurchaseOrder


@login_required
def dispatch_list(request):
    qs = (PurchaseOrderDispatch.objects.filter(tenant=request.tenant)
          .select_related("purchase_order", "purchase_order__vendor"))
    return crud_list(
        request, qs, "inventory/po/dispatch/list.html",
        search_fields=["number", "recipient", "reference", "note",
                       "purchase_order__number", "purchase_order__vendor__name"],
        filters=[("channel", "channel", False), ("po", "purchase_order_id", True)],
        extra_context={
            "channel_choices": PurchaseOrderDispatch.CHANNEL_CHOICES,
            "orders": _dispatchable_orders(request.tenant)[:100],
        },
    )


@login_required
def dispatch_create(request):
    """Record a transmission; the FIRST one on an approved order sends it.

    The approved→sent flip is the spine's own transition (scm's ``purchaseorder_send``
    semantics), performed in the same transaction as the log row so the status can never
    claim ``sent`` without a recorded dispatch behind it.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before recording dispatches.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = PurchaseOrderDispatchForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                dispatch = form.save(commit=False)
                dispatch.tenant = request.tenant
                dispatch.save()
                po = dispatch.purchase_order
                sent_now = False
                if po.status == "approved":
                    po.status = "sent"
                    po.save(update_fields=["status", "updated_at"])
                    sent_now = True
            write_audit_log(request.user, dispatch, "create")
            if sent_now:
                write_audit_log(request.user, po, "update", {"action": "send"})
            messages.success(
                request, f"Dispatch {dispatch.number} recorded for order {po.number}.")
            return redirect("inventory:dispatch_detail", pk=dispatch.pk)
    else:
        form = PurchaseOrderDispatchForm(tenant=request.tenant)
    return render(request, "inventory/po/dispatch/form.html", {
        "form": form,
        "is_edit": False,
    })


@login_required
def dispatch_detail(request, pk):
    obj = get_object_or_404(
        PurchaseOrderDispatch.objects.select_related("purchase_order",
                                                     "purchase_order__vendor"),
        pk=pk, tenant=request.tenant)
    return render(request, "inventory/po/dispatch/detail.html", {
        "obj": obj,
        # The same order's other transmissions — scoped + self-excluded here rather than
        # trusted from the reverse relation (the VendorCommunication sibling rule).
        "siblings": (PurchaseOrderDispatch.objects
                     .filter(tenant=request.tenant, purchase_order=obj.purchase_order)
                     .exclude(pk=obj.pk)[:8]),
    })


@login_required
@require_POST
def dispatch_delete(request, pk):
    return crud_delete(request, model=PurchaseOrderDispatch, pk=pk,
                       success_url="inventory:dispatch_list")
