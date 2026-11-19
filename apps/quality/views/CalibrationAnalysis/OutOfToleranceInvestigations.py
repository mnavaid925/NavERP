import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.CalibrationAnalysis.OutOfToleranceInvestigations import OutOfToleranceInvestigationForm
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CalibrationAnalysis.CalibrationRecords import CalibrationRecord
from apps.quality.models.CalibrationAnalysis.OutOfToleranceInvestigations import OutOfToleranceInvestigation
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def out_of_tolerance_investigation_list(request):
    qs = quality_scope(OutOfToleranceInvestigation.objects.all(), request).select_related(
        "gage", "calibration_record", "suspect_work_center", "investigator", "quality_approver"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(gage__gage_id__icontains=search_query)
            | Q(gage__name__icontains=search_query)
            | Q(products_affected__icontains=search_query)
            | Q(suspect_production_orders__icontains=search_query)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    risk_filter = request.GET.get("risk_level", "").strip()
    if risk_filter:
        qs = qs.filter(risk_level=risk_filter)

    total_oots = qs.count()
    base_qs = quality_scope(OutOfToleranceInvestigation.objects.all(), request)
    critical_count = base_qs.filter(risk_level="critical").count()
    open_count = base_qs.filter(status__in=["open", "investigating", "mrb_review", "actions_pending"]).count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "oot_investigations": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "risk_filter": risk_filter,
        "status_choices": OutOfToleranceInvestigation.STATUS_CHOICES,
        "risk_choices": OutOfToleranceInvestigation.RISK_LEVEL_CHOICES,
        "total_oots": total_oots,
        "critical_count": critical_count,
        "open_count": open_count,
    }
    return render(request, "quality/calibrationanalysis/out_of_tolerance_investigation/list.html", context)


@login_required
def out_of_tolerance_investigation_detail(request, pk):
    oot = quality_object(
        request, OutOfToleranceInvestigation, pk,
        select_related=(
            "gage", "calibration_record", "suspect_work_center",
            "linked_ncr", "linked_capa", "investigator", "quality_approver"
        )
    )

    context = {
        "oot_investigation": oot,
        "obj": oot,
    }
    return render(request, "quality/calibrationanalysis/out_of_tolerance_investigation/detail.html", context)


@login_required
def out_of_tolerance_investigation_create(request):
    initial = {}
    cal_pk = request.GET.get("calibration_record")
    if cal_pk and cal_pk.isdigit():
        initial["calibration_record"] = cal_pk
        try:
            record = CalibrationRecord.objects.select_related("gage").get(pk=cal_pk, tenant=request.tenant)
            initial["gage"] = record.gage_id
            initial["as_found_error_description"] = (
                f"As-Found Condition: {record.get_as_found_condition_display()}. "
                f"Max Error: {record.max_observed_error} vs Tolerance: ±{record.gage.max_permissible_error}"
            )
            cal_date = record.calibration_date
            if cal_date:
                last_pass = (
                    CalibrationRecord.objects.filter(
                        tenant=request.tenant,
                        gage_id=record.gage_id,
                        overall_result__in=("pass", "pass_with_limitations"),
                        calibration_date__lt=cal_date,
                    )
                    .order_by("-calibration_date")
                    .first()
                )
                if last_pass and last_pass.calibration_date:
                    initial["suspect_window_start"] = last_pass.calibration_date
                elif record.gage.last_calibration_date and record.gage.last_calibration_date < cal_date:
                    initial["suspect_window_start"] = record.gage.last_calibration_date
        except CalibrationRecord.DoesNotExist:
            pass

    gage_pk = request.GET.get("gage")
    if gage_pk and gage_pk.isdigit() and "gage" not in initial:
        initial["gage"] = gage_pk

    if request.method == "POST":
        form = OutOfToleranceInvestigationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            oot = form.save(commit=False)
            oot.tenant = request.tenant
            oot.save()

            # Quarantining the gage immediately on OOT registration
            gage = oot.gage
            gage.status = "quarantined_oot"
            gage.save()

            write_audit_log(request.user, oot, "create", tenant=request.tenant)
            messages.success(request, f"OOT Investigation {oot.number} created and gage quarantined.")
            return redirect("quality:out_of_tolerance_investigation_detail", pk=oot.pk)
    else:
        form = OutOfToleranceInvestigationForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "oot_investigation": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "quality/calibrationanalysis/out_of_tolerance_investigation/form.html", context)


@login_required
def out_of_tolerance_investigation_edit(request, pk):
    oot = quality_object(request, OutOfToleranceInvestigation, pk)
    if request.method == "POST":
        form = OutOfToleranceInvestigationForm(request.POST, instance=oot, tenant=request.tenant)
        if form.is_valid():
            oot = form.save()
            write_audit_log(request.user, oot, "update", tenant=request.tenant)
            messages.success(request, f"OOT Investigation {oot.number} updated.")
            return redirect("quality:out_of_tolerance_investigation_detail", pk=oot.pk)
    else:
        form = OutOfToleranceInvestigationForm(instance=oot, tenant=request.tenant)

    context = {
        "form": form,
        "oot_investigation": oot,
        "obj": oot,
        "is_edit": True,
    }
    return render(request, "quality/calibrationanalysis/out_of_tolerance_investigation/form.html", context)


@require_POST
@login_required
@tenant_admin_required
def out_of_tolerance_investigation_delete(request, pk):
    oot = quality_object(request, OutOfToleranceInvestigation, pk)
    number = oot.number
    write_audit_log(request.user, oot, "delete", tenant=request.tenant)
    oot.delete()
    messages.success(request, f"OOT Investigation {number} deleted.")
    return redirect("quality:out_of_tolerance_investigation_list")


@login_required
def out_of_tolerance_investigation_export_csv(request):
    qs = quality_scope(OutOfToleranceInvestigation.objects.all(), request).select_related("gage").order_by("-discovery_date")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="oot_investigations.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Investigation #", "Title", "Gage Tag", "Discovery Date", "Risk Level",
        "Status", "Disposition", "Suspect Batches", "Recall Required"
    ])
    for oot in qs:
        writer.writerow([
            _csv_safe(oot.number),
            _csv_safe(oot.title),
            _csv_safe(oot.gage.gage_id),
            _csv_safe(oot.discovery_date.isoformat() if oot.discovery_date else ""),
            _csv_safe(oot.get_risk_level_display()),
            _csv_safe(oot.get_status_display()),
            _csv_safe(oot.get_product_disposition_display()),
            _csv_safe(oot.suspect_lots_count),
            _csv_safe("Yes" if oot.product_recall_required else "No"),
        ])
    return response
