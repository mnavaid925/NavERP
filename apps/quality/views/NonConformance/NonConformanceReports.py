import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.NonConformance.NonConformanceReports import NonConformanceReportForm
from apps.quality.models.NonConformance.MrbDispositions import MrbDisposition
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.startswith(("=", "+", "-", "@")):
        return f"'{s}"
    return s


@login_required
def non_conformance_report_list(request):
    qs = quality_scope(
        NonConformanceReport.objects.select_related(
            "department", "initiator", "owner", "supplier_party", "capa_investigation"
        ),
        request,
        owner_field="owner",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(defect_code__icontains=q)
            | Q(affected_item_code__icontains=q)
            | Q(affected_item_name__icontains=q)
            | Q(lot_serial_numbers__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_severity = request.GET.get("severity", "").strip()
    if selected_severity:
        qs = qs.filter(severity=selected_severity)

    selected_source_type = request.GET.get("source_type", "").strip()
    if selected_source_type:
        qs = qs.filter(source_type=selected_source_type)

    selected_category = request.GET.get("category", "").strip()
    if selected_category:
        qs = qs.filter(category=selected_category)

    total_count = qs.count()
    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "non_conformance_reports": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "selected_status": selected_status,
        "selected_severity": selected_severity,
        "selected_source_type": selected_source_type,
        "selected_category": selected_category,
        "status_choices": NonConformanceReport.STATUS_CHOICES,
        "severity_choices": NonConformanceReport.SEVERITY_CHOICES,
        "source_type_choices": NonConformanceReport.SOURCE_TYPE_CHOICES,
        "category_choices": NonConformanceReport.CATEGORY_CHOICES,
        "total_count": total_count,
    }
    return render(request, "quality/nonconformance/nonconformancereport/list.html", context)


@login_required
def non_conformance_report_detail(request, pk):
    ncr = quality_object(
        request,
        NonConformanceReport,
        pk=pk,
        select_related=("department", "initiator", "owner", "supplier_party", "capa_investigation", "closed_by"),
        prefetch_related=(
            "containment_records",
            Prefetch("mrb_dispositions", queryset=MrbDisposition.objects.select_related("mrb_chair")),
            "process_deviations",
        ),
    )
    containment_records = ncr.containment_records.all()
    mrb_dispositions = ncr.mrb_dispositions.all()
    process_deviations = ncr.process_deviations.all()

    context = {
        "non_conformance_report": ncr,
        "containment_records": containment_records,
        "mrb_dispositions": mrb_dispositions,
        "process_deviations": process_deviations,
    }
    return render(request, "quality/nonconformance/nonconformancereport/detail.html", context)


@login_required
def non_conformance_report_create(request):
    if request.method == "POST":
        form = NonConformanceReportForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            ncr = form.save(commit=False)
            ncr.tenant = request.tenant
            ncr.save()
            form.save_m2m()
            write_audit_log(request.user, ncr, "create", tenant=request.tenant)
            messages.success(request, f"Non-Conformance Report {ncr.number} created successfully.")
            return redirect("quality:non_conformance_report_detail", pk=ncr.pk)
    else:
        form = NonConformanceReportForm(
            tenant=request.tenant,
            initial={"initiator": request.user, "owner": request.user},
        )

    return render(
        request,
        "quality/nonconformance/nonconformancereport/form.html",
        {"form": form, "non_conformance_report": None, "is_edit": False},
    )


@login_required
def non_conformance_report_edit(request, pk):
    ncr = quality_object(request, NonConformanceReport, pk=pk)

    if request.method == "POST":
        form = NonConformanceReportForm(request.POST, instance=ncr, tenant=request.tenant)
        if form.is_valid():
            ncr = form.save(commit=False)
            if ncr.status == "closed" and not ncr.closed_at:
                ncr.closed_at = timezone.now()
                ncr.closed_by = request.user
            ncr.save()
            form.save_m2m()
            write_audit_log(request.user, ncr, "update", tenant=request.tenant)
            messages.success(request, f"Non-Conformance Report {ncr.number} updated successfully.")
            return redirect("quality:non_conformance_report_detail", pk=ncr.pk)
    else:
        form = NonConformanceReportForm(instance=ncr, tenant=request.tenant)

    return render(
        request,
        "quality/nonconformance/nonconformancereport/form.html",
        {"form": form, "non_conformance_report": ncr, "is_edit": True},
    )


@login_required
@require_POST
def non_conformance_report_delete(request, pk):
    ncr = quality_object(request, NonConformanceReport, pk=pk)
    number = ncr.number
    write_audit_log(request.user, ncr, "delete", tenant=request.tenant)
    ncr.delete()
    messages.success(request, f"Non-Conformance Report {number} deleted successfully.")
    return redirect("quality:non_conformance_report_list")


@login_required
def non_conformance_report_export_csv(request):
    qs = quality_scope(
        NonConformanceReport.objects.select_related("department", "initiator", "owner"),
        request,
        owner_field="owner",
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="non_conformance_reports.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "NCR Number",
        "Title",
        "Source Type",
        "Category",
        "Severity",
        "Status",
        "Defect Code",
        "Department",
        "Owner",
        "Affected Item Code",
        "Affected Item Name",
        "Lot / Serial Numbers",
        "Quantity Nonconforming",
        "Estimated Loss",
        "Target Resolution Date",
        "Created At",
    ])

    for ncr in qs[:1000]:
        writer.writerow([
            _csv_safe(ncr.number),
            _csv_safe(ncr.title),
            _csv_safe(ncr.get_source_type_display()),
            _csv_safe(ncr.get_category_display()),
            _csv_safe(ncr.get_severity_display()),
            _csv_safe(ncr.get_status_display()),
            _csv_safe(ncr.defect_code),
            _csv_safe(ncr.department.name if ncr.department else ""),
            _csv_safe(ncr.owner.username if ncr.owner else ""),
            _csv_safe(ncr.affected_item_code),
            _csv_safe(ncr.affected_item_name),
            _csv_safe(ncr.lot_serial_numbers),
            _csv_safe(ncr.quantity_nonconforming),
            _csv_safe(ncr.estimated_financial_loss),
            _csv_safe(ncr.target_resolution_date),
            _csv_safe(ncr.created_at.strftime("%Y-%m-%d %H:%M")),
        ])

    return response
