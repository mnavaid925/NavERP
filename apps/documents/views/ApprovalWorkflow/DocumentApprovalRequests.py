from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.ApprovalWorkflow.DocumentApprovalRequests import (
    ApprovalDecisionForm,
    ApprovalDelegationForm,
    ApprovalEscalationForm,
    DocumentApprovalRequestForm,
)
from apps.documents.models import DocumentApprovalRequest, DocumentApprovalWorkflow
from apps.documents.views._common import documents_object, documents_scope


@login_required
def approval_request_list(request):
    qs = documents_scope(
        DocumentApprovalRequest.objects.select_related(
            "workflow", "workflow__document", "approver", "approver_role", "delegated_to", "escalated_to"
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(workflow__title__icontains=q)
            | Q(approver__username__icontains=q)
            | Q(stage_name__icontains=q)
        )

    wf_id = request.GET.get("workflow", "").strip()
    if wf_id and wf_id.isdigit():
        qs = qs.filter(workflow_id=int(wf_id))

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    stage_type = request.GET.get("stage_type", "").strip()
    if stage_type:
        qs = qs.filter(stage_type=stage_type)

    if request.GET.get("mine") == "1":
        qs = qs.filter(Q(approver=request.user) | Q(delegated_to=request.user))

    total_count = qs.count()
    my_pending_count = DocumentApprovalRequest.objects.filter(
        tenant=request.tenant,
        status="pending",
    ).filter(Q(approver=request.user) | Q(delegated_to=request.user)).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    requests = paginator.get_page(page_number)

    context = {
        "requests": requests,
        "status_choices": DocumentApprovalRequest.STATUS_CHOICES,
        "stage_type_choices": DocumentApprovalRequest.STAGE_TYPE_CHOICES,
        "status_css": DocumentApprovalRequest.STATUS_CSS,
        "stage_type_css": DocumentApprovalRequest.STAGE_TYPE_CSS,
        "total_count": total_count,
        "my_pending_count": my_pending_count,
    }
    return render(request, "documents/approval_workflow/document_approval_request/list.html", context)


@login_required
def approval_request_detail(request, pk):
    request_obj = documents_object(
        request,
        DocumentApprovalRequest,
        pk,
        select_related=("workflow", "workflow__document", "workflow__version", "approver", "approver_role", "delegated_to", "escalated_to"),
    )

    signature = request_obj.signatures.first() if hasattr(request_obj, "signatures") else None

    context = {
        "request_obj": request_obj,
        "status_css": request_obj.status_css_class,
        "stage_type_css": request_obj.stage_type_css_class,
        "signature": signature,
        "decision_form": ApprovalDecisionForm(),
        "delegation_form": ApprovalDelegationForm(tenant=request.tenant),
        "escalation_form": ApprovalEscalationForm(tenant=request.tenant),
    }
    return render(request, "documents/approval_workflow/document_approval_request/detail.html", context)


@login_required
def approval_request_create(request):
    if request.method == "POST":
        form = DocumentApprovalRequestForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            req_obj = form.save(commit=False)
            req_obj.tenant = request.tenant
            req_obj.status = "pending"
            req_obj.save()

            # Update workflow total_stages if stage_number exceeds current total
            wf = req_obj.workflow
            if req_obj.stage_number > wf.total_stages:
                wf.total_stages = req_obj.stage_number
                wf.save(update_fields=["total_stages", "updated_at"])

            write_audit_log(request.user, req_obj, "create", tenant=request.tenant)
            messages.success(request, f"Approval request {req_obj.number} created.")
            return redirect("documents:workflow_detail", pk=req_obj.workflow.pk)
    else:
        initial = {}
        wf_id = request.GET.get("workflow")
        if wf_id and wf_id.isdigit():
            initial["workflow"] = wf_id
        stage_num = request.GET.get("stage_number")
        if stage_num and stage_num.isdigit():
            initial["stage_number"] = stage_num
        form = DocumentApprovalRequestForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "request_obj": None,
        "is_edit": False,
    }
    return render(request, "documents/approval_workflow/document_approval_request/form.html", context)


