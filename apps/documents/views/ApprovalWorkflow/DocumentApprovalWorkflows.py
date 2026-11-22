from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.ApprovalWorkflow.DocumentApprovalWorkflows import (
    DocumentApprovalWorkflowForm,
    WorkflowBypassForm,
)
from apps.documents.models import DocumentApprovalWorkflow
from apps.documents.views._common import documents_object, documents_scope


@login_required
def workflow_list(request):
    qs = documents_scope(
        DocumentApprovalWorkflow.objects.select_related("document", "version", "initiator", "department"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(document__title__icontains=q)
            | Q(initiator__username__icontains=q)
        )

    w_type = request.GET.get("workflow_type", "").strip()
    if w_type:
        qs = qs.filter(workflow_type=w_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    urgency = request.GET.get("urgency", "").strip()
    if urgency:
        qs = qs.filter(urgency=urgency)

    total_count = qs.count()
    pending_count = qs.filter(status="pending").count()
    approved_count = qs.filter(status="approved").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    workflows = paginator.get_page(page_number)

    context = {
        "workflows": workflows,
        "workflow_type_choices": DocumentApprovalWorkflow.WORKFLOW_TYPE_CHOICES,
        "status_choices": DocumentApprovalWorkflow.STATUS_CHOICES,
        "urgency_choices": DocumentApprovalWorkflow.URGENCY_CHOICES,
        "status_css": DocumentApprovalWorkflow.STATUS_CSS,
        "urgency_css": DocumentApprovalWorkflow.URGENCY_CSS,
        "workflow_type_css": DocumentApprovalWorkflow.WORKFLOW_TYPE_CSS,
        "total_count": total_count,
        "pending_count": pending_count,
        "approved_count": approved_count,
    }
    return render(request, "documents/approval_workflow/document_approval_workflow/list.html", context)


@login_required
def workflow_detail(request, pk):
    workflow = documents_object(
        request,
        DocumentApprovalWorkflow,
        pk,
        select_related=("document", "version", "initiator", "department", "bypassed_by"),
        prefetch_related=("approval_requests__approver", "signatures__signer", "review_comments__author"),
    )

    approval_requests = workflow.approval_requests.all().order_by("stage_number", "order", "-created_at")
    signatures = workflow.signatures.all().order_by("-signed_at") if hasattr(workflow, "signatures") else workflow.document.signatures.filter(version=workflow.version).order_by("-signed_at")
    review_comments = workflow.review_comments.all().order_by("page_number", "-created_at")
    blocking_comments_count = review_comments.filter(is_blocking=True, status="open").count()

    context = {
        "workflow": workflow,
        "status_css": workflow.status_css_class,
        "urgency_css": workflow.urgency_css_class,
        "workflow_type_css": workflow.workflow_type_css_class,
        "approval_requests": approval_requests,
        "signatures": signatures,
        "review_comments": review_comments,
        "blocking_comments_count": blocking_comments_count,
        "bypass_form": WorkflowBypassForm(),
    }
    return render(request, "documents/approval_workflow/document_approval_workflow/detail.html", context)


@login_required
def workflow_create(request):
    if request.method == "POST":
        form = DocumentApprovalWorkflowForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            workflow = form.save(commit=False)
            workflow.tenant = request.tenant
            workflow.initiator = request.user
            workflow.status = "draft"
            workflow.save()
            write_audit_log(request.user, workflow, "create", tenant=request.tenant)
            messages.success(request, f"Approval workflow {workflow.number} created successfully.")
            return redirect("documents:workflow_detail", pk=workflow.pk)
    else:
        initial = {}
        doc_id = request.GET.get("document")
        if doc_id and doc_id.isdigit():
            initial["document"] = doc_id
        form = DocumentApprovalWorkflowForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "workflow": None,
        "is_edit": False,
    }
    return render(request, "documents/approval_workflow/document_approval_workflow/form.html", context)


@login_required
def workflow_edit(request, pk):
    workflow = documents_object(request, DocumentApprovalWorkflow, pk)
    if workflow.status in ("approved", "cancelled", "bypassed"):
        messages.warning(request, "Completed or cancelled workflows cannot be edited.")
        return redirect("documents:workflow_detail", pk=workflow.pk)

    if request.method == "POST":
        form = DocumentApprovalWorkflowForm(request.POST, instance=workflow, tenant=request.tenant)
        if form.is_valid():
            workflow = form.save()
            write_audit_log(request.user, workflow, "update", tenant=request.tenant)
            messages.success(request, f"Workflow {workflow.number} updated.")
            return redirect("documents:workflow_detail", pk=workflow.pk)
    else:
        form = DocumentApprovalWorkflowForm(instance=workflow, tenant=request.tenant)

    context = {
        "form": form,
        "workflow": workflow,
        "is_edit": True,
    }
    return render(request, "documents/approval_workflow/document_approval_workflow/form.html", context)


@login_required
@require_POST
def workflow_delete(request, pk):
    workflow = documents_object(request, DocumentApprovalWorkflow, pk)
    number = workflow.number
    write_audit_log(request.user, workflow, "delete", tenant=request.tenant)
    workflow.delete()
    messages.success(request, f"Workflow {number} deleted.")
    return redirect("documents:workflow_list")


@login_required
def workflow_designer(request, pk):
    workflow = documents_object(request, DocumentApprovalWorkflow, pk)
    if request.method == "POST":
        definition_json = request.POST.get("definition_json", "{}")
        workflow.definition_json = definition_json
        workflow.save(update_fields=["definition_json", "updated_at"])
        write_audit_log(request.user, workflow, "update", tenant=request.tenant)
        messages.success(request, "Workflow designer layout saved.")
        return redirect("documents:workflow_designer", pk=workflow.pk)

    requests = workflow.approval_requests.all().select_related("approver", "approver_role").order_by("stage_number", "order")
    stages = {}
    for req in requests:
        stages.setdefault(req.stage_number, []).append(req)

    context = {
        "workflow": workflow,
        "stages": stages,
        "definition_json": workflow.definition_json or "{}",
    }
    return render(request, "documents/approval_workflow/document_approval_workflow/designer.html", context)


@login_required
@require_POST
def workflow_submit(request, pk):
    workflow = documents_object(request, DocumentApprovalWorkflow, pk)
    if workflow.status != "draft":
        messages.warning(request, "Only draft workflows can be submitted.")
        return redirect("documents:workflow_detail", pk=workflow.pk)

    if not workflow.approval_requests.exists():
        messages.error(request, "Cannot submit a workflow without at least one approval request stage.")
        return redirect("documents:workflow_detail", pk=workflow.pk)

    workflow.status = "pending"
    workflow.current_stage = 1
    workflow.save(update_fields=["status", "current_stage", "updated_at"])
    write_audit_log(request.user, workflow, "submit", tenant=request.tenant)
    messages.success(request, f"Workflow {workflow.number} submitted and initiated.")
    return redirect("documents:workflow_detail", pk=workflow.pk)


@login_required
@require_POST
def workflow_bypass(request, pk):
    workflow = documents_object(request, DocumentApprovalWorkflow, pk)
    if not workflow.allow_emergency_bypass and not request.user.is_superuser:
        messages.error(request, "Emergency bypass is not permitted on this workflow.")
        return redirect("documents:workflow_detail", pk=workflow.pk)

    reason = request.POST.get("bypass_reason", "").strip()
    if not reason:
        messages.error(request, "A documented justification is required for emergency bypass.")
        return redirect("documents:workflow_detail", pk=workflow.pk)

    workflow.status = "bypassed"
    workflow.bypass_reason = reason
    workflow.bypassed_by = request.user
    workflow.completed_at = timezone.now()
    workflow.save(update_fields=["status", "bypass_reason", "bypassed_by", "completed_at", "updated_at"])
    write_audit_log(request.user, workflow, "bypass", tenant=request.tenant)
    messages.warning(request, f"Workflow {workflow.number} was emergency bypassed.")
    return redirect("documents:workflow_detail", pk=workflow.pk)


@login_required
@require_POST
def workflow_cancel(request, pk):
    workflow = documents_object(request, DocumentApprovalWorkflow, pk)
    if workflow.status in ("approved", "bypassed"):
        messages.warning(request, "Completed workflows cannot be cancelled.")
        return redirect("documents:workflow_detail", pk=workflow.pk)

    workflow.status = "cancelled"
    workflow.completed_at = timezone.now()
    workflow.save(update_fields=["status", "completed_at", "updated_at"])
    write_audit_log(request.user, workflow, "cancel", tenant=request.tenant)
    messages.info(request, f"Workflow {workflow.number} cancelled.")
    return redirect("documents:workflow_detail", pk=workflow.pk)
