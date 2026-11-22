from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.DataIntegrity.AuditTrailReviews import AuditTrailReviewForm
from apps.quality.models.DataIntegrity.AuditTrailReviews import AuditTrailReview
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 20


@login_required
def audit_trail_review_list(request):
    base_qs = quality_scope(
        AuditTrailReview.objects.all(),
        request,
    )

    stats = base_qs.aggregate(
        total=Count("id"),
        anomalies=Count("id", filter=Q(anomaly_severity__in=["major", "critical"])),
        completed=Count("id", filter=Q(status__in=["completed", "closed"])),
        clean=Count("id", filter=Q(disposition="approved_clean")),
    )
    total_count = stats["total"]
    anomaly_count = stats["anomalies"]
    completed_count = stats["completed"]
    clean_count = stats["clean"]

    qs = base_qs.select_related("system", "reviewer", "qa_approver")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(findings_summary__icontains=q)
        )

    type_selected = request.GET.get("review_type", "").strip()
    if type_selected:
        qs = qs.filter(review_type=type_selected)

    severity_selected = request.GET.get("severity", "").strip()
    if severity_selected:
        qs = qs.filter(anomaly_severity=severity_selected)

    status_selected = request.GET.get("status", "").strip()
    if status_selected:
        qs = qs.filter(status=status_selected)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "reviews": page_obj.object_list,
        "total_count": total_count,
        "anomaly_count": anomaly_count,
        "completed_count": completed_count,
        "clean_count": clean_count,
        "type_choices": AuditTrailReview.REVIEW_TYPE_CHOICES,
        "severity_choices": AuditTrailReview.SEVERITY_CHOICES,
        "status_choices": AuditTrailReview.STATUS_CHOICES,
        "q": q,
        "type_selected": type_selected,
        "severity_selected": severity_selected,
        "status_selected": status_selected,
    }
    return render(
        request,
        "quality/data_integrity/audit_trail_review/list.html",
        context,
    )


@login_required
def audit_trail_review_detail(request, pk):
    review = quality_object(
        request,
        AuditTrailReview,
        pk,
        select_related=("system", "reviewer", "qa_approver", "linked_ncr", "linked_capa"),
    )
    return render(
        request,
        "quality/data_integrity/audit_trail_review/detail.html",
        {"review": review},
    )


@login_required
def audit_trail_review_create(request):
    if request.method == "POST":
        form = AuditTrailReviewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                review = form.save(commit=False)
                review.tenant = request.tenant
                review.save()
                write_audit_log(request.user, review, "create", tenant=request.tenant)
            messages.success(request, f"Audit Trail Review {review.number} created successfully.")
            return redirect("quality:audit_trail_review_detail", pk=review.pk)
    else:
        form = AuditTrailReviewForm(tenant=request.tenant)

    return render(
        request,
        "quality/data_integrity/audit_trail_review/form.html",
        {"form": form, "review": None, "is_edit": False},
    )


@login_required
def audit_trail_review_edit(request, pk):
    review = quality_object(request, AuditTrailReview, pk)
    if request.method == "POST":
        form = AuditTrailReviewForm(request.POST, instance=review, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                review = form.save()
                write_audit_log(request.user, review, "update", tenant=request.tenant)
            messages.success(request, f"Audit Trail Review {review.number} updated successfully.")
            return redirect("quality:audit_trail_review_detail", pk=review.pk)
    else:
        form = AuditTrailReviewForm(instance=review, tenant=request.tenant)

    return render(
        request,
        "quality/data_integrity/audit_trail_review/form.html",
        {"form": form, "review": review, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def audit_trail_review_delete(request, pk):
    review = quality_object(request, AuditTrailReview, pk)
    num = review.number
    with transaction.atomic():
        write_audit_log(request.user, review, "delete", tenant=request.tenant)
        review.delete()
    messages.success(request, f"Audit Trail Review {num} deleted.")
    return redirect("quality:audit_trail_review_list")
