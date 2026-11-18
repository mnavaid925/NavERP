import csv

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.InProcessQuality.ProcessParameterLogs import ProcessParameterLogForm
from apps.quality.models.InProcessQuality.ProcessParameterLogs import ProcessParameterLog

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def process_parameter_log_list(request):
    qs = ProcessParameterLog.objects.filter(tenant=request.tenant).select_related(
        "work_order", "work_center", "logged_by", "non_conformance", "process_deviation"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(parameter_name__icontains=search_query)
            | Q(item_code__icontains=search_query)
            | Q(lot_number__icontains=search_query)
            | Q(production_order_number__icontains=search_query)
            | Q(work_center_code__icontains=search_query)
        )

    current_category = request.GET.get("parameter_category", "").strip()
    if current_category:
        qs = qs.filter(parameter_category=current_category)

    current_excursion = request.GET.get("excursion_status", "").strip()
    if current_excursion:
        qs = qs.filter(excursion_status=current_excursion)

    current_containment = request.GET.get("containment_action", "").strip()
    if current_containment:
        qs = qs.filter(containment_action=current_containment)

    current_work_center = request.GET.get("work_center", "").strip()
    if current_work_center.isdigit():
        qs = qs.filter(work_center_id=int(current_work_center))

    stats = ProcessParameterLog.objects.filter(tenant=request.tenant).aggregate(
        total_logs_count=Count("id"),
        normal_count=Count("id", filter=Q(excursion_status="normal")),
        out_of_control_count=Count("id", filter=Q(excursion_status="out_of_control")),
        out_of_spec_count=Count("id", filter=Q(excursion_status="out_of_spec")),
    )
    total_logs_count = stats["total_logs_count"] or 0
    normal_count = stats["normal_count"] or 0
    out_of_control_count = stats["out_of_control_count"] or 0
    out_of_spec_count = stats["out_of_spec_count"] or 0

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    work_centers = []
    try:
        WorkCenter = apps.get_model("scm", "WorkCenter")
        work_centers = list(WorkCenter.objects.filter(tenant=request.tenant).only("id", "code", "name").order_by("code"))
    except LookupError:
        pass

    context = {
        "page_obj": page_obj,
        "parameter_logs": page_obj,
        "category_choices": ProcessParameterLog.PARAMETER_CATEGORY_CHOICES,
        "excursion_choices": ProcessParameterLog.EXCURSION_STATUS_CHOICES,
        "containment_choices": ProcessParameterLog.CONTAINMENT_ACTION_CHOICES,
        "work_centers": work_centers,
        "total_logs_count": total_logs_count,
        "normal_count": normal_count,
        "out_of_control_count": out_of_control_count,
        "out_of_spec_count": out_of_spec_count,
        "search_query": search_query,
        "current_category": current_category,
        "current_excursion": current_excursion,
        "current_containment": current_containment,
        "current_work_center": current_work_center,
    }
    return render(
        request,
        "quality/inprocessquality/process_parameter_log/list.html",
        context,
    )


@login_required
def process_parameter_log_detail(request, pk):
    log = get_object_or_404(
        ProcessParameterLog.objects.filter(tenant=request.tenant).select_related(
            "work_order__item", "work_center", "logged_by", "non_conformance", "process_deviation"
        ),
        pk=pk,
    )
    context = {
        "log": log,
    }
    return render(
        request,
        "quality/inprocessquality/process_parameter_log/detail.html",
        context,
    )


@login_required
def process_parameter_log_create(request):
    if request.method == "POST":
        form = ProcessParameterLogForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            log = form.save(commit=False)
            log.tenant = request.tenant
            log.logged_by = request.user
            log.save()
            form.save_m2m()
            write_audit_log(request.user, log, "create", tenant=request.tenant)
            messages.success(request, f"Parameter log {log.number} recorded successfully.")
            return redirect("quality:process_parameter_log_detail", pk=log.pk)
    else:
        form = ProcessParameterLogForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "log": None,
        "title": "Log Critical Process Parameter",
    }
    return render(
        request,
        "quality/inprocessquality/process_parameter_log/form.html",
        context,
    )


@login_required
def process_parameter_log_edit(request, pk):
    log = get_object_or_404(ProcessParameterLog, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = ProcessParameterLogForm(request.POST, instance=log, tenant=request.tenant)
        if form.is_valid():
            log = form.save()
            write_audit_log(request.user, log, "update", tenant=request.tenant)
            messages.success(request, f"Parameter log {log.number} updated successfully.")
            return redirect("quality:process_parameter_log_detail", pk=log.pk)
    else:
        form = ProcessParameterLogForm(instance=log, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "log": log,
        "title": f"Edit Process Parameter Log: {log.number}",
    }
    return render(
        request,
        "quality/inprocessquality/process_parameter_log/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def process_parameter_log_delete(request, pk):
    log = get_object_or_404(ProcessParameterLog, pk=pk, tenant=request.tenant)
    number = log.number
    write_audit_log(request.user, log, "delete", tenant=request.tenant)
    log.delete()
    messages.success(request, f"Parameter log {number} deleted successfully.")
    return redirect("quality:process_parameter_log_list")


@login_required
def process_parameter_log_export_csv(request):
    qs = ProcessParameterLog.objects.filter(tenant=request.tenant).order_by("-recorded_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="process_parameter_logs.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Log Number",
        "Parameter Name",
        "Category",
        "Unit",
        "Recorded Value",
        "Target Nominal",
        "LSL",
        "USL",
        "LCL",
        "UCL",
        "Excursion Status",
        "Containment Action",
        "Item Code",
        "Lot Number",
        "Recorded At",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.parameter_name),
            _csv_safe(item.get_parameter_category_display()),
            _csv_safe(item.unit_of_measure),
            _csv_safe(item.recorded_value),
            _csv_safe(item.target_nominal_value),
            _csv_safe(item.lower_spec_limit),
            _csv_safe(item.upper_spec_limit),
            _csv_safe(item.lower_control_limit),
            _csv_safe(item.upper_control_limit),
            _csv_safe(item.get_excursion_status_display()),
            _csv_safe(item.get_containment_action_display()),
            _csv_safe(item.item_code),
            _csv_safe(item.lot_number),
            _csv_safe(item.recorded_at),
        ])

    return response
