import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.quality.forms.EhsManagement.EnvironmentalMonitoringLogs import EnvironmentalMonitoringLogForm
from apps.quality.models.EhsManagement.EnvironmentalMonitoringLogs import EnvironmentalMonitoringLog
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def environmental_monitoring_log_list(request):
    qs = quality_scope(EnvironmentalMonitoringLog.objects.all(), request).select_related(
        "org_unit", "sampled_by", "measurement_instrument"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(sampling_point_id__icontains=q)
            | Q(parameter_name__icontains=q)
            | Q(excursion_details__icontains=q)
        )

    eval_filter = request.GET.get("evaluation_status", "").strip()
    if eval_filter:
        qs = qs.filter(evaluation_status=eval_filter)

    class_filter = request.GET.get("cleanroom_class", "").strip()
    if class_filter:
        qs = qs.filter(cleanroom_class=class_filter)

    cat_filter = request.GET.get("monitoring_category", "").strip()
    if cat_filter:
        qs = qs.filter(monitoring_category=cat_filter)

    org_unit_filter = request.GET.get("org_unit", "").strip()
    if org_unit_filter and org_unit_filter.isdigit():
        qs = qs.filter(org_unit_id=int(org_unit_filter))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if "page" in query_params:
        del query_params["page"]

    context = {
        "environmental_logs": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "evaluation_status_choices": EnvironmentalMonitoringLog.EVALUATION_STATUS_CHOICES,
        "cleanroom_class_choices": EnvironmentalMonitoringLog.CLEANROOM_CLASS_CHOICES,
        "category_choices": EnvironmentalMonitoringLog.MONITORING_CATEGORY_CHOICES,
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "query_string": query_params.urlencode(),
    }
    return render(request, "quality/ehsmanagement/environmental_monitoring_log/list.html", context)


@login_required
def environmental_monitoring_log_create(request):
    if request.method == "POST":
        form = EnvironmentalMonitoringLogForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Environmental monitoring log {obj.number} recorded.")
            return redirect("quality:environmental_monitoring_log_detail", pk=obj.pk)
    else:
        form = EnvironmentalMonitoringLogForm(
            tenant=request.tenant,
            initial={
                "sampling_timestamp": timezone.now(),
                "sampled_by": request.user,
            },
        )

    context = {
        "form": form,
        "environmental_log": None,
        "is_edit": False,
    }
    return render(request, "quality/ehsmanagement/environmental_monitoring_log/form.html", context)


@login_required
def environmental_monitoring_log_detail(request, pk):
    obj = quality_object(
        request,
        EnvironmentalMonitoringLog,
        pk,
        select_related=[
            "org_unit",
            "sampled_by",
            "verified_by",
            "measurement_instrument",
            "process_deviation",
            "non_conformance_report",
            "capa_investigation",
        ],
    )
    context = {
        "environmental_log": obj,
    }
    return render(request, "quality/ehsmanagement/environmental_monitoring_log/detail.html", context)


@login_required
def environmental_monitoring_log_update(request, pk):
    obj = quality_object(
        request,
        EnvironmentalMonitoringLog,
        pk,
        select_related=[
            "org_unit",
            "sampled_by",
            "verified_by",
            "measurement_instrument",
            "process_deviation",
            "non_conformance_report",
            "capa_investigation",
        ],
    )
    if request.method == "POST":
        form = EnvironmentalMonitoringLogForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Environmental monitoring log {obj.number} updated.")
            return redirect("quality:environmental_monitoring_log_detail", pk=obj.pk)
    else:
        form = EnvironmentalMonitoringLogForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "environmental_log": obj,
        "is_edit": True,
    }
    return render(request, "quality/ehsmanagement/environmental_monitoring_log/form.html", context)


environmental_monitoring_log_edit = environmental_monitoring_log_update


@login_required
@require_POST
def environmental_monitoring_log_delete(request, pk):
    obj = quality_object(request, EnvironmentalMonitoringLog, pk)
    if not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)):
        messages.error(request, "Only tenant administrators can delete environmental monitoring logs.")
        return redirect("quality:environmental_monitoring_log_detail", pk=obj.pk)

    if obj.evaluation_status in ("alert_exceeded", "action_exceeded"):
        messages.error(request, "Environmental logs with recorded alert or action excursions cannot be deleted.")
        return redirect("quality:environmental_monitoring_log_detail", pk=obj.pk)

    num = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Environmental monitoring log {num} deleted.")
    return redirect("quality:environmental_monitoring_log_list")


@login_required
def environmental_monitoring_log_export(request):
    qs = quality_scope(EnvironmentalMonitoringLog.objects.all(), request).select_related(
        "org_unit", "sampled_by", "verified_by", "measurement_instrument"
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(sampling_point_id__icontains=q)
            | Q(parameter_name__icontains=q)
            | Q(excursion_details__icontains=q)
        )

    eval_filter = request.GET.get("evaluation_status", "").strip()
    if eval_filter:
        qs = qs.filter(evaluation_status=eval_filter)

    class_filter = request.GET.get("cleanroom_class", "").strip()
    if class_filter:
        qs = qs.filter(cleanroom_class=class_filter)

    cat_filter = request.GET.get("monitoring_category", "").strip()
    if cat_filter:
        qs = qs.filter(monitoring_category=cat_filter)

    org_unit_filter = request.GET.get("org_unit", "").strip()
    if org_unit_filter and org_unit_filter.isdigit():
        qs = qs.filter(org_unit_id=int(org_unit_filter))

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="environmental_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Log Number",
        "Sampling Point ID",
        "Timestamp",
        "Cleanroom Class",
        "Operational State",
        "Monitoring Category",
        "Parameter Name",
        "Measured Value",
        "UOM",
        "Nominal Target",
        "Alert Limit (Upper)",
        "Action Limit (Upper)",
        "Evaluation Status",
        "Technician",
        "Instrument",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.sampling_point_id),
            _csv_safe(item.sampling_timestamp),
            _csv_safe(item.get_cleanroom_class_display()),
            _csv_safe(item.get_operational_state_display()),
            _csv_safe(item.get_monitoring_category_display()),
            _csv_safe(item.parameter_name),
            _csv_safe(item.measured_value),
            _csv_safe(item.get_unit_of_measure_display()),
            _csv_safe(item.target_nominal_value),
            _csv_safe(item.upper_alert_limit),
            _csv_safe(item.upper_action_limit),
            _csv_safe(item.get_evaluation_status_display()),
            _csv_safe(item.sampled_by.get_full_name() or item.sampled_by.username if item.sampled_by else ""),
            _csv_safe(item.measurement_instrument.gage_id if item.measurement_instrument else ""),
        ])
    return response


@login_required
@require_POST
def environmental_monitoring_log_evaluate(request, pk):
    obj = quality_object(request, EnvironmentalMonitoringLog, pk)
    obj.verified_by = request.user
    obj.evaluation_status = obj.calculate_evaluation_status()
    obj.save(update_fields=["verified_by", "evaluation_status", "updated_at"])
    write_audit_log(request.user, obj, "evaluate", tenant=request.tenant)
    messages.success(request, f"Log {obj.number} verified and evaluated: {obj.get_evaluation_status_display()}.")
    return redirect("quality:environmental_monitoring_log_detail", pk=obj.pk)
