"""Procurement 6.10 Purchase Order Management — PurchaseOrderChange views.

**PO Change Order Management** bullet: modify quantity, price or delivery date on an ACTIVE
purchase order. Filing is open to any workspace member (the change names its filer); deciding
is tenant-admin gated because ONLY the approve action mutates the ``scm.PurchaseOrder`` spine —
inside one transaction under a row lock on the order. Mirrors 6.2's requisition amendments.
"""
from django.db import transaction

from apps.procurement.forms import (
    ChangeOrderDecisionForm,
    PurchaseOrderChangeForm,
    PurchaseOrderChangeLineFormSet,
)
from apps.procurement.models import PurchaseOrderChange
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseOrder

#: Line-form fields that count as "this row actually proposes something" when checking whether a
#: cancellation accidentally carries line changes.
_LINE_DATA_FIELDS = ("target_line", "item_description", "quantity", "unit_price", "tax_rate_pct")


@login_required
def poc_create(request, purchase_order_pk):
    """File a change order against one purchase order (any workspace member; an admin decides).

    The status + one-open-change guards run INSIDE a row lock on the order, so two simultaneous
    filings cannot both slip past the one-pending-change rule.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before filing change orders.")
        return redirect("dashboard:home")

    with transaction.atomic():
        order = get_object_or_404(PurchaseOrder.objects.select_for_update(),
                                  pk=purchase_order_pk, tenant=request.tenant)
        if order.status not in PurchaseOrderChange.CHANGEABLE_STATUSES:
            messages.error(request,
                           f"A {order.get_status_display().lower()} purchase order cannot take a "
                           f"change order — drafts and pending approvals edit directly; cancelled "
                           f"and closed ones are finished.")
            return redirect("scm:purchaseorder_detail", pk=order.pk)
        if PurchaseOrderChange.has_open_for(order):
            messages.error(request,
                           f"Order {order.number} already has a pending change order — decide it "
                           f"before filing another.")
            return redirect("scm:purchaseorder_detail", pk=order.pk)

        change = PurchaseOrderChange(purchase_order=order, requested_by=request.user)
        if request.method == "POST":
            form = PurchaseOrderChangeForm(request.POST, instance=change,
                                           tenant=request.tenant)
            formset = PurchaseOrderChangeLineFormSet(request.POST, instance=change,
                                                     form_kwargs={"tenant": request.tenant})
            if form.is_valid() and formset.is_valid():
                if (form.cleaned_data.get("change_type") == "cancel"
                        and _formset_proposes_changes(formset)):
                    form.add_error(None,
                                   "Line changes apply only to 'Change details' — switch the "
                                   "type or remove the proposed line rows.")
                else:
                    change.tenant = request.tenant
                    change.requested_by = request.user
                    change.save()
                    formset.instance = change
                    formset.save()
                    write_audit_log(request.user, change, "create",
                                    {"purchase_order": order.number})
                    messages.success(request,
                                     f"Change order {change.number} filed — it now waits for a "
                                     f"workspace admin to decide.")
                    return redirect("procurement:poc_detail", pk=change.pk)
        else:
            form = PurchaseOrderChangeForm(instance=change, tenant=request.tenant)
            formset = PurchaseOrderChangeLineFormSet(instance=change,
                                                     form_kwargs={"tenant": request.tenant})

    return render(request, "procurement/purchaseordermanagement/changes/form.html", {
        "form": form,
        "formset": formset,
        "obj": None,
        "order": order,
        "order_lines": list(order.lines.order_by("id")),
    })


def _formset_proposes_changes(formset):
    """True when any non-deleted row of the formset actually proposes something."""
    for form in formset.forms:
        if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
            continue
        data = form.cleaned_data
        if any(data.get(field) for field in _LINE_DATA_FIELDS):
            return True
        if data.get("action") == "remove":
            return True
    return False



@login_required
def poc_list(request):
    qs = (PurchaseOrderChange.objects.filter(tenant=request.tenant)
          .select_related("purchase_order", "requested_by", "decided_by"))
    return crud_list(
        request, qs, "procurement/purchaseordermanagement/changes/list.html",
        search_fields=["number", "reason"],
        filters=[("status", "status", False), ("type", "change_type", False)],
        extra_context={
            "status_choices": PurchaseOrderChange.STATUS_CHOICES,
            "type_choices": PurchaseOrderChange.CHANGE_TYPES,
        },
    )


@login_required
def poc_detail(request, pk):
    obj = get_object_or_404(
        PurchaseOrderChange.objects.select_related(
            "purchase_order", "requested_by", "decided_by"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "procurement/purchaseordermanagement/changes/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("target_line").order_by("id"),
        "decision_form": ChangeOrderDecisionForm(),
    })


@login_required
@tenant_admin_required
@require_POST
def poc_approve(request, pk):
    """Decide YES and apply atomically. Tenant-admin gated: this is the one path that mutates a
    dispatched purchase order. The change row is locked and its pending-ness re-checked INSIDE
    the transaction, so a double-submit cannot apply twice; the order's row is locked inside
    apply() by the same transaction, so a concurrent spine edit cannot interleave."""
    with transaction.atomic():
        obj = get_object_or_404(PurchaseOrderChange.objects.select_for_update()
                                .select_related("purchase_order"),
                                pk=pk, tenant=request.tenant)
        if not obj.is_pending:
            messages.info(request, "This change order has already been decided.")
            return redirect("procurement:poc_detail", pk=pk)
        order = obj.purchase_order
        if order.status not in PurchaseOrderChange.CHANGEABLE_STATUSES:
            messages.error(request,
                           f"The purchase order is now '{order.get_status_display()}' — "
                           f"there is nothing left to change. Reject this change order instead.")
            return redirect("procurement:poc_detail", pk=pk)

        summary = obj.apply(request.user, note=request.POST.get("decision_note") or "")
        # The spine changed too — record it on the ORDER's trail so its timeline shows the
        # change order landing, not just on the change's own row.
        write_audit_log(request.user, order, "update",
                        {"action": f"change_{obj.change_type}", "change": obj.number})
    write_audit_log(request.user, obj, "update", {"action": "approve", "applied": summary})
    messages.success(request, f"Change order {obj.number} approved and applied ({summary}).")
    return redirect("procurement:poc_detail", pk=pk)


@login_required
@tenant_admin_required
@require_POST
def poc_reject(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(PurchaseOrderChange.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.is_pending:
            messages.info(request, "This change order has already been decided.")
            return redirect("procurement:poc_detail", pk=pk)
        note = (request.POST.get("decision_note") or "").strip()
        if not note:
            messages.error(request, "Give a reason when rejecting a change order.")
            return redirect("procurement:poc_detail", pk=pk)
        obj.status = "rejected"
        obj.decided_by = request.user
        obj.decided_at = timezone.now()
        obj.decision_note = note[:2000]
        obj.save(update_fields=["status", "decided_by", "decided_at", "decision_note",
                                "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Change order {obj.number} rejected.")
    return redirect("procurement:poc_detail", pk=pk)