@login_required
def approval_request_edit(request, pk):
    req_obj = documents_object(request, DocumentApprovalRequest, pk)
    if req_obj.status in ("approved", "rejected", "bypassed"):
        messages.warning(request, "Decided approval requests cannot be modified.")
        return redirect("documents:approval_request_detail", pk=req_obj.pk)

    if request.method == "POST":
        form = DocumentApprovalRequestForm(request.POST, instance=req_obj, tenant=request.tenant)
        if form.is_valid():
            req_obj = form.save()
            write_audit_log(request.user, req_obj, "update", tenant=request.tenant)
            messages.success(request, f"Approval request {req_obj.number} updated.")
            return redirect("documents:approval_request_detail", pk=req_obj.pk)
    else:
        form = DocumentApprovalRequestForm(instance=req_obj, tenant=request.tenant)

    context = {
        "form": form,
        "request_obj": req_obj,
        "is_edit": True,
    }
    return render(request, "documents/approval_workflow/document_approval_request/form.html", context)


@login_required
@require_POST
def approval_request_delete(request, pk):
    req_obj = documents_object(request, DocumentApprovalRequest, pk)
    # C5: Reject deletion if workflow is not draft or request is not pending
    if req_obj.workflow.status != "draft" or req_obj.status != "pending":
        messages.error(request, "Only pending requests in a draft workflow can be deleted.")
        return redirect("documents:approval_request_detail", pk=req_obj.pk)

    wf_pk = req_obj.workflow.pk
    number = req_obj.number
    write_audit_log(request.user, req_obj, "delete", tenant=request.tenant)
    req_obj.delete()
    messages.success(request, f"Approval request {number} removed.")
    return redirect("documents:workflow_detail", pk=wf_pk)


@login_required
@require_POST
def approval_request_decide(request, pk):
    req_obj = documents_object(request, DocumentApprovalRequest, pk)
    if req_obj.status not in ["pending", "delegated", "escalated"]:
        messages.warning(request, "This request has already been processed.")
        return redirect("documents:approval_request_detail", pk=req_obj.pk)

    # C2: Authorization check
    is_authorized = (
        request.user == req_obj.approver
        or (req_obj.delegated_to and request.user == req_obj.delegated_to)
        or (req_obj.escalated_to and request.user == req_obj.escalated_to)
        or request.user.is_superuser
        or getattr(request.user, "is_tenant_admin", False)
    )
    if not is_authorized:
        messages.error(request, "You are not authorized to decide this approval request.")
        return redirect("documents:approval_request_detail", pk=req_obj.pk)

    wf = req_obj.workflow
    # I2: Parent workflow status and stage sequence check
    if wf.status != "pending":
        messages.error(request, f"Workflow is currently '{wf.status}', not pending. Decisions can only be made on active workflows.")
        return redirect("documents:approval_request_detail", pk=req_obj.pk)

    if req_obj.stage_type == "sequential" and req_obj.stage_number != wf.current_stage:
        messages.error(request, f"This request is for Stage {req_obj.stage_number}, but the workflow is currently at Stage {wf.current_stage}.")
        return redirect("documents:approval_request_detail", pk=req_obj.pk)

    form = ApprovalDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please enter a valid decision and decision remarks.")
        return redirect("documents:approval_request_detail", pk=req_obj.pk)

    decision = form.cleaned_data["decision"]
    comments = form.cleaned_data["decision_comments"]

    # Check comment resolution gate
    if decision == "approved" and wf.requires_all_comments_resolved:
        blocking_comments = wf.review_comments.filter(is_blocking=True, status="open").count()
        if blocking_comments > 0:
            messages.error(
                request,
                f"Cannot approve: {blocking_comments} blocking review comment(s) remain open on this workflow.",
            )
            return redirect("documents:approval_request_detail", pk=req_obj.pk)

    # I3: Multi-model updates wrapped in transaction.atomic()
    with transaction.atomic():
        req_obj.status = decision
        req_obj.decision_comments = comments
        req_obj.decided_at = timezone.now()
        req_obj.save(update_fields=["status", "decision_comments", "decided_at", "updated_at"])

        audit_verb = "approve" if decision == "approved" else "reject"
        write_audit_log(request.user, req_obj, audit_verb, tenant=request.tenant)

        if decision == "rejected":
            wf.status = "rejected"
            wf.completed_at = timezone.now()
            wf.save(update_fields=["status", "completed_at", "updated_at"])
            write_audit_log(request.user, wf, "reject", tenant=request.tenant)
            messages.error(request, f"Approval request {req_obj.number} was rejected. Workflow marked rejected.")
        else:
            stage_requests = wf.approval_requests.filter(stage_number=wf.current_stage)
            stage_done = False
            if req_obj.stage_type == "parallel_first":
                stage_done = True
                # M5: mark remaining pending/delegated sibling requests in this stage bypassed
                stage_requests.exclude(pk=req_obj.pk).filter(
                    status__in=["pending", "delegated", "escalated"]
                ).update(status="bypassed", updated_at=timezone.now())
            elif not stage_requests.filter(status__in=["pending", "delegated", "escalated"]).exists():
                # I1: Ensure stage has approved requests
                if stage_requests.filter(status="approved").exists():
                    stage_done = True

            if stage_done:
                next_stage = wf.current_stage + 1
                if next_stage <= wf.total_stages and wf.approval_requests.filter(stage_number=next_stage).exists():
                    wf.current_stage = next_stage
                    wf.save(update_fields=["current_stage", "updated_at"])
                    messages.info(request, f"Stage {wf.current_stage - 1} completed. Advanced to Stage {next_stage}.")
                else:
                    wf.status = "approved"
                    wf.completed_at = timezone.now()
                    wf.save(update_fields=["status", "completed_at", "updated_at"])
                    write_audit_log(request.user, wf, "approve", tenant=request.tenant)
                    messages.success(request, f"Workflow {wf.number} is now fully approved!")

            messages.success(request, f"Approval request {req_obj.number} recorded as approved.")

    return redirect("documents:approval_request_detail", pk=req_obj.pk)


