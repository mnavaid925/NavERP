import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.CalibrationAnalysis.CalibrationGages import CalibrationGageForm
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def calibration_gage_list(request):
    qs = quality_scope(CalibrationGage.objects.all(), request).select_related(
        "department", "custodian", "work_center"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(gage_id__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(serial_number__icontains=search_query)
            | Q(manufacturer__icontains=search_query)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get("gage_type", "").strip()
    if type_filter:
        qs = qs.filter(gage_type=type_filter)

    criticality_filter = request.GET.get("criticality", "").strip()
    if criticality_filter:
        qs = qs.filter(criticality=criticality_filter)

    total_gages = qs.count()
    base_qs = quality_scope(CalibrationGage.objects.all(), request)
    past_due_count = base_qs.filter(
        Q(status="past_due") | Q(next_calibration_due__lt=date.today(), status="active_in_service")
    ).count()
    in_service_count = base_qs.filter(status="active_in_service").count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "gages": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "criticality_filter": criticality_filter,
        "status_choices": CalibrationGage.STATUS_CHOICES,
        "type_choices": CalibrationGage.GAGE_TYPE_CHOICES,
        "criticality_choices": CalibrationGage.CRITICALITY_CHOICES,
        "total_gages": total_gages,
        "past_due_count": past_due_count,
        "in_service_count": in_service_count,
    }
    return render(request, "quality/calibrationanalysis/calibration_gage/list.html", context)


@login_required
def calibration_gage_detail(request, pk):
    gage = quality_object(
        request, CalibrationGage, pk,
        select_related=("department", "custodian", "work_center", "asset_link", "sop_document", "reference_standard_parent")
    )
    calibration_history = gage.calibration_records.filter(tenant=request.tenant).order_by("-calibration_date")[:10]
    oot_history = gage.oot_investigations.filter(tenant=request.tenant).order_by("-discovery_date")[:5]
    msa_studies = gage.msa_studies.filter(tenant=request.tenant).order_by("-study_date")[:5]

    context = {
        "gage": gage,
        "obj": gage,
        "calibration_history": calibration_history,
        "oot_history": oot_history,
        "msa_studies": msa_studies,
    }
    return render(request, "quality/calibrationanalysis/calibration_gage/detail.html", context)


@login_required
def calibration_gage_create(request):
    if request.method == "POST":
        form = CalibrationGageForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            gage = form.save(commit=False)
            gage.tenant = request.tenant
            gage.save()
            write_audit_log(request.user, gage, "create", tenant=request.tenant)
            messages.success(request, f"Gage {gage.gage_id} created successfully.")
            return redirect("quality:calibration_gage_detail", pk=gage.pk)
    else:
        form = CalibrationGageForm(tenant=request.tenant)

    context = {
        "form": form,
        "gage": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "quality/calibrationanalysis/calibration_gage/form.html", context)


@login_required
def calibration_gage_edit(request, pk):
    gage = quality_object(request, CalibrationGage, pk)
    if request.method == "POST":
        form = CalibrationGageForm(request.POST, instance=gage, tenant=request.tenant)
        if form.is_valid():
            gage = form.save()
            write_audit_log(request.user, gage, "update", tenant=request.tenant)
            messages.success(request, f"Gage {gage.gage_id} updated successfully.")
            return redirect("quality:calibration_gage_detail", pk=gage.pk)
    else:
        form = CalibrationGageForm(instance=gage, tenant=request.tenant)

    context = {
        "form": form,
        "gage": gage,
        "obj": gage,
        "is_edit": True,
    }
    return render(request, "quality/calibrationanalysis/calibration_gage/form.html", context)


@require_POST
@login_required
@tenant_admin_required
def calibration_gage_delete(request, pk):
    gage = quality_object(request, CalibrationGage, pk)
    gage_id = gage.gage_id
    write_audit_log(request.user, gage, "delete", tenant=request.tenant)
    gage.delete()
    messages.success(request, f"Gage {gage_id} deleted.")
    return redirect("quality:calibration_gage_list")


@login_required
def calibration_gage_export_csv(request):
    qs = quality_scope(CalibrationGage.objects.all(), request).order_by("gage_id")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="calibration_gages.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Gage ID", "Name", "Type", "Criticality", "Status",
        "Serial Number", "Range", "MPE", "Unit", "Next Due", "Location"
    ])
    for g in qs:
        writer.writerow([
            g.gage_id, g.name, g.get_gage_type_display(), g.get_criticality_display(),
            g.get_status_display(), g.serial_number, g.measurement_range,
            str(g.max_permissible_error), g.engineering_unit,
            g.next_calibration_due.isoformat() if g.next_calibration_due else "",
            g.storage_location
        ])
    return response
