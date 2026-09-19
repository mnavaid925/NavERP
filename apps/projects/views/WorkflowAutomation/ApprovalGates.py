"""Projects 7.17 — ProjectApprovalGate views."""
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.views.decorators.http import require_POST

from apps.projects.forms.WorkflowAutomation.ApprovalGates import (
    ApprovalDecisionForm,
    ApprovalDelegateForm,
    ProjectApprovalGateForm,
)
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.WorkflowAutomation.ApprovalGates import ProjectApprovalGate
from apps.projects.views._common import *


@login_required
def par_list(request):
    """List approval gates with search and filters."""
    qs = ProjectApprovalGate.objects.filter(tenant=request.tenant).select_related(
        "project", "requested_by", "approver", "delegate_approver", "escalate_to"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(number__icontains=q) | Q(description__icontains=q) | Q(target_label__icontains=q))

    gate_type = request.GET.get("gate_type", "").strip()
    if gate_type:
        qs = qs.filter(gate_type=gate_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    project_id = request.GET.get("project", "").strip()
    if project_id and project_id.isdigit():
        qs = qs.filter(project_id=project_id)

    gate_counts = ProjectApprovalGate.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending")),
        approved=Count("id", filter=Q(status__in=["approved", "auto_approved"])),
        escalated=Count("id", filter=Q(status="escalated")),
    )
    total_count = gate_counts["total"] or 0
    pending_count = gate_counts["pending"] or 0
    approved_count = gate_counts["approved"] or 0
    escalated_count = gate_counts["escalated"] or 0

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/workflowautomation/approvalgate/list.html",
        {
            "gates": page_obj.object_list,
            "page_obj": page_obj,
            "gate_type_choices": ProjectApprovalGate.GATE_TYPE_CHOICES,
            "status_choices": ProjectApprovalGate.STATUS_CHOICES,
            "projects": Project.objects.filter(tenant=request.tenant),
            "stats": {
                "total": total_count,
                "pending": pending_count,
                "approved": approved_count,
                "escalated": escalated_count,
            },
            "q": q,
            "gate_type": gate_type,
            "status": status,
            "project_id": project_id,
        },
    )


@login_required
def par_detail(request, pk):
    """Detail view for a ProjectApprovalGate showing status, target, and decision forms."""
    gate = get_object_or_404(
        ProjectApprovalGate.objects.select_related("project", "requested_by", "approver", "delegate_approver", "escalate_to"),
        pk=pk,
        tenant=request.tenant,
    )

    return render(
        request,
        "projects/workflowautomation/approvalgate/detail.html",
        {
            "gate": gate,
            "decision_form": ApprovalDecisionForm(),
            "delegate_form": ApprovalDelegateForm(tenant=request.tenant),
        },
    )


@login_required
def par_create(request):
    """Create a new ProjectApprovalGate."""
    if request.method == "POST":
        form = ProjectApprovalGateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            gate = form.save(commit=False)
            gate.tenant = request.tenant
            gate.requested_by = request.user
            # Check auto-approval tolerance
            if (
                gate.threshold_amount
                and gate.auto_approve_threshold
                and gate.threshold_amount <= gate.auto_approve_threshold
            ):
                gate.status = "auto_approved"
                gate.decided_at = timezone.now()
                gate.decision_notes = f"Auto-approved: threshold {gate.threshold_amount} within tolerance {gate.auto_approve_threshold}."

            gate.save()
            write_audit_log(
                user=request.user,
                obj=gate,
                action="create",
                changes={"description": f"Created approval gate {gate.number}: {gate.title} ({gate.status})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Approval gate {gate.number} created successfully.")
            return redirect("projects:par_detail", pk=gate.pk)
    else:
        initial = {}
        if request.GET.get("project"):
            initial["project"] = request.GET.get("project")
        form = ProjectApprovalGateForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "projects/workflowautomation/approvalgate/form.html",
        {
            "form": form,
            "gate": None,
            "is_edit": False,
        },
    )


