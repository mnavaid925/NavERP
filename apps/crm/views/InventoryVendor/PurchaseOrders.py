"""CRM 1.12 Inventory & Vendor Management — PurchaseOrders views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    ProductStock,
    PurchaseOrder,
    PurchaseOrderLine,
)
from apps.crm.forms import (
    PurchaseOrderForm,
    PurchaseOrderLineForm,
)


# ------------------------------------------------------------ 1.12 Purchase orders
@login_required
def crm_po_list(request):
    return crud_list(
        request,
        PurchaseOrder.objects.filter(tenant=request.tenant).select_related("vendor", "owner"),
        "crm/vendor/crm_po/list.html",
        search_fields=["number", "vendor__name", "notes"],
        filters=[("status", "status", False), ("vendor", "vendor_id", True)],
        extra_context={"status_choices": PurchaseOrder.STATUS_CHOICES,
                       "vendors": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")},
    )


@login_required
def crm_po_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            po = form.save(commit=False)
            po.tenant = request.tenant
            po.save()
            write_audit_log(request.user, po, "create")
            messages.success(request, f"Purchase order {po.number} created — add line items below.")
            return redirect("crm:crm_po_detail", pk=po.pk)
    else:
        form = PurchaseOrderForm(tenant=request.tenant)
    return render(request, "crm/vendor/crm_po/form.html", {"form": form, "is_edit": False})


@login_required
def crm_po_detail(request, pk):
    obj = get_object_or_404(PurchaseOrder.objects.select_related("vendor", "owner"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/vendor/crm_po/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("product").all(),
        "line_form": PurchaseOrderLineForm(tenant=request.tenant),
    })


@login_required
def crm_po_edit(request, pk):
    return crud_edit(request, model=PurchaseOrder, pk=pk, form_class=PurchaseOrderForm,
                     template="crm/vendor/crm_po/form.html", success_url="crm:crm_po_list")


@login_required
@require_POST
def crm_po_delete(request, pk):
    return crud_delete(request, model=PurchaseOrder, pk=pk, success_url="crm:crm_po_list")


@login_required
@require_POST
def crm_po_add_line(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    form = PurchaseOrderLineForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        with transaction.atomic():
            line = form.save(commit=False)
            line.tenant = request.tenant
            line.purchase_order = po
            line.order = po.lines.count()  # append after existing lines
            line.save()
            po.recalc_total()
        messages.success(request, "Line item added.")
    else:
        messages.error(request, "Could not add line — item name is required.")
    return redirect("crm:crm_po_detail", pk=po.pk)


@login_required
@require_POST
def crm_po_remove_line(request, pk, line_pk):
    po = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    line = get_object_or_404(PurchaseOrderLine, pk=line_pk, purchase_order=po, tenant=request.tenant)
    with transaction.atomic():
        line.delete()
        po.recalc_total()
    messages.success(request, "Line item removed.")
    return redirect("crm:crm_po_detail", pk=po.pk)


@tenant_admin_required  # receiving mutates inventory (irreversible) — privileged action
@require_POST
def crm_po_receive(request, pk):
    """1.12: mark a PO received and add its quantities to linked ProductStock on-hand."""
    po = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.tenant)
    if po.status not in ("draft", "sent"):
        messages.info(request, "Only a draft or sent purchase order can be received.")
        return redirect("crm:crm_po_detail", pk=po.pk)
    with transaction.atomic():
        for line in po.lines.select_related("product"):
            if line.product_id:
                ProductStock.objects.filter(pk=line.product_id, tenant=request.tenant).update(
                    on_hand_qty=F("on_hand_qty") + line.quantity)
        po.status = "received"
        po.received_at = timezone.now()
        po.save(update_fields=["status", "received_at", "updated_at"])
    write_audit_log(request.user, po, "update", {"action": "receive"})
    messages.success(request, f"PO {po.number} received — stock levels updated.")
    return redirect("crm:crm_po_detail", pk=po.pk)
