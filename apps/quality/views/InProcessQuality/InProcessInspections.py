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
from apps.quality.forms.InProcessQuality.InProcessInspections import InProcessInspectionForm
from apps.quality.models.InProcessQuality.InProcessInspections import InProcessInspection

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def in_process_inspection_list(request):
    qs = InProcessInspection.objects.filter(tenant=request.tenant).select_related(
        "work_order", "work_center", "operator", "inspector", "non_conformance"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(item_code__icontains=search_query)
            | Q(item_name__icontains=search_query)
            | Q(lot_number__icontains=search_query)
            | Q(serial_number__icontains=search_query)
            | Q(production_order_number__icontains=search_query)
            | Q(work_center_code__icontains=search_query)
            | Q(stage_gate__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_disposition = request.GET.get("disposition", "").strip()
    if current_disposition:
        qs = qs.filter(disposition=current_disposition)

    current_type = request.GET.get("inspection_type", "").strip()
    if current_type:
        qs = qs.filter(inspection_type=current_type)

    current_defect = request.GET.get("defect_category", "").strip()
    if current_defect:
        qs = qs.filter(defect_category=current_defect)

    current_work_center = request.GET.get("work_center", "").strip()
    if current_work_center.isdigit():
        qs = qs.filter(work_center_id=int(current_work_center))

    stats = InProcessInspection.objects.filter(tenant=request.tenant).aggregate(
        total_inspections_count=Count("id"),
        passed_count=Count("id", filter=Q(disposition="pass")),
        rework_count=Count("id", filter=Q(disposition="rework_required")),
        rejected_count=Count("id", filter=Q(disposition__in=["reject_scrap", "quarantine_hold"])),
    )
    total_inspections_count = stats["total_inspections_count"] or 0
    passed_count = stats["passed_count"] or 0
    rework_count = stats["rework_count"] or 0
    rejected_count = stats["rejected_count"] or 0

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
        "inspections": page_obj,
        "status_choices": InProcessInspection.STATUS_CHOICES,
        "disposition_choices": InProcessInspection.DISPOSITION_CHOICES,
        "type_choices": InProcessInspection.INSPECTION_TYPE_CHOICES,
        "defect_choices": InProcessInspection.DEFECT_CATEGORY_CHOICES,
        "work_centers": work_centers,
        "total_inspections_count": total_inspections_count,
        "passed_count": passed_count,
        "rework_count": rework_count,
        "rejected_count": rejected_count,
        "search_query": search_query,
        "current_status": current_status,
        "current_disposition": current_disposition,
        "current_type": current_type,
        "current_defect": current_defect,
        "current_work_center": current_work_center,
    }
    return render(
        request,
        "quality/inprocessquality/in_process_inspection/list.html",
        context,
    )


@login_required
def in_process_inspection_detail(request, pk):
    inspection = get_object_or_404(
        InProcessInspection.objects.filter(tenant=request.tenant).select_related(
            "work_order__item", "work_center", "operator", "inspector", "controlled_document", "non_conformance"
        ),
        pk=pk,
    )
    context = {
        "inspection": inspection,
    }
    return render(
        request,
        "quality/inprocessquality/in_process_inspection/detail.html",
        context,
    )


@login_required
def in_process_inspection_create(request):
    if request.method == "POST":
        form = InProcessInspectionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            inspection = form.save(commit=False)
            inspection.tenant = request.tenant
            inspection.save()
            form.save_m2m()
            write_audit_log(request.user, inspection, "create", tenant=request.tenant)
            messages.success(request, f"Inspection {inspection.number} created successfully.")
            return redirect("quality:in_process_inspection_detail", pk=inspection.pk)
    else:
        form = InProcessInspectionForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "inspection": None,
        "title": "New In-Process Inspection",
    }
    return render(
        request,
        "quality/inprocessquality/in_process_inspection/form.html",
        context,
    )


@login_required
def in_process_inspection_edit(request, pk):
    inspection = get_object_or_404(InProcessInspection, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = InProcessInspectionForm(request.POST, instance=inspection, tenant=request.tenant)
        if form.is_valid():
            inspection = form.save()
            write_audit_log(request.user, inspection, "update", tenant=request.tenant)
            messages.success(request, f"Inspection {inspection.number} updated successfully.")
            return redirect("quality:in_process_inspection_detail", pk=inspection.pk)
    else:
        form = InProcessInspectionForm(instance=inspection, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "inspection": inspection,
        "title": f"Edit In-Process Inspection: {inspection.number}",
    }
    return render(
        request,
        "quality/inprocessquality/in_process_inspection/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def in_process_inspection_delete(request, pk):
    inspection = get_object_or_404(InProcessInspection, pk=pk, tenant=request.tenant)
    number = inspection.number
    write_audit_log(request.user, inspection, "delete", tenant=request.tenant)
    inspection.delete()
    messages.success(request, f"Inspection {number} deleted successfully.")
    return redirect("quality:in_process_inspection_list")


@login_required
def in_process_inspection_export_csv(request):
    qs = InProcessInspection.objects.filter(tenant=request.tenant).order_by("-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="in_process_inspections.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Inspection Number",
        "Title",
        "Type",
        "Stage Gate",
        "Status",
        "Disposition",
        "Item Code",
        "Lot Number",
        "Batch Qty",
        "Sample Size",
        "Qty Passed",
        "Qty Rejected",
        "Defect Category",
        "Inspection Date",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.get_inspection_type_display()),
            _csv_safe(item.stage_gate),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.get_disposition_display()),
            _csv_safe(item.item_code),
            _csv_safe(item.lot_number),
            _csv_safe(item.batch_quantity),
            _csv_safe(item.sample_size_inspected),
            _csv_safe(item.quantity_passed),
            _csv_safe(item.quantity_rejected),
            _csv_safe(item.get_defect_category_display()),
            _csv_safe(item.inspection_date),
        ])

    return response