@login_required
def par_edit(request, pk):
    """Edit an existing ProjectApprovalGate."""
    gate = get_object_or_404(ProjectApprovalGate, pk=pk, tenant=request.tenant)

    if gate.is_terminal:
        messages.warning(request, f"Cannot edit gate {gate.number} as it has already reached terminal status '{gate.status}'.")
        return redirect("projects:par_detail", pk=gate.pk)

    if request.method == "POST":
        form = ProjectApprovalGateForm(request.POST, instance=gate, tenant=request.tenant)
        if form.is_valid():
            gate = form.save()
            write_audit_log(
                user=request.user,
                obj=gate,
                action="update",
                changes={"description": f"Updated approval gate {gate.number}: {gate.title}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Approval gate {gate.number} updated successfully.")
            return redirect("projects:par_detail", pk=gate.pk)
    else:
        form = ProjectApprovalGateForm(instance=gate, tenant=request.tenant)

    return render(
        request,
        "projects/workflowautomation/approvalgate/form.html",
        {
            "form": form,
            "gate": gate,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def par_delete(request, pk):
    """Delete an approval gate."""
    gate = get_object_or_404(ProjectApprovalGate, pk=pk, tenant=request.tenant)
    if gate.status not in ("pending", "cancelled"):
        messages.error(request, f"Cannot delete gate {gate.number} with decision status '{gate.status}'.")
        return redirect("projects:par_detail", pk=gate.pk)
    number = gate.number
    title = gate.title
    gate.delete()
    write_audit_log(
        user=request.user,
        obj=None,
        action="delete",
        changes={"description": f"Deleted approval gate {number}: {title}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Approval gate {number} deleted successfully.")
    return redirect("projects:par_list")


@login_required
@require_POST
def par_approve(request, pk):
    """Approve a pending approval gate."""
    gate = get_object_or_404(ProjectApprovalGate, pk=pk, tenant=request.tenant)
    if gate.is_terminal:
        messages.error(request, f"Gate {gate.number} is already in state '{gate.status}'.")
        return redirect("projects:par_detail", pk=gate.pk)

    is_admin = getattr(request.user, "is_tenant_admin", False) or request.user.is_superuser
    if not (request.user in (gate.approver, gate.delegate_approver) or is_admin):
        messages.error(request, "You are not authorized to approve this gate.")
        return redirect("projects:par_detail", pk=gate.pk)

    if gate.requested_by == request.user and not is_admin:
        messages.error(request, "Requesters cannot approve their own approval gates.")
        return redirect("projects:par_detail", pk=gate.pk)

    notes = request.POST.get("decision_notes", "").strip()
    gate.status = "approved"
    gate.decided_at = timezone.now()
    if notes:
        gate.decision_notes = notes
    gate.save(update_fields=["status", "decided_at", "decision_notes", "updated_at"])

    write_audit_log(
        user=request.user,
        obj=gate,
        action="approve",
        changes={"description": f"Approved gate {gate.number}: {notes or 'No notes'}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Approval gate {gate.number} has been approved.")
    return redirect("projects:par_detail", pk=gate.pk)


@login_required
@require_POST
def par_reject(request, pk):
    """Reject a pending approval gate."""
    gate = get_object_or_404(ProjectApprovalGate, pk=pk, tenant=request.tenant)
    if gate.is_terminal:
        messages.error(request, f"Gate {gate.number} is already in state '{gate.status}'.")
        return redirect("projects:par_detail", pk=gate.pk)

    is_admin = getattr(request.user, "is_tenant_admin", False) or request.user.is_superuser
    if not (request.user in (gate.approver, gate.delegate_approver) or is_admin):
        messages.error(request, "You are not authorized to reject this gate.")
        return redirect("projects:par_detail", pk=gate.pk)

    notes = request.POST.get("decision_notes", "").strip()
    gate.status = "rejected"
    gate.decided_at = timezone.now()
    gate.decision_notes = notes
    gate.save(update_fields=["status", "decided_at", "decision_notes", "updated_at"])

    write_audit_log(
        user=request.user,
        obj=gate,
        action="reject",
        changes={"description": f"Rejected gate {gate.number}: {notes or 'No notes'}"},
        tenant=request.tenant,
    )
    messages.warning(request, f"Approval gate {gate.number} has been rejected.")
    return redirect("projects:par_detail", pk=gate.pk)


@login_required
@require_POST
def par_escalate(request, pk):
    """Escalate a pending approval gate past SLA timeout."""
    gate = get_object_or_404(ProjectApprovalGate, pk=pk, tenant=request.tenant)
    if gate.is_terminal:
        messages.error(request, f"Cannot escalate gate in state '{gate.status}'.")
        return redirect("projects:par_detail", pk=gate.pk)

    is_admin = getattr(request.user, "is_tenant_admin", False) or request.user.is_superuser
    if not (request.user in (gate.approver, gate.delegate_approver) or is_admin):
        messages.error(request, "You are not authorized to escalate this gate.")
        return redirect("projects:par_detail", pk=gate.pk)

    gate.status = "escalated"
    gate.escalated_at = timezone.now()
    gate.save(update_fields=["status", "escalated_at", "updated_at"])

    write_audit_log(
        user=request.user,
        obj=gate,
        action="escalate",
        changes={"description": f"Escalated approval gate {gate.number} to {gate.escalate_to}"},
        tenant=request.tenant,
    )
    messages.warning(request, f"Approval gate {gate.number} escalated.")
    return redirect("projects:par_detail", pk=gate.pk)


@login_required
@require_POST
def par_delegate(request, pk):
    """Delegate approval authority to another user."""
    gate = get_object_or_404(ProjectApprovalGate, pk=pk, tenant=request.tenant)
    if gate.is_terminal:
        messages.error(request, f"Cannot delegate gate in state '{gate.status}'.")
        return redirect("projects:par_detail", pk=gate.pk)

    is_admin = getattr(request.user, "is_tenant_admin", False) or request.user.is_superuser
    if not (request.user in (gate.approver, gate.delegate_approver) or is_admin):
        messages.error(request, "You are not authorized to delegate this gate.")
        return redirect("projects:par_detail", pk=gate.pk)

    form = ApprovalDelegateForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        delegate = form.cleaned_data["delegate_approver"]
        if delegate.tenant != request.tenant:
            messages.error(request, "Selected delegate does not belong to this tenant.")
            return redirect("projects:par_detail", pk=gate.pk)
        gate.delegate_approver = delegate
        gate.save(update_fields=["delegate_approver", "updated_at"])

        write_audit_log(
            user=request.user,
            obj=gate,
            action="delegate",
            changes={"description": f"Delegated approval gate {gate.number} to {delegate}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Approval gate {gate.number} delegated to {delegate.get_full_name() or delegate.username}.")
    else:
        messages.error(request, "Please select a valid user to delegate to.")

    return redirect("projects:par_detail", pk=gate.pk)


@login_required
@require_POST
def par_cancel(request, pk):
    """Cancel an approval gate."""
    gate = get_object_or_404(ProjectApprovalGate, pk=pk, tenant=request.tenant)
    gate.status = "cancelled"
    gate.save(update_fields=["status", "updated_at"])

    write_audit_log(
        user=request.user,
        obj=gate,
        action="cancel",
        changes={"description": f"Cancelled approval gate {gate.number}"},
        tenant=request.tenant,
    )
    messages.info(request, f"Approval gate {gate.number} has been cancelled.")
    return redirect("projects:par_detail", pk=gate.pk)