@login_required
@require_POST
def approval_request_delegate(request, pk):
    req_obj = documents_object(request, DocumentApprovalRequest, pk)
    # Authorization check
    is_authorized = (
        request.user == req_obj.approver
        or (req_obj.delegated_to and request.user == req_obj.delegated_to)
        or request.user.is_superuser
        or getattr(request.user, "is_tenant_admin", False)
    )
    if not is_authorized:
        messages.error(request, "You are not authorized to delegate this approval request.")
        return redirect("documents:approval_request_detail", pk=req_obj.pk)

    form = ApprovalDelegationForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        delegated_to = form.cleaned_data["delegated_to"]
        reason = form.cleaned_data["delegation_reason"]
        req_obj.delegated_to = delegated_to
        req_obj.delegation_reason = reason
        req_obj.delegated_at = timezone.now()
        req_obj.status = "delegated"
        req_obj.save(update_fields=["delegated_to", "delegation_reason", "delegated_at", "status", "updated_at"])
        write_audit_log(request.user, req_obj, "delegate", tenant=request.tenant)
        messages.info(request, f"Request {req_obj.number} delegated to {delegated_to.username}.")
    else:
        messages.error(request, "Invalid delegation details.")
    return redirect("documents:approval_request_detail", pk=req_obj.pk)


@login_required
@require_POST
def approval_request_escalate(request, pk):
    req_obj = documents_object(request, DocumentApprovalRequest, pk)
    # Authorization check
    is_authorized = (
        request.user == req_obj.approver
        or request.user == req_obj.workflow.initiator
        or request.user.is_superuser
        or getattr(request.user, "is_tenant_admin", False)
    )
    if not is_authorized:
        messages.error(request, "You are not authorized to escalate this approval request.")
        return redirect("documents:approval_request_detail", pk=req_obj.pk)

    form = ApprovalEscalationForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        escalated_to = form.cleaned_data["escalated_to"]
        reason = form.cleaned_data["escalation_reason"]
        req_obj.is_escalated = True
        req_obj.escalated_to = escalated_to
        req_obj.escalation_reason = reason
        req_obj.escalated_at = timezone.now()
        req_obj.status = "escalated"
        req_obj.save(update_fields=["is_escalated", "escalated_to", "escalation_reason", "escalated_at", "status", "updated_at"])
        write_audit_log(request.user, req_obj, "escalate", tenant=request.tenant)
        messages.warning(request, f"Request {req_obj.number} escalated to {escalated_to.username}.")
    else:
        messages.error(request, "Invalid escalation details.")
    return redirect("documents:approval_request_detail", pk=req_obj.pk)
