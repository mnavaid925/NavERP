"""Procurement 6.10 Purchase Order Management — requisition -> PO generation views.

**PO Generation** bullet: automated creation of POs from approved requisitions (manual entry
lives on the spine at ``scm:purchaseorder_create``). The console lists approved requisitions;
generating asks exactly one real question (which supplier) and drafts a DRAFT order on the
spine — 4.1's submit/approve/send machinery owns everything after that.
"""
from django.db import transaction

from apps.procurement.forms import GeneratePOForm
from apps.procurement.models import convertible_requisitions, generate_po_from_requisition
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseRequisition


@login_required
def po_generation(request):
    """The generation console: approved requisitions, oldest backlog first."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to view the generation queue.")
        return redirect("dashboard:home")
    return crud_list(
        request, convertible_requisitions(request.tenant),
        "procurement/purchaseordermanagement/generation.html",
        search_fields=["number", "title"],
    )


@login_required
def po_generate(request, requisition_pk):
    """Draft one PO from an approved requisition.

    The approved-ness re-check happens INSIDE a row lock on the requisition, so two buyers
    hitting Generate simultaneously both get their own order rather than a race — splitting one
    requisition across vendors is legitimate, not a conflict.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before generating orders.")
        return redirect("dashboard:home")

    with transaction.atomic():
        requisition = get_object_or_404(PurchaseRequisition.objects.select_for_update(),
                                        pk=requisition_pk, tenant=request.tenant)
        if requisition.status != "approved":
            messages.error(request,
                           f"Only approved requisitions can generate orders — this one is "
                           f"{requisition.get_status_display().lower()}.")
            return redirect("procurement:po_generation")
        if not requisition.lines.exists():
            messages.error(request, "This requisition has no lines to copy into an order.")
            return redirect("procurement:po_generation")

        if request.method == "POST":
            form = GeneratePOForm(request.POST, tenant=request.tenant)
            if form.is_valid():
                order = generate_po_from_requisition(
                    requisition,
                    vendor=form.cleaned_data["vendor"],
                    expected_date=form.cleaned_data.get("expected_date"),
                )
                write_audit_log(request.user, requisition, "update",
                                {"action": "generate_po", "order": order.number})
                messages.success(request,
                                 f"Draft order {order.number} created from {requisition.number} "
                                 f"— it starts as a draft; submit, approve and send it from the "
                                 f"order page.")
                return redirect("scm:purchaseorder_detail", pk=order.pk)
        else:
            form = GeneratePOForm(tenant=request.tenant)

    return render(request, "procurement/purchaseordermanagement/generate.html", {
        "form": form,
        "requisition": requisition,
        "lines": list(requisition.lines.order_by("id")),
        "linked_orders": list(requisition.purchase_orders.all()),
    })
