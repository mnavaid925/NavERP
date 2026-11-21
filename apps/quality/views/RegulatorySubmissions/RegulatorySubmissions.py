import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.quality.forms.RegulatorySubmissions.RegulatorySubmissions import RegulatorySubmissionForm
from apps.quality.models.RegulatorySubmissions.RegulatorySubmissions import RegulatorySubmission
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def regulatory_submission_list(request):
    qs = quality_scope(
        RegulatorySubmission.objects.all(),
        request,
    ).select_related("target_authority", "org_unit", "lead_author", "qa_approver")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(product_name__icontains=q)
            | Q(product_code__icontains=q)
            | Q(application_number__icontains=q)
        )

    submission_type = request.GET.get("submission_type", "").strip()
    if submission_type:
        qs = qs.filter(submission_type=submission_type)

    device_class = request.GET.get("device_class", "").strip()
    if device_class:
        qs = qs.filter(device_class=device_class)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    target_authority_id = request.GET.get("target_authority", "").strip()
    if target_authority_id.isdigit():
        qs = qs.filter(target_authority_id=int(target_authority_id))

    total_submissions = qs.count()
    pending_review_count = qs.filter(
        status__in=["authoring", "internal_review", "under_review", "deficiency_response"]
    ).count()
    approved_count = qs.filter(status="approved_cleared").count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    target_authorities = Party.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "regulatory_submissions": page_obj.object_list,
        "submission_type_choices": RegulatorySubmission.SUBMISSION_TYPE_CHOICES,
        "device_class_choices": RegulatorySubmission.DEVICE_CLASS_CHOICES,
        "status_choices": RegulatorySubmission.STATUS_CHOICES,
        "target_authorities": target_authorities,
        "total_submissions": total_submissions,
        "pending_review_count": pending_review_count,
        "approved_count": approved_count,
        "search_query": q,
    }
    return render(
        request,
        "quality/regulatory_submissions/regulatory_submission/list.html",
        context,
    )


@login_required
def regulatory_submission_detail(request, pk):
    submission = quality_object(
        request,
        RegulatorySubmission,
        pk,
        select_related=("target_authority", "org_unit", "lead_author", "qa_approver", "technical_dossier"),
    )
    linked_commitments = submission.regulatory_commitments.all().order_by("due_date")
    linked_registrations = submission.product_registrations.all().order_by("product_name")

    context = {
        "regulatory_submission": submission,
        "linked_commitments": linked_commitments,
        "linked_registrations": linked_registrations,
    }
    return render(
        request,
        "quality/regulatory_submissions/regulatory_submission/detail.html",
        context,
    )


@login_required
def regulatory_submission_create(request):
    if request.method == "POST":
        form = RegulatorySubmissionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Regulatory Submission {obj.number} created successfully.")
            return redirect("quality:regulatory_submission_detail", pk=obj.pk)
    else:
        form = RegulatorySubmissionForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(
        request,
        "quality/regulatory_submissions/regulatory_submission/form.html",
        context,
    )


@login_required
def regulatory_submission_edit(request, pk):
    submission = quality_object(request, RegulatorySubmission, pk)
    if request.method == "POST":
        form = RegulatorySubmissionForm(request.POST, instance=submission, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Regulatory Submission {obj.number} updated successfully.")
            return redirect("quality:regulatory_submission_detail", pk=obj.pk)
    else:
        form = RegulatorySubmissionForm(instance=submission, tenant=request.tenant)

    context = {
        "form": form,
        "regulatory_submission": submission,
        "is_edit": True,
    }
    return render(
        request,
        "quality/regulatory_submissions/regulatory_submission/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def regulatory_submission_delete(request, pk):
    submission = quality_object(request, RegulatorySubmission, pk)
    num = submission.number
    write_audit_log(request.user, submission, "delete", tenant=request.tenant)
    submission.delete()
    messages.success(request, f"Regulatory Submission {num} was deleted.")
    return redirect("quality:regulatory_submission_list")


@login_required
def regulatory_submission_export(request):
    qs = (
        quality_scope(RegulatorySubmission.objects.all(), request)
        .select_related("target_authority", "lead_author")
        .defer("technical_sections_summary", "notes")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="regulatory_submissions.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Submission Number",
        "Title",
        "Submission Type",
        "Target Authority",
        "Product Name",
        "Product Code",
        "Device Class",
        "Application Number",
        "Status",
        "Planned Submission Date",
        "Actual Submission Date",
        "Decision Date",
        "Lead Author",
        "Days Under Review",
    ])

    for item in qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.get_submission_type_display()),
            _csv_safe(item.target_authority.name if item.target_authority else ""),
            _csv_safe(item.product_name),
            _csv_safe(item.product_code),
            _csv_safe(item.get_device_class_display()),
            _csv_safe(item.application_number),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.planned_submission_date),
            _csv_safe(item.actual_submission_date),
            _csv_safe(item.decision_date),
            _csv_safe(item.lead_author.get_full_name() if item.lead_author else ""),
            _csv_safe(item.days_under_review),
        ])

    return response
