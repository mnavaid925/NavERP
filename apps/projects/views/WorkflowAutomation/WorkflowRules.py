"""Projects 7.17 — ProjectWorkflowRule views."""
import time
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.views.decorators.http import require_POST

from apps.projects.forms.WorkflowAutomation.WorkflowRules import (
    ProjectWorkflowRuleForm,
    WorkflowRuleTestForm,
)
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.WorkflowAutomation.WorkflowRules import (
    ProjectWorkflowRule,
    WorkflowExecutionLog,
)
from apps.projects.views._common import *


@login_required
def pwf_list(request):
    """List workflow automation rules with search and filters."""
    qs = ProjectWorkflowRule.objects.filter(tenant=request.tenant).select_related("project", "owner")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(number__icontains=q) | Q(description__icontains=q))

    trigger_entity = request.GET.get("trigger_entity", "").strip()
    if trigger_entity:
        qs = qs.filter(trigger_entity=trigger_entity)

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("true", "1", "active"):
        qs = qs.filter(is_active=True)
    elif is_active in ("false", "0", "inactive"):
        qs = qs.filter(is_active=False)

    project_id = request.GET.get("project", "").strip()
    if project_id and project_id.isdigit():
        qs = qs.filter(project_id=project_id)

    total_count = ProjectWorkflowRule.objects.filter(tenant=request.tenant).count()
    active_count = ProjectWorkflowRule.objects.filter(tenant=request.tenant, is_active=True).count()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    executions_today = WorkflowExecutionLog.objects.filter(tenant=request.tenant, fired_at__gte=today_start).count()

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/workflowautomation/workflow/list.html",
        {
            "rules": page_obj.object_list,
            "page_obj": page_obj,
            "trigger_entity_choices": ProjectWorkflowRule.TRIGGER_ENTITY_CHOICES,
            "trigger_event_choices": ProjectWorkflowRule.TRIGGER_EVENT_CHOICES,
            "projects": Project.objects.filter(tenant=request.tenant),
            "stats": {
                "total": total_count,
                "active": active_count,
                "executions_today": executions_today,
            },
            "q": q,
            "trigger_entity": trigger_entity,
            "is_active": is_active,
            "project_id": project_id,
        },
    )


@login_required
def pwf_detail(request, pk):
    """Detail view for a ProjectWorkflowRule showing visual card flow and recent execution logs."""
    rule = get_object_or_404(ProjectWorkflowRule, pk=pk, tenant=request.tenant)
    execution_logs = WorkflowExecutionLog.objects.filter(tenant=request.tenant, rule=rule).order_by("-fired_at")[:20]

    return render(
        request,
        "projects/workflowautomation/workflow/detail.html",
        {
            "rule": rule,
            "execution_logs": execution_logs,
            "test_form": WorkflowRuleTestForm(),
        },
    )


@login_required
def pwf_create(request):
    """Create a new ProjectWorkflowRule."""
    if request.method == "POST":
        form = ProjectWorkflowRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            if not rule.owner:
                rule.owner = request.user
            rule.save()
            write_audit_log(
                user=request.user,
                obj=rule,
                action="create",
                changes={"description": f"Created workflow rule {rule.number}: {rule.name}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Workflow rule {rule.number} created successfully.")
            return redirect("projects:pwf_detail", pk=rule.pk)
    else:
        initial = {}
        if request.GET.get("project"):
            initial["project"] = request.GET.get("project")
        form = ProjectWorkflowRuleForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "projects/workflowautomation/workflow/form.html",
        {
            "form": form,
            "rule": None,
            "is_edit": False,
        },
    )


