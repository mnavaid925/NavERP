import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.RiskManagement.RiskReviewRecords import RiskReviewRecordForm
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan
from apps.quality.models.RiskManagement.RiskReviewRecords import RiskReviewRecord
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "%")):
        return f"'{text}"
    return text


@login_required
def risk_review_record_list(request):
    qs = quality_scope(RiskReviewRecord.objects.all(), request).select_related(
        "plan", "lead_reviewer", "approved_signature"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(review_title__icontains=q)
            | Q(findings_summary__icontains=q)
        )

    selected_type = request.GET.get("review_type", "").strip()
    if selected_type:
        qs = qs.filter(review_type=selected_type)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_plan = request.GET.get("plan", "").strip()
    if selected_plan and selected_plan.isdigit():
        qs = qs.filter(plan_id=int(selected_plan))

    base_qs = quality_scope(RiskReviewRecord.objects.all(), request)
    counts = base_qs.aggregate(
        total_count=Count("id"),
        approved_count=Count("id", filter=Q(status="approved")),
        pms_count=Count("id", filter=Q(review_type="post_market_surveillance")),
        draft_count=Count("id", filter=Q(status="draft")),
    )
    total_count = counts["total_count"] or 0
    approved_count = counts["approved_count"] or 0
    pms_count = counts["pms_count"] or 0
    draft_count = counts["draft_count"] or 0

    plans = quality_scope(RiskManagementPlan.objects.all(), request).only("id", "number", "title").order_by("number")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "quality/riskmanagement/risk_review_record/list.html",
        {
            "review_records": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "approved_count": approved_count,
            "pms_count": pms_count,
            "draft_count": draft_count,
            "review_type_choices": RiskReviewRecord.REVIEW_TYPE_CHOICES,
            "status_choices": RiskReviewRecord.STATUS_CHOICES,
            "plans": plans,
            "selected_type": selected_type,
            "selected_status": selected_status,
            "selected_plan": selected_plan,
            "q": q,
        },
    )


@login_required
def risk_review_record_detail(request, pk):
    review_record = quality_object(
        request,
        RiskReviewRecord,
        pk,
        select_related=("plan", "lead_reviewer", "approved_signature"),
    )

    return render(
        request,
        "quality/riskmanagement/risk_review_record/detail.html",
        {
            "review_record": review_record,
        },
    )


@login_required
def risk_review_record_create(request):
    initial = {}
    plan_param = request.GET.get("plan", "").strip()
    if plan_param and plan_param.isdigit():
        initial["plan"] = int(plan_param)

    if request.method == "POST":
        form = RiskReviewRecordForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            review = form.save(commit=False)
            review.tenant = request.tenant
            review.save()
            write_audit_log(request.user, review, "create", tenant=request.tenant)
            messages.success(request, f"Risk Review Record {review.number} logged successfully.")
            return redirect("quality:risk_review_record_detail", pk=review.pk)
    else:
        form = RiskReviewRecordForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "quality/riskmanagement/risk_review_record/form.html",
        {
            "form": form,
            "review_record": None,
            "is_edit": False,
        },
    )


@login_required
def risk_review_record_edit(request, pk):
    review_record = quality_object(request, RiskReviewRecord, pk)
    if review_record.status == "approved" or review_record.approved_signature_id:
        messages.error(
            request,
            f"Risk Review Record {review_record.number} cannot be modified because it is already approved or signed.",
        )
        return redirect("quality:risk_review_record_detail", pk=review_record.pk)

    if request.method == "POST":
        form = RiskReviewRecordForm(request.POST, instance=review_record, tenant=request.tenant)
        if form.is_valid():
            review_record = form.save()
            write_audit_log(request.user, review_record, "update", tenant=request.tenant)
            messages.success(request, f"Risk Review Record {review_record.number} updated successfully.")
            return redirect("quality:risk_review_record_detail", pk=review_record.pk)
    else:
        form = RiskReviewRecordForm(instance=review_record, tenant=request.tenant)

    return render(
        request,
        "quality/riskmanagement/risk_review_record/form.html",
        {
            "form": form,
            "review_record": review_record,
            "is_edit": True,
        },
    )


@require_POST
@login_required
@tenant_admin_required
def risk_review_record_delete(request, pk):
    review_record = quality_object(request, RiskReviewRecord, pk)
    number = review_record.number
    plan_id = review_record.plan_id
    write_audit_log(request.user, review_record, "delete", tenant=request.tenant)
    review_record.delete()
    messages.success(request, f"Risk Review Record {number} deleted successfully.")
    return redirect("quality:risk_management_plan_detail", pk=plan_id)


@require_POST
@login_required
@tenant_admin_required
def risk_review_record_approve(request, pk):
    review_record = quality_object(request, RiskReviewRecord, pk)
    review_record.status = "approved"
    review_record.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, review_record, "approve", tenant=request.tenant)
    messages.success(request, f"Risk Review Record {review_record.number} has been approved.")
    return redirect("quality:risk_review_record_detail", pk=review_record.pk)


@login_required
def risk_review_record_export(request):
    qs = quality_scope(RiskReviewRecord.objects.all(), request).select_related(
        "plan", "lead_reviewer"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="risk_review_records.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number",
        "Plan",
        "Review Title",
        "Review Type",
        "Review Date",
        "Lead Reviewer",
        "New Hazards Identified",
        "Risk Profile Changed",
        "Overall Residual Risk Reconfirmed",
        "Status",
        "Created At",
    ])

    for r in qs:
        writer.writerow([
            csv_safe(r.number),
            csv_safe(r.plan.number if r.plan else ""),
            csv_safe(r.review_title),
            csv_safe(r.get_review_type_display()),
            csv_safe(r.review_date),
            csv_safe(r.lead_reviewer.get_full_name() or r.lead_reviewer.username if r.lead_reviewer else ""),
            "Yes" if r.new_hazards_identified else "No",
            "Yes" if r.risk_profile_changed else "No",
            "Yes" if r.overall_residual_risk_reconfirmed else "No",
            csv_safe(r.get_status_display()),
            csv_safe(r.created_at.strftime("%Y-%m-%d")),
        ])

    return response
