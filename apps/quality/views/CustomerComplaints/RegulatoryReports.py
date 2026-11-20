import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.CustomerComplaints.RegulatoryReports import RegulatoryReportForm
from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
from apps.quality.models.CustomerComplaints.RegulatoryReports import RegulatoryReport
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def regulatory_report_list(request):
    qs = quality_scope(RegulatoryReport.objects.all(), request).select_related(
        "complaint", "prepared_by", "reviewed_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(complaint__number__icontains=q)
            | Q(agency_report_identifier__icontains=q)
            | Q(agency_acknowledgement_number__icontains=q)
            | Q(event_summary__icontains=q)
        )

    agency_filter = request.GET.get("agency", "").strip()
    if agency_filter:
        qs = qs.filter(agency=agency_filter)

    report_type_filter = request.GET.get("report_type", "").strip()
    if report_type_filter:
        qs = qs.filter(report_type=report_type_filter)

    submission_status_filter = request.GET.get("submission_status", "").strip()
    if submission_status_filter:
        qs = qs.filter(submission_status=submission_status_filter)

    timeline_filter = request.GET.get("timeline_category", "").strip()
    if timeline_filter:
        qs = qs.filter(timeline_category=timeline_filter)

    complaint_filter = request.GET.get("complaint", "").strip()
    if complaint_filter and complaint_filter.isdigit():
        qs = qs.filter(complaint_id=int(complaint_filter))

    total_count = qs.count()

    base_tenant_qs = RegulatoryReport.objects.filter(tenant=request.tenant)
    pending_submission_count = base_tenant_qs.filter(
        submission_status__in=["draft", "under_internal_review", "ready_to_transmit"]
    ).count()

    today = timezone.now().date()
    overdue_count = base_tenant_qs.filter(
        statutory_due_date__lt=today
    ).exclude(submission_status__in=["acknowledged", "submitted", "withdrawn"]).count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    filter_querystring = query_params.urlencode()

    context = {
        "reports": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "filter_querystring": filter_querystring,
        "total_count": total_count,
        "pending_submission_count": pending_submission_count,
        "overdue_count": overdue_count,
        "agency_choices": RegulatoryReport.AGENCY_CHOICES,
        "report_type_choices": RegulatoryReport.REPORT_TYPE_CHOICES,
        "submission_status_choices": RegulatoryReport.SUBMISSION_STATUS_CHOICES,
        "timeline_category_choices": RegulatoryReport.TIMELINE_CATEGORY_CHOICES,
    }
    return render(
        request,
        "quality/customercomplaints/regulatory_report/list.html",
        context,
    )


@login_required
def regulatory_report_detail(request, pk):
    report = quality_object(
        request,
        RegulatoryReport,
        pk,
        select_related=("complaint", "complaint__customer", "prepared_by", "reviewed_by"),
    )
    return render(
        request,
        "quality/customercomplaints/regulatory_report/detail.html",
        {"report": report},
    )


