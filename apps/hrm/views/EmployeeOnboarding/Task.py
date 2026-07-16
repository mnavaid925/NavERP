"""HRM 3.3 Employee Onboarding — Task views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    OnboardingProgram,
    OnboardingTask,
    PHASE_CHOICES,
    TASK_CATEGORY_CHOICES,
)
from apps.hrm.forms import (
    OnboardingTaskForm,
)


# ============================================================ Onboarding Tasks (3.3)
@login_required
def onboardingtask_list(request):
    return crud_list(
        request,
        OnboardingTask.objects.filter(tenant=request.tenant)
        .select_related("program", "assignee"),  # rows show program.number + assignee.username only
        "hrm/onboarding/task/list.html",
        search_fields=["title", "description", "assignee__username", "program__number"],
        filters=[("program", "program_id", True), ("status", "status", False),
                 ("phase", "phase", False), ("task_category", "task_category", False)],
        extra_context={"status_choices": OnboardingTask.STATUS_CHOICES,
                       "phase_choices": PHASE_CHOICES,
                       "category_choices": TASK_CATEGORY_CHOICES,
                       "programs": OnboardingProgram.objects.filter(tenant=request.tenant)
                       .select_related("employee__party").order_by("-start_date")},
        per_page=30,
    )


@login_required
def onboardingtask_create(request):
    return crud_create(request, form_class=OnboardingTaskForm,
                       template="hrm/onboarding/task/form.html",
                       success_url="hrm:onboardingtask_list")


@login_required
def onboardingtask_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTask.objects.select_related("program__employee__party", "assignee", "completed_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/task/detail.html", {"obj": obj})


@login_required
def onboardingtask_edit(request, pk):
    obj = get_object_or_404(OnboardingTask, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "Reopen this task before editing it.")
        return redirect("hrm:onboardingtask_detail", pk=obj.pk)
    return crud_edit(request, model=OnboardingTask, pk=pk, form_class=OnboardingTaskForm,
                     template="hrm/onboarding/task/form.html", success_url="hrm:onboardingtask_list")


@login_required
@require_POST
def onboardingtask_delete(request, pk):
    return crud_delete(request, model=OnboardingTask, pk=pk, success_url="hrm:onboardingtask_list")


@login_required
@require_POST
def onboardingtask_complete(request, pk):
    obj = get_object_or_404(OnboardingTask.objects.select_related("program"), pk=pk, tenant=request.tenant)
    if obj.status != "completed":
        obj.status = "completed"
        obj.completed_at = timezone.now()
        obj.completed_by = request.user
        obj.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"Task '{obj.title}' marked complete.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.program_id)


@login_required
@require_POST
def onboardingtask_reopen(request, pk):
    obj = get_object_or_404(OnboardingTask.objects.select_related("program"), pk=pk, tenant=request.tenant)
    if obj.status in ("completed", "skipped"):
        obj.status = "pending"
        obj.completed_at = None
        obj.completed_by = None
        obj.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reopen"})
        messages.success(request, f"Task '{obj.title}' reopened.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.program_id)


@login_required
@require_POST
def onboardingtask_skip(request, pk):
    obj = get_object_or_404(OnboardingTask.objects.select_related("program"), pk=pk, tenant=request.tenant)
    if obj.status in ("pending", "in_progress"):
        obj.status = "skipped"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "skip"})
        messages.success(request, f"Task '{obj.title}' skipped.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.program_id)
