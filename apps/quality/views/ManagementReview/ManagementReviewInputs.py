import csv

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.ManagementReview.ManagementReviewInputs import ManagementReviewInputForm
from apps.quality.models.ManagementReview.ManagementReviewInputs import ManagementReviewInput
from apps.quality.models.ManagementReview.ManagementReviews import ManagementReview
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

User = get_user_model()
PAGE_SIZE = 15


@login_required
def management_review_input_list(request):
    qs = quality_scope(ManagementReviewInput.objects.all(), request).select_related(
        "management_review", "presenter", "linked_audit", "linked_capa", "linked_complaint", "linked_ncr"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(summary_findings__icontains=q)
            | Q(attachments_summary__icontains=q)
        )

    category_filter = request.GET.get("category", "").strip()
    if category_filter:
        qs = qs.filter(category=category_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    review_filter = request.GET.get("review", "").strip()
    if review_filter and review_filter.isdigit():
        qs = qs.filter(management_review_id=int(review_filter))

    presenter_filter = request.GET.get("presenter", "").strip()
    if presenter_filter and presenter_filter.isdigit():
        qs = qs.filter(presenter_id=int(presenter_filter))

    total_count = qs.count()

    base_tenant_qs = ManagementReviewInput.objects.filter(tenant=request.tenant)
    stats = base_tenant_qs.aggregate(
        compiled_count=Count("id", filter=Q(status="compiled")),
        presented_count=Count("id", filter=Q(status="presented")),
        accepted_count=Count("id", filter=Q(status="accepted")),
    )
    compiled_count = stats["compiled_count"]
    presented_count = stats["presented_count"]
    accepted_count = stats["accepted_count"]

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    filter_querystring = query_params.urlencode()

    reviews = ManagementReview.objects.filter(tenant=request.tenant).order_by("-scheduled_date")
    presenters = User.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "last_name", "username")

    context = {
        "inputs": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "filter_querystring": filter_querystring,
        "total_count": total_count,
        "compiled_count": compiled_count,
        "presented_count": presented_count,
        "accepted_count": accepted_count,
        "category_choices": ManagementReviewInput.CATEGORY_CHOICES,
        "status_choices": ManagementReviewInput.STATUS_CHOICES,
        "reviews": reviews,
        "presenters": presenters,
        "q": q,
        "selected_category": category_filter,
        "selected_status": status_filter,
        "selected_review": review_filter,
        "selected_presenter": presenter_filter,
    }
    return render(request, "quality/managementreview/management_review_input/list.html", context)


@login_required
def management_review_input_detail(request, pk):
    review_input = quality_object(
        request,
        ManagementReviewInput,
        pk,
        select_related=("management_review", "presenter", "linked_audit", "linked_capa", "linked_complaint", "linked_ncr"),
    )

    can_present = review_input.status in ["draft", "compiled"]
    can_accept = review_input.status in ["draft", "compiled", "presented"]

    context = {
        "review_input": review_input,
        "can_present": can_present,
        "can_accept": can_accept,
    }
    return render(request, "quality/managementreview/management_review_input/detail.html", context)


@login_required
def management_review_input_create(request):
    review_id = request.GET.get("review_id", "").strip()
    initial = {}
    parent_review = None
    if review_id and review_id.isdigit():
        parent_review = quality_object(request, ManagementReview, int(review_id))
        if parent_review.status in ["approved", "cancelled"]:
            messages.error(request, f"Cannot add inputs to a {parent_review.get_status_display().lower()} review.")
            return redirect("quality:management_review_detail", pk=parent_review.pk)
        initial["management_review"] = parent_review.pk
        initial["agenda_order"] = parent_review.inputs.count() + 1

    if request.method == "POST":
        form = ManagementReviewInputForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.management_review.status in ["approved", "cancelled"]:
                messages.error(request, f"Cannot add inputs to a {obj.management_review.get_status_display().lower()} review.")
                return redirect("quality:management_review_detail", pk=obj.management_review.pk)
            with transaction.atomic():
                obj.tenant = request.tenant
                obj.status = "compiled"
                obj.save()
                write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Review input {obj.number} created successfully.")
            return redirect("quality:management_review_detail", pk=obj.management_review.pk)
    else:
        form = ManagementReviewInputForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "review_input": None,
        "is_edit": False,
        "parent_review": parent_review,
    }
    return render(request, "quality/managementreview/management_review_input/form.html", context)