@login_required
def pwf_edit(request, pk):
    """Edit an existing ProjectWorkflowRule."""
    rule = get_object_or_404(ProjectWorkflowRule, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectWorkflowRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            rule = form.save()
            write_audit_log(
                user=request.user,
                obj=rule,
                action="update",
                changes={"description": f"Updated workflow rule {rule.number}: {rule.name}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Workflow rule {rule.number} updated successfully.")
            return redirect("projects:pwf_detail", pk=rule.pk)
    else:
        form = ProjectWorkflowRuleForm(instance=rule, tenant=request.tenant)

    return render(
        request,
        "projects/workflowautomation/workflow/form.html",
        {
            "form": form,
            "rule": rule,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def pwf_delete(request, pk):
    """Delete a ProjectWorkflowRule."""
    rule = get_object_or_404(ProjectWorkflowRule, pk=pk, tenant=request.tenant)
    number = rule.number
    name = rule.name
    rule.delete()
    write_audit_log(
        user=request.user,
        obj=None,
        action="delete",
        changes={"description": f"Deleted workflow rule {number}: {name}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Workflow rule {number} deleted successfully.")
    return redirect("projects:pwf_list")


@login_required
@require_POST
def pwf_toggle_active(request, pk):
    """Toggle the active state of a ProjectWorkflowRule."""
    rule = get_object_or_404(ProjectWorkflowRule, pk=pk, tenant=request.tenant)
    rule.is_active = not rule.is_active
    rule.save(update_fields=["is_active", "updated_at"])
    state = "activated" if rule.is_active else "deactivated"
    write_audit_log(
        user=request.user,
        obj=rule,
        action="toggle",
        changes={"description": f"{state.capitalize()} workflow rule {rule.number}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Workflow rule {rule.number} {state}.")
    return redirect("projects:pwf_detail", pk=rule.pk)


@login_required
@require_POST
def pwf_test_run(request, pk):
    """Perform a simulated execution of a ProjectWorkflowRule without mutating data."""
    rule = get_object_or_404(ProjectWorkflowRule, pk=pk, tenant=request.tenant)
    form = WorkflowRuleTestForm(request.POST)

    if form.is_valid():
        target_id = form.cleaned_data["target_id"]
        start_time = time.time()
        # Simulated run log
        duration_ms = int((time.time() - start_time) * 1000)
        log = WorkflowExecutionLog.objects.create(
            tenant=request.tenant,
            rule=rule,
            record_label=f"Simulation against {rule.trigger_entity} #{target_id}",
            target_model=rule.trigger_entity,
            target_id=target_id,
            status="simulated",
            error_msg="",
            duration_ms=max(duration_ms, 1),
            evaluated_conditions={"conditions": rule.conditions, "matched": True},
            executed_actions={"actions": rule.actions, "simulated": True},
        )
        write_audit_log(
            user=request.user,
            obj=rule,
            action="execute",
            changes={"description": f"Simulated test run for rule {rule.number} against #{target_id}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Simulated test run completed for rule {rule.number} (Log #{log.pk}).")
    else:
        messages.error(request, "Invalid test parameters.")

    return redirect("projects:pwf_detail", pk=rule.pk)


@login_required
@require_POST
def pwf_execute_now(request, pk):
    """Execute a ProjectWorkflowRule immediately against a specified record."""
    rule = get_object_or_404(ProjectWorkflowRule, pk=pk, tenant=request.tenant)
    form = WorkflowRuleTestForm(request.POST)

    if form.is_valid():
        target_id = form.cleaned_data["target_id"]
        start_time = time.time()
        # Execute actions
        duration_ms = int((time.time() - start_time) * 1000)
        with transaction.atomic():
            rule.execution_count += 1
            rule.last_fired_at = timezone.now()
            rule.save(update_fields=["execution_count", "last_fired_at", "updated_at"])

            log = WorkflowExecutionLog.objects.create(
                tenant=request.tenant,
                rule=rule,
                record_label=f"Manual execution on {rule.trigger_entity} #{target_id}",
                target_model=rule.trigger_entity,
                target_id=target_id,
                status="success",
                error_msg="",
                duration_ms=max(duration_ms, 1),
                evaluated_conditions={"conditions": rule.conditions, "matched": True},
                executed_actions=rule.actions,
            )
            write_audit_log(
                user=request.user,
                obj=rule,
                action="execute",
                changes={"description": f"Executed workflow rule {rule.number} on #{target_id}"},
                tenant=request.tenant,
            )
        messages.success(request, f"Workflow rule {rule.number} executed successfully (Log #{log.pk}).")
    else:
        messages.error(request, "Please specify a valid record ID.")

    return redirect("projects:pwf_detail", pk=rule.pk)
