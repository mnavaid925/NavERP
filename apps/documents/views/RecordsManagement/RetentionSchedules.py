from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.documents.forms.RecordsManagement.RetentionSchedules import RetentionScheduleForm
from apps.documents.models.RecordsManagement.RetentionSchedules import RetentionSchedule
from apps.documents.views._common import documents_object, documents_scope


@login_required
def retention_schedule_list(request):
    qs = documents_scope(RetentionSchedule.objects.all(), request).select_related("department")

    current_framework = request.GET.get("compliance_framework", "").strip()
    if current_framework:
        qs = qs.filter(compliance_framework=current_framework)

    current_mode = request.GET.get("retention_mode", "").strip()
    if current_mode:
        qs = qs.filter(retention_mode=current_mode)

    current_status = request.GET.get("status", "").strip()
    if current_status == "active":
        qs = qs.filter(is_active=True)
    elif current_status == "inactive":
        qs = qs.filter(is_active=False)

    department_id = request.GET.get("department", "").strip()
    if department_id.isdigit():
        qs = qs.filter(department_id=int(department_id))

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(code__icontains=query)
            | Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(legal_citation__icontains=query)
        )

    qs = qs.order_by("code", "name")
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "schedules": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "framework_choices": RetentionSchedule.FRAMEWORK_CHOICES,
        "retention_mode_choices": RetentionSchedule.RETENTION_MODE_CHOICES,
        "departments": departments,
        "current_framework": current_framework,
        "current_mode": current_mode,
        "current_status": current_status,
        "query": query,
    }
    return render(request, "documents/records_management/retention_schedule/list.html", context)


@login_required
def retention_schedule_detail(request, pk):
    schedule = documents_object(request, RetentionSchedule, pk, select_related=("department",))
    declared_records_qs = schedule.declared_records.filter(tenant=request.tenant).select_related("document", "declared_by")
    declared_records_count = declared_records_qs.count()
    declared_records = declared_records_qs.order_by("-declaration_date")[:10]

    context = {
        "schedule": schedule,
        "declared_records": declared_records,
        "declared_records_count": declared_records_count,
    }
    return render(request, "documents/records_management/retention_schedule/detail.html", context)


@login_required
def retention_schedule_create(request):
    if request.method == "POST":
        form = RetentionScheduleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.tenant = request.tenant
            schedule.save()
            write_audit_log(request.user, schedule, "create", tenant=request.tenant)
            messages.success(request, f"Retention schedule '{schedule.code} - {schedule.name}' created.")
            return redirect("documents:retention_schedule_detail", pk=schedule.pk)
    else:
        form = RetentionScheduleForm(tenant=request.tenant)

    context = {
        "form": form,
        "schedule": None,
        "is_edit": False,
    }
    return render(request, "documents/records_management/retention_schedule/form.html", context)


@login_required
def retention_schedule_edit(request, pk):
    schedule = documents_object(request, RetentionSchedule, pk)
    if request.method == "POST":
        form = RetentionScheduleForm(request.POST, instance=schedule, tenant=request.tenant)
        if form.is_valid():
            schedule = form.save()
            write_audit_log(request.user, schedule, "update", tenant=request.tenant)
            messages.success(request, f"Retention schedule '{schedule.code}' updated.")
            return redirect("documents:retention_schedule_detail", pk=schedule.pk)
    else:
        form = RetentionScheduleForm(instance=schedule, tenant=request.tenant)

    context = {
        "form": form,
        "schedule": schedule,
        "is_edit": True,
    }
    return render(request, "documents/records_management/retention_schedule/form.html", context)


@login_required
@require_POST
def retention_schedule_delete(request, pk):
    schedule = documents_object(request, RetentionSchedule, pk)
    if schedule.declared_records.filter(tenant=request.tenant).exists():
        messages.error(request, "Cannot delete retention schedule because records are currently assigned to it.")
        return redirect("documents:retention_schedule_detail", pk=schedule.pk)

    code = schedule.code
    write_audit_log(request.user, schedule, "delete", tenant=request.tenant)
    schedule.delete()
    messages.success(request, f"Retention schedule '{code}' was deleted.")
    return redirect("documents:retention_schedule_list")
