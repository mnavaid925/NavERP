"""Projects 7.15 Financial & Billing Management — ProjectRevenueSchedule views.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, crud_create, crud_delete, crud_edit, crud_list
from apps.core.utils import write_audit_log
from apps.projects.forms.FinancialBillingManagement.RevenueSchedules import (
    ProjectRevenueScheduleForm,
    RevenueScheduleRecognizeForm,
)
from apps.projects.models.FinancialBillingManagement.RevenueSchedules import ProjectRevenueSchedule
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import login_required


@login_required
def prs_list(request):
    qs = (
        ProjectRevenueSchedule.objects.filter(tenant=request.tenant)
        .select_related("project", "milestone", "fiscal_period", "cost_center", "gl_account", "journal_entry")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    method_filter = request.GET.get("method", "")
    if method_filter:
        qs = qs.filter(method=method_filter)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/financialbilling/revenueschedule/list.html",
        search_fields=["number", "project__name", "milestone__name", "notes"],
        filters=[
            ("status", "status", False),
            ("method", "method", False),
        ],
        extra_context={
            "projects": projects,
            "project_filter": project_id,
            "status_choices": ProjectRevenueSchedule.STATUS_CHOICES,
            "status_filter": status_filter,
            "method_choices": ProjectRevenueSchedule.METHOD_CHOICES,
            "method_filter": method_filter,
            "total_count": qs.count(),
        },
    )


@login_required
def prs_create(request):
    return crud_create(
        request,
        form_class=ProjectRevenueScheduleForm,
        template="projects/financialbilling/revenueschedule/form.html",
        success_url="projects:prs_list",
        extra_context={"is_edit": False},
    )


@login_required
def prs_detail(request, pk):
    schedule = get_object_or_404(
        ProjectRevenueSchedule.objects.select_related(
            "project", "milestone", "fiscal_period", "cost_center", "gl_account", "journal_entry", "recognized_by"
        ),
        pk=pk,
        tenant=request.tenant,
    )
    recognize_form = RevenueScheduleRecognizeForm(initial={"recognition_date": schedule.recognition_date})
    return render(
        request,
        "projects/financialbilling/revenueschedule/detail.html",
        {
            "obj": schedule,
            "schedule": schedule,
            "recognize_form": recognize_form,
        },
    )


@login_required
def prs_edit(request, pk):
    schedule = get_object_or_404(
        ProjectRevenueSchedule,
        pk=pk,
        tenant=request.tenant,
    )
    if schedule.status in ("locked", "void"):
        messages.warning(request, f"Revenue schedule {schedule.number} is {schedule.get_status_display()} and cannot be edited.")
        return redirect("projects:prs_detail", pk=schedule.pk)

    return crud_edit(
        request,
        model=ProjectRevenueSchedule,
        pk=pk,
        form_class=ProjectRevenueScheduleForm,
        template="projects/financialbilling/revenueschedule/form.html",
        success_url="projects:prs_list",
        extra_context={"is_edit": True, "obj": schedule, "schedule": schedule},
    )


@login_required
@require_POST
def prs_delete(request, pk):
    schedule = get_object_or_404(ProjectRevenueSchedule, pk=pk, tenant=request.tenant)
    if schedule.status in ("recognized", "locked"):
        messages.error(request, f"Cannot delete revenue schedule with status {schedule.get_status_display()}.")
        return redirect("projects:prs_detail", pk=schedule.pk)

    return crud_delete(
        request,
        model=ProjectRevenueSchedule,
        pk=pk,
        success_url="projects:prs_list",
    )


@login_required
@require_POST
def prs_approve(request, pk):
    schedule = get_object_or_404(ProjectRevenueSchedule, pk=pk, tenant=request.tenant)
    if schedule.status != "draft":
        messages.error(request, f"Schedule {schedule.number} cannot be approved because status is {schedule.get_status_display()}.")
        return redirect("projects:prs_detail", pk=schedule.pk)

    schedule.status = "approved"
    schedule.save(update_fields=["status", "updated_at"])
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="approve",
        obj=schedule,
        changes={"status": ["draft", "approved"]},
    )
    messages.success(request, f"Revenue schedule {schedule.number} approved.")
    return redirect("projects:prs_detail", pk=schedule.pk)


@login_required
@require_POST
def prs_recognize(request, pk):
    schedule = get_object_or_404(ProjectRevenueSchedule, pk=pk, tenant=request.tenant)
    if schedule.status not in ("draft", "approved"):
        messages.error(request, f"Schedule {schedule.number} cannot be recognized because status is {schedule.get_status_display()}.")
        return redirect("projects:prs_detail", pk=schedule.pk)

    form = RevenueScheduleRecognizeForm(request.POST)
    if form.is_valid():
        rec_date = form.cleaned_data["recognition_date"]
        notes = form.cleaned_data.get("notes", "")

        schedule.recognition_date = rec_date
        schedule.status = "recognized"
        schedule.recognized_at = timezone.now()
        schedule.recognized_by = request.user
        if notes:
            schedule.notes = (schedule.notes + f"\n[Recognition note]: {notes}").strip()

        schedule.save(update_fields=["recognition_date", "status", "recognized_at", "recognized_by", "notes", "updated_at"])
        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="recognize",
            obj=schedule,
            changes={"status": ["approved", "recognized"], "recognized_amount": str(schedule.recognized_amount)},
        )
        messages.success(request, f"Revenue schedule {schedule.number} successfully marked as recognized.")
    else:
        messages.error(request, "Invalid recognition parameters.")

    return redirect("projects:prs_detail", pk=schedule.pk)


@login_required
@require_POST
def prs_lock(request, pk):
    schedule = get_object_or_404(ProjectRevenueSchedule, pk=pk, tenant=request.tenant)
    if schedule.status != "recognized":
        messages.error(request, f"Only recognized revenue schedules can be locked.")
        return redirect("projects:prs_detail", pk=schedule.pk)

    schedule.status = "locked"
    schedule.save(update_fields=["status", "updated_at"])
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="lock",
        obj=schedule,
        changes={"status": ["recognized", "locked"]},
    )
    messages.success(request, f"Revenue schedule {schedule.number} is now locked against modification.")
    return redirect("projects:prs_detail", pk=schedule.pk)
