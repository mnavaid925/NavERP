"""HRM 3.8 Offer Management — Offerapprovals views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Offer,
    OfferApproval,
)
from apps.hrm.forms import (
    OfferApprovalForm,
)


# --- Offer approval-chain steps (inline on the offer hub; admin-only, steps only before submit) ---
@tenant_admin_required
@require_POST
def offerapproval_add(request, pk):
    offer = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    if offer.status != "draft":
        messages.error(request, "Approval steps can only be added while the offer is a draft.")
        return redirect("hrm:offer_detail", pk=offer.pk)
    form = OfferApprovalForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        step = form.save(commit=False)
        step.tenant = request.tenant
        step.offer = offer
        step.status = "pending"
        try:
            step.save()
        except IntegrityError:
            messages.error(request, f"An approval step #{step.step_order} already exists.")
            return redirect("hrm:offer_detail", pk=offer.pk)
        write_audit_log(request.user, step, "create",
                        {"action": "add_offer_approval_step", "step": step.step_order})
        messages.success(request, f"Approval step #{step.step_order} added.")
    else:
        messages.error(request, "Could not add the approval step — check the step order and approver.")
    return redirect("hrm:offer_detail", pk=offer.pk)


@tenant_admin_required
@require_POST
def offerapproval_delete(request, pk):
    step = get_object_or_404(OfferApproval.objects.select_related("offer"), pk=pk, tenant=request.tenant)
    offer = step.offer
    if offer.status != "draft":
        messages.error(request, "Approval steps can only be removed while the offer is a draft.")
        return redirect("hrm:offer_detail", pk=offer.pk)
    write_audit_log(request.user, step, "delete",
                    {"action": "remove_offer_approval_step", "step": step.step_order})
    step.delete()
    messages.success(request, "Approval step removed.")
    return redirect("hrm:offer_detail", pk=offer.pk)
