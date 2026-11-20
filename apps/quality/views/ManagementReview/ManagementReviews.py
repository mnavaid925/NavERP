import csv

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.quality.forms.ManagementReview.ManagementReviews import (
    ManagementReviewApproveForm,
    ManagementReviewForm,
    ManagementReviewMinutesForm,
)
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord
from apps.quality.models.ManagementReview.ManagementReviews import ManagementReview
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

User = get_user_model()
PAGE_SIZE = 15


@login_required
def management_review_list(request):
    qs = quality_scope(ManagementReview.objects.all(), request).select_related(
        "executive_sponsor", "lead_facilitator", "org_unit"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(location__icontains=q)
            | Q(executive_summary__icontains=q)
        )

    cadence_filter = request.GET.get("cadence", "").strip()
    if cadence_filter:
        qs = qs.filter(cadence=cadence_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    suitability_filter = request.GET.get("suitability", "").strip()
    if suitability_filter:
        qs = qs.filter(qms_suitability_conclusion=suitability_filter)

    org_unit_filter = request.GET.get("org_unit", "").strip()
    if org_unit_filter and org_unit_filter.isdigit():
        qs = qs.filter(org_unit_id=int(org_unit_filter))

    total_count = qs.count()

    base_tenant_qs = ManagementReview.objects.filter(tenant=request.tenant)
    stats = base_tenant_qs.aggregate(
        scheduled_count=Count("id", filter=Q(status="scheduled")),
        active_count=Count("id", filter=Q(status__in=["in_preparation", "meeting_active", "minutes_drafting", "pending_approval"])),
        approved_count=Count("id", filter=Q(status="approved")),
    )
    scheduled_count = stats["scheduled_count"]
    active_count = stats["active_count"]
    approved_count = stats["approved_count"]

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    filter_querystring = query_params.urlencode()

    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "reviews": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "filter_querystring": filter_querystring,
        "total_count": total_count,
        "scheduled_count": scheduled_count,
        "active_count": active_count,
        "approved_count": approved_count,
        "cadence_choices": ManagementReview.CADENCE_CHOICES,
        "status_choices": ManagementReview.STATUS_CHOICES,
        "suitability_choices": ManagementReview.SUITABILITY_CHOICES,
        "org_units": org_units,
        "q": q,
        "selected_cadence": cadence_filter,
        "selected_status": status_filter,
        "selected_suitability": suitability_filter,
        "selected_org_unit": org_unit_filter,
    }
    return render(request, "quality/managementreview/management_review/list.html", context)


@login_required
def management_review_detail(request, pk):
    review = quality_object(
        request,
        ManagementReview,
        pk,
        select_related=("executive_sponsor", "lead_facilitator", "org_unit", "approved_by", "electronic_signature"),
    )

    inputs = review.inputs.select_related("presenter", "linked_audit", "linked_capa", "linked_complaint", "linked_ncr").order_by("agenda_order", "id")
    actions = review.actions.select_related("assignee", "verified_by", "spawned_capa", "spawned_change_order").order_by("due_date", "id")
    open_actions = actions.filter(status__in=["open", "in_progress", "pending_verification"])

    approve_form = ManagementReviewApproveForm()

    can_start = review.status in ["scheduled", "in_preparation"]
    can_draft_minutes = review.status in ["meeting_active", "minutes_drafting", "pending_approval"]
    can_approve = review.status == "pending_approval" or (review.status in ["meeting_active", "minutes_drafting"] and review.qms_suitability_conclusion != "pending")
    can_cancel = review.status not in ["approved", "cancelled"]

    context = {
        "review": review,
        "inputs": inputs,
        "actions": actions,
        "open_actions": open_actions,
        "approve_form": approve_form,
        "can_start": can_start,
        "can_draft_minutes": can_draft_minutes,
        "can_approve": can_approve,
        "can_cancel": can_cancel,
    }
    return render(request, "quality/managementreview/management_review/detail.html", context)


