"""Projects 7.14 Client & External Collaboration — ClientApprovalRequest views.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, crud_create, crud_delete, crud_edit, crud_list
from apps.core.utils import write_audit_log
from apps.projects.forms.ClientExternalCollaboration.ClientFeedbacks import ClientApprovalRequestForm
from apps.projects.models.ClientExternalCollaboration.ClientFeedbacks import ClientApprovalRequest
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import login_required


@login_required
def cfb_list(request):
    qs = (
        ClientApprovalRequest.objects.filter(tenant=request.tenant)
        .select_related("project", "document", "milestone", "requested_by", "assigned_contact")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/clientcollaboration/clientfeedback/list.html",
        search_fields=["number", "deliverable_name", "review_notes", "client_feedback", "signed_by_name"],
        filters=[
            ("status", "status", False),
        ],
        extra_context={
            "approval_list": qs,
            "projects": projects,
            "project_filter": project_id,
            "status_choices": ClientApprovalRequest.STATUS_CHOICES,
            "status_filter": request.GET.get("status", ""),
            "total_count": qs.count(),
        },
    )


@login_required
def cfb_create(request):
    if request.method == "POST":
        form = ClientApprovalRequestForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            req_obj = form.save(commit=False)
            req_obj.tenant = request.tenant
            if not req_obj.requested_by:
                req_obj.requested_by = request.user
            req_obj.save()
            write_audit_log(
                request.user,
                action="create",
                model_name="ClientApprovalRequest",
                object_id=req_obj.pk,
                changes={"number": req_obj.number, "deliverable": req_obj.deliverable_name},
            )
            messages.success(request, f"Client approval request {req_obj.number} created.")
            return redirect("projects:cfb_detail", pk=req_obj.pk)
    else:
        form = ClientApprovalRequestForm(tenant=request.tenant)

    return render(
        request,
        "projects/clientcollaboration/clientfeedback/form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def cfb_detail(request, pk):
    approval = get_object_or_404(
        ClientApprovalRequest.objects.select_related(
            "project", "document", "milestone", "requested_by", "assigned_contact"
        ),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "projects/clientcollaboration/clientfeedback/detail.html",
        {
            "obj": approval,
            "approval": approval,
        },
    )


@login_required
def cfb_edit(request, pk):
    approval = get_object_or_404(
        ClientApprovalRequest,
        pk=pk,
        tenant=request.tenant,
    )
    return crud_edit(
        request,
        model=ClientApprovalRequest,
        pk=pk,
        form_class=ClientApprovalRequestForm,
        template="projects/clientcollaboration/clientfeedback/form.html",
        success_url="projects:cfb_list",
        extra_context={"is_edit": True, "obj": approval, "approval": approval},
    )


@login_required
def cfb_delete(request, pk):
    return crud_delete(
        request,
        model=ClientApprovalRequest,
        pk=pk,
        success_url="projects:cfb_list",
    )


@login_required
@require_POST
def cfb_approve(request, pk):
    approval = get_object_or_404(
        ClientApprovalRequest,
        pk=pk,
        tenant=request.tenant,
    )
    if approval.status == "approved":
        messages.warning(request, f"Approval request {approval.number} is already approved.")
        return redirect("projects:cfb_detail", pk=pk)

    signer = request.POST.get("signed_by_name", "").strip()
    if not signer:
        signer = request.user.get_full_name() or request.user.username

    approval.status = "approved"
    approval.signed_by_name = signer
    approval.signed_at = timezone.now()
    approval.save()

    write_audit_log(
        request.user,
        action="approve",
        model_name="ClientApprovalRequest",
        object_id=approval.pk,
        changes={"status": "approved", "signed_by": signer},
    )
    messages.success(request, f"Approval request {approval.number} approved successfully.")
    return redirect("projects:cfb_detail", pk=pk)


@login_required
@require_POST
def cfb_reject(request, pk):
    approval = get_object_or_404(
        ClientApprovalRequest,
        pk=pk,
        tenant=request.tenant,
    )
    if approval.status == "rejected":
        messages.warning(request, f"Approval request {approval.number} is already rejected.")
        return redirect("projects:cfb_detail", pk=pk)

    reason = request.POST.get("rejection_reason", "").strip()
    approval.status = "rejected"
    approval.rejection_reason = reason
    approval.save()

    write_audit_log(
        request.user,
        action="reject",
        model_name="ClientApprovalRequest",
        object_id=approval.pk,
        changes={"status": "rejected", "reason": reason},
    )
    messages.success(request, f"Approval request {approval.number} marked as rejected.")
    return redirect("projects:cfb_detail", pk=pk)
