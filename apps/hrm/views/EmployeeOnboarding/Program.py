"""HRM 3.3 Employee Onboarding — Program views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    OnboardingProgram,
    PHASE_CHOICES,
)
from apps.hrm.forms import (
    OnboardingProgramForm,
)


# ============================================================ Onboarding Programs (3.3)
@login_required
def onboardingprogram_list(request):
    return crud_list(
        request,
        OnboardingProgram.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "buddy__party", "template")
        .annotate(tasks_total=Count("tasks", distinct=True),
                  tasks_done=Count("tasks", filter=Q(tasks__status__in=("completed", "skipped")),
                                   distinct=True))
        .order_by("-start_date"),  # explicit — aggregate annotation drops Meta ordering (pagination guard)
        "hrm/onboarding/program/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True)],
        extra_context={"status_choices": OnboardingProgram.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def onboardingprogram_create(request):
    return crud_create(request, form_class=OnboardingProgramForm,
                       template="hrm/onboarding/program/form.html",
                       success_url="hrm:onboardingprogram_list")


@login_required
def onboardingprogram_detail(request, pk):
    obj = get_object_or_404(
        OnboardingProgram.objects.select_related("employee__party", "buddy__party", "template"),
        pk=pk, tenant=request.tenant)
    tasks = list(obj.tasks.select_related("assignee").order_by("phase", "order", "due_date", "title"))
    # Group tasks by phase, preserving the canonical PHASE_CHOICES order.
    phase_labels = dict(PHASE_CHOICES)
    grouped = {}
    for t in tasks:
        grouped.setdefault(t.phase, []).append(t)
    tasks_by_phase = [{"phase": p, "label": phase_labels.get(p, p), "tasks": grouped[p]}
                      for p, _ in PHASE_CHOICES if p in grouped]
    # Progress from the already-fetched list (matches OnboardingProgram.progress) — avoids the two
    # extra COUNT queries the model property would run on a page that has the tasks in hand.
    done = sum(1 for t in tasks if t.status in ("completed", "skipped"))
    progress = int(round(done / len(tasks) * 100)) if tasks else 0
    return render(request, "hrm/onboarding/program/detail.html", {
        "obj": obj,
        "progress": progress,
        "tasks_by_phase": tasks_by_phase,
        "task_count": len(tasks),
        "documents": obj.documents.order_by("document_type", "title"),
        "assets": obj.assets.order_by("-created_at"),  # sub-table shows issued_at, not issued_by
        "sessions": obj.orientation_sessions.select_related("facilitator").order_by("scheduled_at"),
    })


@login_required
def onboardingprogram_edit(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status in ("completed", "cancelled"):
        messages.error(request, "A completed or cancelled program cannot be edited.")
        return redirect("hrm:onboardingprogram_detail", pk=obj.pk)
    return crud_edit(request, model=OnboardingProgram, pk=pk, form_class=OnboardingProgramForm,
                     template="hrm/onboarding/program/form.html",
                     success_url="hrm:onboardingprogram_list")


@login_required
@require_POST
def onboardingprogram_delete(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    # Only a draft or cancelled program is deletable — an active/completed one has live records.
    if obj.status not in ("draft", "cancelled"):
        messages.error(request, "Only a draft or cancelled program can be deleted. Cancel it first.")
        return redirect("hrm:onboardingprogram_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Onboarding program deleted.")
    return redirect("hrm:onboardingprogram_list")


@login_required
@require_POST
def onboardingprogram_activate(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        with transaction.atomic():
            obj.status = "active"
            obj.save(update_fields=["status", "updated_at"])
            created = generate_tasks_from_template(obj)
        write_audit_log(request.user, obj, "update",
                        {"action": "activate", "tasks_generated": created})
        messages.success(request, f"Onboarding program {obj.number} activated"
                         + (f" — {created} task(s) generated." if created else "."))
        # A program with no template (and so no generated tasks) starts empty — nudge HR to add some.
        if not created and not obj.template_id:
            messages.warning(request, "No template attached — add onboarding tasks manually.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.pk)


@login_required
@require_POST
def onboardingprogram_generate_tasks(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "active"):
        if not obj.template_id:
            messages.error(request, "This program has no template to generate tasks from.")
        else:
            with transaction.atomic():
                created = generate_tasks_from_template(obj)
            write_audit_log(request.user, obj, "update",
                            {"action": "generate_tasks", "tasks_generated": created})
            if created:
                messages.success(request, f"{created} task(s) generated from the template.")
            else:
                messages.info(request, "No new tasks — they were already generated.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.pk)


@tenant_admin_required  # closing out an onboarding is a privileged HR/admin action
@require_POST
def onboardingprogram_complete(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status == "active":
        obj.status = "completed"
        obj.completed_at = timezone.now()
        obj.save(update_fields=["status", "completed_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"Onboarding program {obj.number} marked complete.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.pk)


@tenant_admin_required  # cancelling an onboarding is a privileged HR/admin action
@require_POST
def onboardingprogram_cancel(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "active"):
        obj.status = "cancelled"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Onboarding program {obj.number} cancelled.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.pk)