@login_required
def management_review_create(request):
    if request.method == "POST":
        form = ManagementReviewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.status = "scheduled"
                obj.save()
                write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Management Review {obj.number} scheduled successfully.")
            return redirect("quality:management_review_detail", pk=obj.pk)
    else:
        initial = {
            "period_start": timezone.now().date().replace(month=1, day=1),
            "period_end": timezone.now().date(),
            "scheduled_date": timezone.now().date(),
        }
        form = ManagementReviewForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "review": None,
        "is_edit": False,
    }
    return render(request, "quality/managementreview/management_review/form.html", context)


@login_required
def management_review_edit(request, pk):
    review = quality_object(request, ManagementReview, pk)
    if review.status in ["approved", "cancelled"]:
        messages.error(request, f"Review {review.number} cannot be edited because it is {review.get_status_display().lower()}.")
        return redirect("quality:management_review_detail", pk=review.pk)

    if request.method == "POST":
        form = ManagementReviewForm(request.POST, instance=review, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save()
                write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Management Review {obj.number} updated successfully.")
            return redirect("quality:management_review_detail", pk=obj.pk)
    else:
        form = ManagementReviewForm(instance=review, tenant=request.tenant)

    context = {
        "form": form,
        "review": review,
        "is_edit": True,
    }
    return render(request, "quality/managementreview/management_review/form.html", context)


@login_required
@require_POST
def management_review_delete(request, pk):
    review = quality_object(request, ManagementReview, pk)
    if review.status == "approved":
        messages.error(request, "Approved executive management reviews cannot be deleted due to regulatory compliance.")
        return redirect("quality:management_review_detail", pk=review.pk)

    number = review.number
    with transaction.atomic():
        write_audit_log(request.user, review, "delete", tenant=request.tenant)
        review.delete()
    messages.success(request, f"Management Review {number} has been deleted.")
    return redirect("quality:management_review_list")


@login_required
@require_POST
def management_review_start(request, pk):
    review = quality_object(request, ManagementReview, pk)
    if review.status not in ["scheduled", "in_preparation"]:
        messages.warning(request, f"Review {review.number} is already {review.get_status_display().lower()}.")
        return redirect("quality:management_review_detail", pk=review.pk)

    with transaction.atomic():
        review.status = "meeting_active"
        if not review.actual_meeting_date:
            review.actual_meeting_date = timezone.now().date()
        review.save()
        write_audit_log(request.user, review, "start", tenant=request.tenant)

    messages.success(request, f"Management Review {review.number} is now marked In Progress.")
    return redirect("quality:management_review_detail", pk=review.pk)


@login_required
def management_review_draft_minutes(request, pk):
    review = quality_object(request, ManagementReview, pk)
    if review.status in ["approved", "cancelled"]:
        messages.error(request, f"Cannot edit minutes of a {review.get_status_display().lower()} review.")
        return redirect("quality:management_review_detail", pk=review.pk)

    if request.method == "POST":
        form = ManagementReviewMinutesForm(request.POST, instance=review)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                if obj.qms_suitability_conclusion != "pending":
                    obj.status = "pending_approval"
                else:
                    obj.status = "minutes_drafting"
                obj.save()
                write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Minutes and decisions for {obj.number} saved successfully.")
            return redirect("quality:management_review_detail", pk=obj.pk)
    else:
        form = ManagementReviewMinutesForm(instance=review)

    context = {
        "form": form,
        "review": review,
    }
    return render(request, "quality/managementreview/management_review/minutes_form.html", context)


@login_required
@require_POST
def management_review_approve(request, pk):
    review = quality_object(request, ManagementReview, pk)
    if review.status == "approved":
        messages.info(request, f"Review {review.number} is already approved.")
        return redirect("quality:management_review_detail", pk=review.pk)

    if review.qms_suitability_conclusion == "pending":
        messages.error(request, "Cannot approve review before an executive QMS suitability conclusion is recorded.")
        return redirect("quality:management_review_detail", pk=review.pk)

    form = ManagementReviewApproveForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            # Create digital signature record if supported
            doc = ControlledDocument.objects.filter(tenant=request.tenant).first()
            if not doc:
                doc = ControlledDocument.objects.create(
                    tenant=request.tenant,
                    title="Management Review Governance Charter",
                    document_type="policy",
                    owner=request.user,
                    revision="1.0",
                    lifecycle_state="approved",
                    description="Master governance record for executive management reviews.",
                )

            sig_record = ElectronicSignatureRecord.objects.create(
                tenant=request.tenant,
                document=doc,
                document_revision=doc.revision or "1.0",
                signer=request.user,
                signer_name=request.user.get_full_name() or request.user.username,
                signer_title="Management with Executive Responsibility",
                signature_meaning="management_approval",
                comments=form.cleaned_data.get("comment", "") or "Executive Management Review Sign-off",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            review.status = "approved"
            review.approved_by = request.user
            review.approved_at = timezone.now()
            review.electronic_signature = sig_record
            review.save()
            write_audit_log(request.user, review, "approve", tenant=request.tenant)
            write_audit_log(request.user, sig_record, "create", tenant=request.tenant)

        messages.success(request, f"Management Review {review.number} has been formally approved and closed.")
    else:
        messages.error(request, "Please confirm the executive suitability endorsement certification.")

    return redirect("quality:management_review_detail", pk=review.pk)


@login_required
@require_POST
def management_review_cancel(request, pk):
    review = quality_object(request, ManagementReview, pk)
    if review.status == "approved":
        messages.error(request, "Approved reviews cannot be cancelled.")
        return redirect("quality:management_review_detail", pk=review.pk)

    with transaction.atomic():
        review.status = "cancelled"
        review.save()
        write_audit_log(request.user, review, "cancel", tenant=request.tenant)

    messages.info(request, f"Management Review {review.number} has been cancelled.")
    return redirect("quality:management_review_detail", pk=review.pk)


@login_required
def management_review_export_csv(request):
    qs = quality_scope(ManagementReview.objects.all(), request).select_related(
        "executive_sponsor", "lead_facilitator", "org_unit"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="management_reviews.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Review Number",
        "Title",
        "Cadence",
        "Scheduled Date",
        "Actual Meeting Date",
        "Status",
        "QMS Suitability Conclusion",
        "Executive Sponsor",
        "Lead Facilitator",
        "Org Unit",
        "Quorum Met",
        "Inputs Count",
        "Actions Count",
    ])

    for r in qs:
        writer.writerow([
            _csv_safe(r.number),
            _csv_safe(r.title),
            _csv_safe(r.get_cadence_display()),
            _csv_safe(r.scheduled_date),
            _csv_safe(r.actual_meeting_date),
            _csv_safe(r.get_status_display()),
            _csv_safe(r.get_qms_suitability_conclusion_display()),
            _csv_safe(r.executive_sponsor.get_full_name() or r.executive_sponsor.username if r.executive_sponsor else ""),
            _csv_safe(r.lead_facilitator.get_full_name() or r.lead_facilitator.username if r.lead_facilitator else ""),
            _csv_safe(r.org_unit.name if r.org_unit else ""),
            _csv_safe("Yes" if r.quorum_met else "No"),
            _csv_safe(r.total_inputs_count),
            _csv_safe(r.total_actions_count),
        ])

    return response


@login_required
def management_review_export_pdf(request, pk):
    """Audit-ready printable / dossier summary view for FDA / ISO inspections."""
    review = quality_object(
        request,
        ManagementReview,
        pk,
        select_related=("executive_sponsor", "lead_facilitator", "org_unit", "approved_by", "electronic_signature"),
    )
    inputs = review.inputs.select_related("presenter").order_by("agenda_order")
    actions = review.actions.select_related("assignee", "verified_by").order_by("due_date")

    context = {
        "review": review,
        "inputs": inputs,
        "actions": actions,
        "export_date": timezone.now(),
    }
    return render(request, "quality/managementreview/management_review/dossier.html", context)
