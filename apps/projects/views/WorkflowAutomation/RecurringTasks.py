"""Projects 7.17 — RecurringTaskSchedule views."""
from datetime import timedelta
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_POST

from apps.projects.forms.WorkflowAutomation.RecurringTasks import RecurringTaskScheduleForm
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ProjectPlanningScheduling.ProjectTasks import ProjectTask
from apps.projects.models.WorkflowAutomation.RecurringTasks import RecurringTaskSchedule
from apps.projects.views._common import *


@login_required
def rts_list(request):
    """List recurring task schedules with search and filters."""
    qs = RecurringTaskSchedule.objects.filter(tenant=request.tenant).select_related("project", "default_assignee")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title_template__icontains=q) | Q(number__icontains=q) | Q(description_template__icontains=q))

    frequency = request.GET.get("frequency", "").strip()
    if frequency:
        qs = qs.filter(frequency=frequency)

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("true", "1", "active"):
        qs = qs.filter(is_active=True)
    elif is_active in ("false", "0", "inactive"):
        qs = qs.filter(is_active=False)

    project_id = request.GET.get("project", "").strip()
    if project_id and project_id.isdigit():
        qs = qs.filter(project_id=project_id)

    total_count = RecurringTaskSchedule.objects.filter(tenant=request.tenant).count()
    active_count = RecurringTaskSchedule.objects.filter(tenant=request.tenant, is_active=True).count()
    today = timezone.localdate()
    due_this_week = RecurringTaskSchedule.objects.filter(
        tenant=request.tenant,
        is_active=True,
        next_run_date__gte=today,
        next_run_date__lte=today + timedelta(days=7),
    ).count()

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/workflowautomation/recurringtask/list.html",
        {
            "schedules": page_obj.object_list,
            "page_obj": page_obj,
            "frequency_choices": RecurringTaskSchedule.FREQUENCY_CHOICES,
            "priority_choices": RecurringTaskSchedule.PRIORITY_CHOICES,
            "projects": Project.objects.filter(tenant=request.tenant),
            "stats": {
                "total": total_count,
                "active": active_count,
                "due_this_week": due_this_week,
            },
            "q": q,
            "frequency": frequency,
            "is_active": is_active,
            "project_id": project_id,
        },
    )


@login_required
def rts_detail(request, pk):
    """Detail view for a RecurringTaskSchedule with recent generated tasks."""
    schedule = get_object_or_404(
        RecurringTaskSchedule.objects.select_related("project", "default_assignee"),
        pk=pk,
        tenant=request.tenant,
    )
    recent_tasks = ProjectTask.objects.filter(
        tenant=request.tenant,
        project=schedule.project,
        description__icontains=schedule.number,
    ).select_related("assignee").order_by("-created_at")[:10]

    return render(
        request,
        "projects/workflowautomation/recurringtask/detail.html",
        {
            "schedule": schedule,
            "recent_tasks": recent_tasks,
        },
    )


@login_required
def rts_create(request):
    """Create a new RecurringTaskSchedule."""
    if request.method == "POST":
        form = RecurringTaskScheduleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.tenant = request.tenant
            if not schedule.next_run_date:
                schedule.next_run_date = schedule.start_date
            schedule.save()
            write_audit_log(
                user=request.user,
                obj=schedule,
                action="create",
                changes={"description": f"Created recurring schedule {schedule.number}: {schedule.title_template}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Recurring schedule {schedule.number} created successfully.")
            return redirect("projects:rts_detail", pk=schedule.pk)
    else:
        initial = {
            "start_date": timezone.localdate(),
            "next_run_date": timezone.localdate(),
        }
        if request.GET.get("project"):
            initial["project"] = request.GET.get("project")
        form = RecurringTaskScheduleForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "projects/workflowautomation/recurringtask/form.html",
        {
            "form": form,
            "schedule": None,
            "is_edit": False,
        },
    )


@login_required
def rts_edit(request, pk):
    """Edit an existing RecurringTaskSchedule."""
    schedule = get_object_or_404(RecurringTaskSchedule, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = RecurringTaskScheduleForm(request.POST, instance=schedule, tenant=request.tenant)
        if form.is_valid():
            schedule = form.save()
            write_audit_log(
                user=request.user,
                obj=schedule,
                action="update",
                changes={"description": f"Updated recurring schedule {schedule.number}: {schedule.title_template}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Recurring schedule {schedule.number} updated successfully.")
            return redirect("projects:rts_detail", pk=schedule.pk)
    else:
        form = RecurringTaskScheduleForm(instance=schedule, tenant=request.tenant)

    return render(
        request,
        "projects/workflowautomation/recurringtask/form.html",
        {
            "form": form,
            "schedule": schedule,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def rts_delete(request, pk):
    """Delete a RecurringTaskSchedule."""
    schedule = get_object_or_404(RecurringTaskSchedule, pk=pk, tenant=request.tenant)
    number = schedule.number
    title = schedule.title_template
    schedule.delete()
    write_audit_log(
        user=request.user,
        obj=None,
        action="delete",
        changes={"description": f"Deleted recurring schedule {number}: {title}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Recurring schedule {number} deleted successfully.")
    return redirect("projects:rts_list")


@login_required
@require_POST
def rts_toggle_active(request, pk):
    """Toggle active state of a RecurringTaskSchedule."""
    schedule = get_object_or_404(RecurringTaskSchedule, pk=pk, tenant=request.tenant)
    schedule.is_active = not schedule.is_active
    schedule.save(update_fields=["is_active", "updated_at"])
    state = "activated" if schedule.is_active else "deactivated"
    write_audit_log(
        user=request.user,
        obj=schedule,
        action="toggle",
        changes={"description": f"{state.capitalize()} recurring schedule {schedule.number}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Recurring schedule {schedule.number} {state}.")
    return redirect("projects:rts_detail", pk=schedule.pk)


@login_required
@require_POST
def rts_generate_task(request, pk):
    """Mint a task immediately from this recurring schedule."""
    schedule = get_object_or_404(RecurringTaskSchedule, pk=pk, tenant=request.tenant)
    task = schedule.generate_task(actor=request.user)

    write_audit_log(
        user=request.user,
        obj=schedule,
        action="generate",
        changes={"description": f"Generated task {task.name} from schedule {schedule.number}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Task '{task.name}' successfully generated (Next run: {schedule.next_run_date}).")
    return redirect("projects:rts_detail", pk=schedule.pk)


@login_required
@require_POST
def rts_skip_next(request, pk):
    """Skip the next scheduled execution and advance the run date."""
    schedule = get_object_or_404(RecurringTaskSchedule, pk=pk, tenant=request.tenant)
    old_date = schedule.next_run_date
    schedule.advance_next_run_date()
    schedule.save(update_fields=["next_run_date", "is_active", "updated_at"])

    write_audit_log(
        user=request.user,
        obj=schedule,
        action="skip",
        changes={"description": f"Skipped execution for {old_date} on schedule {schedule.number} (Next: {schedule.next_run_date})"},
        tenant=request.tenant,
    )
    messages.info(request, f"Skipped run for {old_date}. Next execution set to {schedule.next_run_date}.")
    return redirect("projects:rts_detail", pk=schedule.pk)