@login_required
def management_review_input_edit(request, pk):
    review_input = quality_object(request, ManagementReviewInput, pk, select_related=("management_review",))
    if review_input.management_review.status in ["approved", "cancelled"]:
        messages.error(request, f"Cannot edit inputs of a {review_input.management_review.get_status_display().lower()} review.")
        return redirect("quality:management_review_input_detail", pk=review_input.pk)

    if request.method == "POST":
        form = ManagementReviewInputForm(request.POST, instance=review_input, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save()
                write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Review input {obj.number} updated successfully.")
            return redirect("quality:management_review_input_detail", pk=obj.pk)
    else:
        form = ManagementReviewInputForm(instance=review_input, tenant=request.tenant)

    context = {
        "form": form,
        "review_input": review_input,
        "is_edit": True,
        "parent_review": review_input.management_review,
    }
    return render(request, "quality/managementreview/management_review_input/form.html", context)


@login_required
@require_POST
def management_review_input_delete(request, pk):
    review_input = quality_object(request, ManagementReviewInput, pk, select_related=("management_review",))
    if review_input.management_review.status in ["approved", "cancelled"]:
        messages.error(request, f"Cannot delete inputs of a {review_input.management_review.get_status_display().lower()} review.")
        return redirect("quality:management_review_detail", pk=review_input.management_review_id)

    parent_id = review_input.management_review_id
    number = review_input.number
    with transaction.atomic():
        write_audit_log(request.user, review_input, "delete", tenant=request.tenant)
        review_input.delete()
    messages.success(request, f"Review input {number} has been deleted.")
    return redirect("quality:management_review_detail", pk=parent_id)


@login_required
@require_POST
def management_review_input_present(request, pk):
    review_input = quality_object(request, ManagementReviewInput, pk, select_related=("management_review",))
    if review_input.management_review.status in ["approved", "cancelled"]:
        messages.error(request, f"Cannot alter inputs of a {review_input.management_review.get_status_display().lower()} review.")
        return redirect("quality:management_review_input_detail", pk=review_input.pk)

    with transaction.atomic():
        review_input.status = "presented"
        review_input.save()
        write_audit_log(request.user, review_input, "update", tenant=request.tenant)
    messages.success(request, f"Review input {review_input.number} marked as Presented.")
    return redirect("quality:management_review_input_detail", pk=review_input.pk)


@login_required
@require_POST
def management_review_input_accept(request, pk):
    review_input = quality_object(request, ManagementReviewInput, pk, select_related=("management_review",))
    if review_input.management_review.status in ["approved", "cancelled"]:
        messages.error(request, f"Cannot alter inputs of a {review_input.management_review.get_status_display().lower()} review.")
        return redirect("quality:management_review_input_detail", pk=review_input.pk)

    with transaction.atomic():
        review_input.status = "accepted"
        review_input.save()
        write_audit_log(request.user, review_input, "update", tenant=request.tenant)
    messages.success(request, f"Review input {review_input.number} marked as Accepted by Management.")
    return redirect("quality:management_review_input_detail", pk=review_input.pk)


@login_required
def management_review_input_export_csv(request):
    qs = quality_scope(ManagementReviewInput.objects.all(), request).select_related(
        "management_review", "presenter"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="management_review_inputs.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Input Number",
        "Review Session",
        "Agenda Order",
        "Topic Title",
        "Category",
        "Presenter",
        "Status",
        "Summary Findings",
        "Attachments Reference",
    ])

    for inp in qs:
        writer.writerow([
            _csv_safe(inp.number),
            _csv_safe(inp.management_review.number),
            _csv_safe(inp.agenda_order),
            _csv_safe(inp.title),
            _csv_safe(inp.get_category_display()),
            _csv_safe(inp.presenter.get_full_name() or inp.presenter.username if inp.presenter else ""),
            _csv_safe(inp.get_status_display()),
            _csv_safe(inp.summary_findings),
            _csv_safe(inp.attachments_summary),
        ])

    return response
