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
from apps.quality.forms.CustomerComplaints.ComplaintInvestigations import ComplaintInvestigationForm
from apps.quality.models.CustomerComplaints.ComplaintInvestigations import ComplaintInvestigation
from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def complaint_investigation_list(request):
    qs = quality_scope(ComplaintInvestigation.objects.all(), request).select_related(
        "complaint", "lead_investigator", "qa_approved_by", "capa", "ncr", "risk_assessment"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(complaint__number__icontains=q)
            | Q(complaint__title__icontains=q)
            | Q(dhr_lot_number__icontains=q)
            | Q(sample_testing_findings__icontains=q)
            | Q(root_cause_narrative__icontains=q)
            | Q(investigation_conclusion__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    method_filter = request.GET.get("analytical_method", "").strip()
    if method_filter:
        qs = qs.filter(analytical_method=method_filter)

    root_cause_filter = request.GET.get("root_cause_category", "").strip()
    if root_cause_filter:
        qs = qs.filter(root_cause_category=root_cause_filter)

    complaint_filter = request.GET.get("complaint", "").strip()
    if complaint_filter and complaint_filter.isdigit():
        qs = qs.filter(complaint_id=int(complaint_filter))

    total_count = qs.count()

    base_tenant_qs = ComplaintInvestigation.objects.filter(tenant=request.tenant)
    in_progress_count = base_tenant_qs.filter(status__in=["in_progress", "hhe_review", "pending_qa_review"]).count()
    capa_triggered_count = base_tenant_qs.filter(capa_required=True).count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "investigations": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "in_progress_count": in_progress_count,
        "capa_triggered_count": capa_triggered_count,
        "status_choices": ComplaintInvestigation.INVESTIGATION_STATUS_CHOICES,
        "analytical_method_choices": ComplaintInvestigation.ANALYTICAL_METHOD_CHOICES,
        "root_cause_category_choices": ComplaintInvestigation.ROOT_CAUSE_CATEGORY_CHOICES,
    }
    return render(
        request,
        "quality/customercomplaints/complaint_investigation/list.html",
        context,
    )


@login_required
def complaint_investigation_detail(request, pk):
    investigation = quality_object(
        request,
        ComplaintInvestigation,
        pk,
        select_related=(
            "complaint",
            "complaint__customer",
            "lead_investigator",
            "qa_approved_by",
            "risk_assessment",
            "capa",
            "ncr",
        ),
    )
    return render(
        request,
        "quality/customercomplaints/complaint_investigation/detail.html",
        {"investigation": investigation},
    )


@login_required
def complaint_investigation_create(request):
    initial = {"status": "assigned", "analytical_method": "visual_microscopy"}
    complaint_pk = request.GET.get("complaint", "").strip()
    if complaint_pk and complaint_pk.isdigit():
        complaint = get_object_or_404(CustomerComplaint, pk=int(complaint_pk), tenant=request.tenant)
        initial["complaint"] = complaint
        initial["dhr_lot_number"] = complaint.lot_number

    if request.method == "POST":
        form = ComplaintInvestigationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                investigation = form.save(commit=False)
                investigation.tenant = request.tenant
                investigation.save()
                # If complaint status was intake, move to under investigation
                c = investigation.complaint
                if c.status in ["intake_received", "under_triage"]:
                    c.status = "under_investigation"
                    c.save(update_fields=["status", "updated_at"])
                write_audit_log(request.user, investigation, "create", tenant=request.tenant)
            messages.success(request, f"Investigation {investigation.number} created.")
            return redirect("quality:complaint_investigation_detail", pk=investigation.pk)
    else:
        form = ComplaintInvestigationForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "quality/customercomplaints/complaint_investigation/form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def complaint_investigation_edit(request, pk):
    investigation = quality_object(request, ComplaintInvestigation, pk)

    if request.method == "POST":
        form = ComplaintInvestigationForm(request.POST, instance=investigation, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                investigation = form.save()
                write_audit_log(request.user, investigation, "update", tenant=request.tenant)
            messages.success(request, f"Investigation {investigation.number} updated.")
            return redirect("quality:complaint_investigation_detail", pk=investigation.pk)
    else:
        form = ComplaintInvestigationForm(instance=investigation, tenant=request.tenant)

    return render(
        request,
        "quality/customercomplaints/complaint_investigation/form.html",
        {"form": form, "investigation": investigation, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def complaint_investigation_delete(request, pk):
    investigation = quality_object(request, ComplaintInvestigation, pk)
    number = investigation.number
    complaint_pk = investigation.complaint_id
    with transaction.atomic():
        write_audit_log(request.user, investigation, "delete", tenant=request.tenant)
        investigation.delete()
    messages.success(request, f"Investigation {number} deleted.")
    return redirect("quality:customer_complaint_detail", pk=complaint_pk)


@login_required
@require_POST
def complaint_investigation_complete(request, pk):
    investigation = quality_object(request, ComplaintInvestigation, pk)
    action_type = request.POST.get("action_type", "approve")

    with transaction.atomic():
        if action_type == "approve":
            investigation.status = "approved"
            investigation.qa_approved_by = request.user
            investigation.qa_approved_date = timezone.now().date()
            if not investigation.actual_completion_date:
                investigation.actual_completion_date = timezone.now().date()
            investigation.save()
            write_audit_log(request.user, investigation, "complete", tenant=request.tenant)
            messages.success(request, f"Investigation {investigation.number} approved and marked complete.")
        else:
            investigation.status = "rejected_rework"
            investigation.save()
            write_audit_log(request.user, investigation, "update", tenant=request.tenant)
            messages.warning(request, f"Investigation {investigation.number} returned for engineering rework.")

    return redirect("quality:complaint_investigation_detail", pk=investigation.pk)


@login_required
def complaint_investigation_export_csv(request):
    qs = quality_scope(ComplaintInvestigation.objects.all(), request).select_related(
        "complaint", "lead_investigator", "qa_approved_by"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="complaint_investigations.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Investigation #",
        "Complaint #",
        "Status",
        "Lead Investigator",
        "DHR Reviewed",
        "DHR Lot #",
        "Analytical Method",
        "Sample Tested",
        "Failure Reproduced",
        "Root Cause Category",
        "CAPA Required",
        "Target Date",
        "Actual Date",
    ])

    for inv in qs.iterator():
        writer.writerow([
            _csv_safe(inv.number),
            _csv_safe(inv.complaint.number if inv.complaint else ""),
            _csv_safe(inv.get_status_display()),
            _csv_safe(inv.lead_investigator.get_full_name() or inv.lead_investigator.username if inv.lead_investigator else ""),
            _csv_safe("Yes" if inv.dhr_reviewed else "No"),
            _csv_safe(inv.dhr_lot_number),
            _csv_safe(inv.get_analytical_method_display()),
            _csv_safe("Yes" if inv.physical_sample_examined else "No"),
            _csv_safe("Yes" if inv.failure_reproduced else "No"),
            _csv_safe(inv.get_root_cause_category_display()),
            _csv_safe("Yes" if inv.capa_required else "No"),
            _csv_safe(inv.target_completion_date),
            _csv_safe(inv.actual_completion_date),
        ])

    return response
