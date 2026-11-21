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
from apps.quality.forms.RegulatorySubmissions.PostMarketSurveillanceReports import PostMarketSurveillanceReportForm
from apps.quality.models.RegulatorySubmissions.PostMarketSurveillanceReports import PostMarketSurveillanceReport
from apps.quality.models.RegulatorySubmissions.ProductRegistrations import ProductRegistration
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def post_market_surveillance_report_list(request):
    qs = quality_scope(
        PostMarketSurveillanceReport.objects.all(),
        request,
    ).select_related("product_registration", "prepared_by", "approved_by")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(report_title__icontains=q)
            | Q(number__icontains=q)
            | Q(device_model_family__icontains=q)
            | Q(benefit_risk_rationale__icontains=q)
        )

    report_type = request.GET.get("report_type", "").strip()
    if report_type:
        qs = qs.filter(report_type=report_type)

    benefit_risk_conclusion = request.GET.get("benefit_risk_conclusion", "").strip()
    if benefit_risk_conclusion:
        qs = qs.filter(benefit_risk_conclusion=benefit_risk_conclusion)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    product_registration_id = request.GET.get("product_registration", "").strip()
    if product_registration_id.isdigit():
        qs = qs.filter(product_registration_id=int(product_registration_id))

    total_reports = qs.count()
    approved_count = qs.filter(status__in=["approved", "submitted_to_authority"]).count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    registrations = ProductRegistration.objects.filter(tenant=request.tenant).order_by("product_name")

    context = {
        "page_obj": page_obj,
        "post_market_surveillance_reports": page_obj.object_list,
        "report_type_choices": PostMarketSurveillanceReport.REPORT_TYPE_CHOICES,
        "benefit_risk_choices": PostMarketSurveillanceReport.BENEFIT_RISK_CHOICES,
        "status_choices": PostMarketSurveillanceReport.STATUS_CHOICES,
        "registrations": registrations,
        "total_reports": total_reports,
        "approved_count": approved_count,
        "search_query": q,
    }
    return render(
        request,
        "quality/regulatory_submissions/post_market_surveillance_report/list.html",
        context,
    )


@login_required
def post_market_surveillance_report_detail(request, pk):
    report = quality_object(
        request,
        PostMarketSurveillanceReport,
        pk,
        select_related=("product_registration", "prepared_by", "approved_by"),
    )

    context = {
        "post_market_surveillance_report": report,
    }
    return render(
        request,
        "quality/regulatory_submissions/post_market_surveillance_report/detail.html",
        context,
    )


@login_required
def post_market_surveillance_report_create(request):
    initial_data = {}
    reg_id = request.GET.get("registration")
    if reg_id and reg_id.isdigit():
        reg = ProductRegistration.objects.filter(tenant=request.tenant, pk=int(reg_id)).first()
        if reg:
            initial_data["product_registration"] = reg
            initial_data["device_model_family"] = reg.product_name
            initial_data["report_title"] = f"Periodic Safety Update Report — {reg.product_name}"

    if request.method == "POST":
        form = PostMarketSurveillanceReportForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Post-Market Surveillance Report {obj.number} created successfully.")
            return redirect("quality:post_market_surveillance_report_detail", pk=obj.pk)
    else:
        form = PostMarketSurveillanceReportForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(
        request,
        "quality/regulatory_submissions/post_market_surveillance_report/form.html",
        context,
    )


@login_required
def post_market_surveillance_report_edit(request, pk):
    report = quality_object(request, PostMarketSurveillanceReport, pk)
    if request.method == "POST":
        form = PostMarketSurveillanceReportForm(request.POST, instance=report, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Post-Market Surveillance Report {obj.number} updated successfully.")
            return redirect("quality:post_market_surveillance_report_detail", pk=obj.pk)
    else:
        form = PostMarketSurveillanceReportForm(instance=report, tenant=request.tenant)

    context = {
        "form": form,
        "post_market_surveillance_report": report,
        "is_edit": True,
    }
    return render(
        request,
        "quality/regulatory_submissions/post_market_surveillance_report/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def post_market_surveillance_report_delete(request, pk):
    report = quality_object(request, PostMarketSurveillanceReport, pk)
    num = report.number
    write_audit_log(request.user, report, "delete", tenant=request.tenant)
    report.delete()
    messages.success(request, f"Post-Market Surveillance Report {num} was deleted.")
    return redirect("quality:post_market_surveillance_report_list")


@login_required
def post_market_surveillance_report_export(request):
    qs = (
        quality_scope(PostMarketSurveillanceReport.objects.all(), request)
        .defer("benefit_risk_rationale", "pmcf_action_summary", "notes")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="post_market_surveillance_reports.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Report Number",
        "Title",
        "Report Type",
        "Device Family",
        "Period Start",
        "Period End",
        "Units Distributed",
        "Complaints Count",
        "Complaint Rate %",
        "Serious Incidents",
        "Incident Rate %",
        "Field Actions",
        "Benefit-Risk Conclusion",
        "Status",
        "Next Due Date",
    ])

    for item in qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.report_title),
            _csv_safe(item.get_report_type_display()),
            _csv_safe(item.device_model_family),
            _csv_safe(item.reporting_period_start),
            _csv_safe(item.reporting_period_end),
            _csv_safe(item.units_distributed),
            _csv_safe(item.total_complaints_count),
            _csv_safe(item.complaint_rate_pct),
            _csv_safe(item.serious_incidents_count),
            _csv_safe(item.serious_incident_rate_pct),
            _csv_safe(item.field_actions_count),
            _csv_safe(item.get_benefit_risk_conclusion_display()),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.next_report_due_date),
        ])

    return response
