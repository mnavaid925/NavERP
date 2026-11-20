import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.CustomerComplaints.CustomerComplaints import (
    ComplaintTriageForm,
    CustomerComplaintForm,
)
from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def customer_complaint_list(request):
    qs = quality_scope(CustomerComplaint.objects.all(), request).select_related(
        "customer", "assigned_to", "sales_order"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(item_code__icontains=q)
            | Q(item_name__icontains=q)
            | Q(lot_number__icontains=q)
            | Q(serial_number__icontains=q)
            | Q(complainant_name__icontains=q)
            | Q(complainant_organization__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    severity_filter = request.GET.get("severity", "").strip()
    if severity_filter:
        qs = qs.filter(severity=severity_filter)

    validity_filter = request.GET.get("validity", "").strip()
    if validity_filter:
        qs = qs.filter(validity=validity_filter)

    reportability_filter = request.GET.get("reportability", "").strip()
    if reportability_filter:
        qs = qs.filter(reportability=reportability_filter)

    intake_channel_filter = request.GET.get("intake_channel", "").strip()
    if intake_channel_filter:
        qs = qs.filter(intake_channel=intake_channel_filter)

    customer_filter = request.GET.get("customer", "").strip()
    if customer_filter and customer_filter.isdigit():
        qs = qs.filter(customer_id=int(customer_filter))

    total_count = qs.count()

    base_tenant_qs = CustomerComplaint.objects.filter(tenant=request.tenant)
    open_count = base_tenant_qs.exclude(status__in=["closed", "cancelled"]).count()
    reportable_count = base_tenant_qs.filter(reportability="reportable_event").count()
    critical_count = base_tenant_qs.filter(severity="critical_safety").count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    filter_querystring = query_params.urlencode()

    from apps.core.models import Party
    customer_options = Party.objects.filter(tenant=request.tenant).order_by("name")[:100]

    context = {
        "complaints": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "filter_querystring": filter_querystring,
        "total_count": total_count,
        "open_count": open_count,
        "reportable_count": reportable_count,
        "critical_count": critical_count,
        "intake_channel_choices": CustomerComplaint.INTAKE_CHANNEL_CHOICES,
        "severity_choices": CustomerComplaint.SEVERITY_CHOICES,
        "status_choices": CustomerComplaint.COMPLAINT_STATUS_CHOICES,
        "validity_choices": CustomerComplaint.VALIDITY_CHOICES,
        "reportability_choices": CustomerComplaint.REPORTABILITY_CHOICES,
        "customer_options": customer_options,
    }
    return render(request, "quality/customercomplaints/customer_complaint/list.html", context)


@login_required
def customer_complaint_detail(request, pk):
    complaint = quality_object(
        request,
        CustomerComplaint,
        pk,
        select_related=("customer", "sales_order", "return_authorization", "triaged_by", "closed_by", "assigned_to"),
    )

    investigations = list(complaint.investigations.select_related("lead_investigator", "qa_approved_by"))
    reports = list(complaint.regulatory_reports.select_related("prepared_by", "reviewed_by"))
    field_actions = list(complaint.field_actions.select_related("coordinator", "fsn_document"))

    triage_form = None
    if complaint.status in ["intake_received", "under_triage"]:
        triage_form = ComplaintTriageForm(instance=complaint, tenant=request.tenant)

    context = {
        "complaint": complaint,
        "investigations": investigations,
        "reports": reports,
        "field_actions": field_actions,
        "triage_form": triage_form,
    }
    return render(request, "quality/customercomplaints/customer_complaint/detail.html", context)


@login_required
def customer_complaint_create(request):
    if request.method == "POST":
        form = CustomerComplaintForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                complaint = form.save(commit=False)
                complaint.tenant = request.tenant
                complaint.save()
                write_audit_log(request.user, complaint, "create", tenant=request.tenant)
            messages.success(request, f"Customer Complaint {complaint.number} logged successfully.")
            return redirect("quality:customer_complaint_detail", pk=complaint.pk)
    else:
        initial = {
            "date_received": timezone.now().date(),
            "status": "intake_received",
            "validity": "pending_triage",
            "severity": "unspecified",
            "reportability": "undetermined",
        }
        form = CustomerComplaintForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "quality/customercomplaints/customer_complaint/form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def customer_complaint_edit(request, pk):
    complaint = quality_object(request, CustomerComplaint, pk)
    if complaint.status in ["closed", "cancelled"]:
        messages.error(request, f"Complaint {complaint.number} is {complaint.get_status_display()} and cannot be modified.")
        return redirect("quality:customer_complaint_detail", pk=complaint.pk)

    if request.method == "POST":
        form = CustomerComplaintForm(request.POST, instance=complaint, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                complaint = form.save()
                write_audit_log(request.user, complaint, "update", tenant=request.tenant)
            messages.success(request, f"Complaint {complaint.number} updated.")
            return redirect("quality:customer_complaint_detail", pk=complaint.pk)
    else:
        form = CustomerComplaintForm(instance=complaint, tenant=request.tenant)

    return render(
        request,
        "quality/customercomplaints/customer_complaint/form.html",
        {"form": form, "complaint": complaint, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def customer_complaint_delete(request, pk):
    complaint = quality_object(request, CustomerComplaint, pk)
    number = complaint.number

    if complaint.regulatory_reports.exclude(submission_status="draft").exists():
        messages.error(
            request,
            f"Cannot delete complaint {number}: active statutory regulatory reports have been filed with authorities.",
        )
        return redirect("quality:customer_complaint_detail", pk=complaint.pk)

    if complaint.investigations.filter(status="approved").exists():
        messages.error(
            request,
            f"Cannot delete complaint {number}: approved quality investigations exist.",
        )
        return redirect("quality:customer_complaint_detail", pk=complaint.pk)

    try:
        with transaction.atomic():
            complaint.regulatory_reports.filter(submission_status="draft").delete()
            complaint.investigations.exclude(status="approved").delete()
            write_audit_log(request.user, complaint, "delete", tenant=request.tenant)
            complaint.delete()
    except models.ProtectedError:
        messages.error(
            request,
            f"Cannot delete complaint {number}: protected linked records exist.",
        )
        return redirect("quality:customer_complaint_detail", pk=complaint.pk)

    messages.success(request, f"Complaint {number} has been deleted.")
    return redirect("quality:customer_complaint_list")


@login_required
@require_POST
def customer_complaint_triage(request, pk):
    complaint = quality_object(request, CustomerComplaint, pk)
    if complaint.status not in ["intake_received", "under_triage"]:
        messages.error(request, f"Complaint {complaint.number} is already triaged ({complaint.get_status_display()}).")
        return redirect("quality:customer_complaint_detail", pk=complaint.pk)

    form = ComplaintTriageForm(request.POST, instance=complaint, tenant=request.tenant)
    if form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.triaged_by = request.user
            obj.triaged_at = timezone.now()
            if obj.validity == "valid_complaint":
                if obj.investigation_required:
                    obj.status = "under_investigation"
                elif obj.reportability == "reportable_event":
                    obj.status = "pending_regulatory"
                else:
                    obj.status = "resolved"
            elif obj.validity in ["invalid_allegation", "commercial_inquiry"]:
                obj.status = "closed"
                obj.closed_by = request.user
                obj.closed_at = timezone.now()
            obj.save()
            write_audit_log(request.user, obj, "triage", tenant=request.tenant)
        messages.success(request, f"Complaint {obj.number} triage completed.")
    else:
        err_msg = "; ".join(f"{f}: {e[0]}" for f, e in form.errors.items())
        messages.error(request, f"Triage validation error: {err_msg}")
    return redirect("quality:customer_complaint_detail", pk=complaint.pk)


@login_required
@require_POST
def customer_complaint_close(request, pk):
    complaint = quality_object(request, CustomerComplaint, pk)
    if complaint.status in ["closed", "cancelled"]:
        messages.error(request, f"Complaint {complaint.number} is already closed.")
        return redirect("quality:customer_complaint_detail", pk=complaint.pk)

    if complaint.has_active_regulatory_report:
        messages.error(request, f"Complaint {complaint.number} cannot be closed while active regulatory reports are pending.")
        return redirect("quality:customer_complaint_detail", pk=complaint.pk)

    if complaint.investigations.filter(status__in=["pending_assignment", "in_progress", "dhr_review", "hhe_review"]).exists():
        messages.error(request, f"Complaint {complaint.number} cannot be closed with unresolved investigations.")
        return redirect("quality:customer_complaint_detail", pk=complaint.pk)

    resolution_summary = request.POST.get("resolution_summary", "").strip()
    customer_letter_sent = request.POST.get("customer_letter_sent") == "on"

    with transaction.atomic():
        if resolution_summary:
            complaint.resolution_summary = resolution_summary
        complaint.customer_letter_sent = customer_letter_sent
        if customer_letter_sent and not complaint.customer_letter_date:
            complaint.customer_letter_date = timezone.now().date()
        complaint.status = "closed"
        complaint.closed_by = request.user
        complaint.closed_at = timezone.now()
        complaint.save()
        write_audit_log(request.user, complaint, "close", tenant=request.tenant)

    messages.success(request, f"Complaint {complaint.number} is now closed.")
    return redirect("quality:customer_complaint_detail", pk=complaint.pk)


@login_required
def customer_complaint_export_csv(request):
    qs = quality_scope(CustomerComplaint.objects.all(), request).select_related(
        "customer", "assigned_to", "sales_order"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="customer_complaints.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Complaint #",
        "Title",
        "Status",
        "Severity",
        "Validity",
        "Reportability",
        "Intake Channel",
        "Customer",
        "Complainant Name",
        "Item Code",
        "Item Name",
        "Lot #",
        "Serial #",
        "Date Received",
        "Days Open",
        "Assigned To",
    ])

    for c in qs.iterator():
        writer.writerow([
            _csv_safe(c.number),
            _csv_safe(c.title),
            _csv_safe(c.get_status_display()),
            _csv_safe(c.get_severity_display()),
            _csv_safe(c.get_validity_display()),
            _csv_safe(c.get_reportability_display()),
            _csv_safe(c.get_intake_channel_display()),
            _csv_safe(c.customer.name if c.customer else ""),
            _csv_safe(c.complainant_name),
            _csv_safe(c.item_code),
            _csv_safe(c.item_name),
            _csv_safe(c.lot_number),
            _csv_safe(c.serial_number),
            _csv_safe(c.date_received),
            _csv_safe(c.days_open),
            _csv_safe(c.assigned_to.get_full_name() or c.assigned_to.username if c.assigned_to else ""),
        ])

    return response