@login_required
def regulatory_report_create(request):
    initial = {
        "submission_status": "draft",
        "timeline_category": "30_day_standard_mdr",
        "agency": "fda_cdrh",
        "report_type": "initial_report",
        "submission_format": "fda_emdr_xml",
    }
    complaint_pk = request.GET.get("complaint", "").strip()
    if complaint_pk and complaint_pk.isdigit():
        complaint = get_object_or_404(CustomerComplaint, pk=int(complaint_pk), tenant=request.tenant)
        initial["complaint"] = complaint
        initial["event_summary"] = complaint.problem_description
        # Calculate statutory deadline based on complaint date
        if complaint.date_received:
            initial["statutory_due_date"] = complaint.date_received + timezone.timedelta(days=30)

    if request.method == "POST":
        form = RegulatoryReportForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                report = form.save(commit=False)
                report.tenant = request.tenant
                report.save()
                # Ensure complaint is marked reportable if not already
                c = report.complaint
                if c.reportability != "reportable_event":
                    c.reportability = "reportable_event"
                    if c.status not in ["closed", "cancelled"]:
                        c.status = "pending_regulatory"
                    c.save(update_fields=["reportability", "status", "updated_at"])
                write_audit_log(request.user, report, "create", tenant=request.tenant)
            messages.success(request, f"Regulatory report {report.number} generated.")
            return redirect("quality:regulatory_report_detail", pk=report.pk)
    else:
        form = RegulatoryReportForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "quality/customercomplaints/regulatory_report/form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def regulatory_report_edit(request, pk):
    report = quality_object(request, RegulatoryReport, pk)

    if request.method == "POST":
        form = RegulatoryReportForm(request.POST, instance=report, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                report = form.save()
                write_audit_log(request.user, report, "update", tenant=request.tenant)
            messages.success(request, f"Regulatory report {report.number} updated.")
            return redirect("quality:regulatory_report_detail", pk=report.pk)
    else:
        form = RegulatoryReportForm(instance=report, tenant=request.tenant)

    return render(
        request,
        "quality/customercomplaints/regulatory_report/form.html",
        {"form": form, "report": report, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def regulatory_report_delete(request, pk):
    report = quality_object(request, RegulatoryReport, pk)
    number = report.number
    complaint_pk = report.complaint_id
    with transaction.atomic():
        write_audit_log(request.user, report, "delete", tenant=request.tenant)
        report.delete()
    messages.success(request, f"Regulatory report {number} deleted.")
    return redirect("quality:customer_complaint_detail", pk=complaint_pk)


@login_required
@require_POST
def regulatory_report_submit(request, pk):
    report = quality_object(request, RegulatoryReport, pk)
    identifier = request.POST.get("agency_report_identifier", "").strip()

    with transaction.atomic():
        report.submission_status = "submitted"
        report.submission_date = timezone.now().date()
        if identifier:
            report.agency_report_identifier = identifier
        report.save()
        write_audit_log(request.user, report, "submit", tenant=request.tenant)

    messages.success(request, f"Report {report.number} recorded as transmitted to {report.get_agency_display()}.")
    return redirect("quality:regulatory_report_detail", pk=report.pk)


@login_required
@require_POST
def regulatory_report_acknowledge(request, pk):
    report = quality_object(request, RegulatoryReport, pk)
    ack_number = request.POST.get("agency_acknowledgement_number", "").strip()

    with transaction.atomic():
        report.submission_status = "acknowledged"
        report.agency_acknowledgement_date = timezone.now().date()
        if ack_number:
            report.agency_acknowledgement_number = ack_number
        report.save()
        write_audit_log(request.user, report, "ack", tenant=request.tenant)

    messages.success(request, f"Agency gateway acknowledgement recorded for report {report.number}.")
    return redirect("quality:regulatory_report_detail", pk=report.pk)


@login_required
def regulatory_report_export_csv(request):
    qs = quality_scope(RegulatoryReport.objects.all(), request).select_related(
        "complaint", "prepared_by"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="regulatory_vigilance_reports.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Report #",
        "Complaint #",
        "Agency",
        "Report Type",
        "Adverse Event Classification",
        "Timeline Clock",
        "Statutory Due Date",
        "Submission Status",
        "Submission Date",
        "Agency Case / Report #",
        "Gateway ACK #",
        "Prepared By",
    ])

    for r in qs.iterator():
        writer.writerow([
            _csv_safe(r.number),
            _csv_safe(r.complaint.number if r.complaint else ""),
            _csv_safe(r.get_agency_display()),
            _csv_safe(r.get_report_type_display()),
            _csv_safe(r.get_adverse_event_class_display()),
            _csv_safe(r.get_timeline_category_display()),
            _csv_safe(r.statutory_due_date),
            _csv_safe(r.get_submission_status_display()),
            _csv_safe(r.submission_date),
            _csv_safe(r.agency_report_identifier),
            _csv_safe(r.agency_acknowledgement_number),
            _csv_safe(r.prepared_by.get_full_name() or r.prepared_by.username if r.prepared_by else ""),
        ])

    return response
