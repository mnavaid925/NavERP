"""HRM 3.5 Job Requisition — Approvals views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    JobRequisition,
    RequisitionApproval,
)
from apps.hrm.forms import (
    RequisitionApprovalForm,
)


# --- Approval chain steps (inline on the requisition hub; admin-only, steps only before submit) ---
@tenant_admin_required
@require_POST
def approval_add(request, jr_pk):
    req = get_object_or_404(JobRequisition, pk=jr_pk, tenant=request.tenant)
    if req.status != "draft":
        messages.error(request, "Approval steps can only be added while the requisition is a draft.")
        return redirect("hrm:jobrequisition_detail", pk=req.pk)
    form = RequisitionApprovalForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        step = form.save(commit=False)
        step.tenant = request.tenant
        step.requisition = req
        step.status = "pending"
        try:
            step.save()
        except IntegrityError:
            messages.error(request, f"An approval step #{step.step_order} already exists.")
            return redirect("hrm:jobrequisition_detail", pk=req.pk)
        write_audit_log(request.user, step, "create", {"action": "add_approval_step",
                                                        "step": step.step_order})
        messages.success(request, f"Approval step #{step.step_order} added.")
    else:
        messages.error(request, "Could not add the approval step — check the step order and approver.")
    return redirect("hrm:jobrequisition_detail", pk=req.pk)


@tenant_admin_required
@require_POST
def approval_delete(request, pk):
    step = get_object_or_404(RequisitionApproval.objects.select_related("requisition"),
                             pk=pk, tenant=request.tenant)
    req = step.requisition
    if req.status != "draft":
        messages.error(request, "Approval steps can only be removed while the requisition is a draft.")
        return redirect("hrm:jobrequisition_detail", pk=req.pk)
    write_audit_log(request.user, step, "delete", {"action": "remove_approval_step",
                                                   "step": step.step_order})
    step.delete()
    messages.success(request, "Approval step removed.")
    return redirect("hrm:jobrequisition_detail", pk=req.pk)
