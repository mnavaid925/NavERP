"""CRM 1.10 Automation & Workflow Engine — Approvals views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    ApprovalRequest,
)
from apps.crm.forms import (
    ApprovalRequestForm,
)


# ------------------------------------------------------------ 1.10 Approval requests
@login_required
def approvalrequest_list(request):
    return crud_list(
        request,
        ApprovalRequest.objects.filter(tenant=request.tenant).select_related(
            "approver", "requested_by", "rule"),
        "crm/workflow/approvalrequest/list.html",
        search_fields=["number", "subject", "record_label"],
        filters=[("status", "status", False), ("approver", "approver_id", True)],
        extra_context={"status_choices": ApprovalRequest.STATUS_CHOICES,
                       "approvers": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


@login_required
def approvalrequest_create(request):
    return crud_create(request, form_class=ApprovalRequestForm,
                       template="crm/workflow/approvalrequest/form.html", success_url="crm:approvalrequest_list")


@login_required
def approvalrequest_detail(request, pk):
    obj = get_object_or_404(
        ApprovalRequest.objects.select_related("approver", "requested_by", "rule"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/approvalrequest/detail.html", {"obj": obj})


@login_required
def approvalrequest_edit(request, pk):
    return crud_edit(request, model=ApprovalRequest, pk=pk, form_class=ApprovalRequestForm,
                     template="crm/workflow/approvalrequest/form.html", success_url="crm:approvalrequest_list")


@login_required
@require_POST
def approvalrequest_delete(request, pk):
    return crud_delete(request, model=ApprovalRequest, pk=pk, success_url="crm:approvalrequest_list")


@tenant_admin_required  # approval decisions are privileged (manager/admin only)
@require_POST
def approvalrequest_approve(request, pk):
    obj = get_object_or_404(ApprovalRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "approved"
        obj.approved_at = timezone.now()
        obj.reason = request.POST.get("reason", obj.reason)
        obj.save(update_fields=["status", "approved_at", "reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, f"{obj.number} approved.")
    return redirect("crm:approvalrequest_detail", pk=obj.pk)


@tenant_admin_required  # approval decisions are privileged (manager/admin only)
@require_POST
def approvalrequest_reject(request, pk):
    obj = get_object_or_404(ApprovalRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.rejected_at = timezone.now()
        obj.reason = request.POST.get("reason", obj.reason)
        obj.save(update_fields=["status", "rejected_at", "reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"{obj.number} rejected.")
    return redirect("crm:approvalrequest_detail", pk=obj.pk)
