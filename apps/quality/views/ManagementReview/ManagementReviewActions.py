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

from apps.core.utils import write_audit_log
from apps.quality.forms.ManagementReview.ManagementReviewActions import (
    ManagementReviewActionCompleteForm,
    ManagementReviewActionForm,
    ManagementReviewActionVerifyForm,
)
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.ManagementReview.ManagementReviewActions import ManagementReviewAction
from apps.quality.models.ManagementReview.ManagementReviews import ManagementReview
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

User = get_user_model()
PAGE_SIZE = 15


@login_required
def management_review_action_list(request):
    qs = quality_scope(ManagementReviewAction.objects.all(), request).select_related(
        "management_review", "assignee", "verified_by", "spawned_capa", "spawned_change_order"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(resolution_summary__icontains=q)
        )

    type_filter = request.GET.get("action_type", "").strip()
    if type_filter:
        qs = qs.filter(action_type=type_filter)

    priority_filter = request.GET.get("priority", "").strip()
    if priority_filter:
        qs = qs.filter(priority=priority_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    review_filter = request.GET.get("review", "").strip()
    if review_filter and review_filter.isdigit():
        qs = qs.filter(management_review_id=int(review_filter))

    assignee_filter = request.GET.get("assignee", "").strip()
    if assignee_filter and assignee_filter.isdigit():
        qs = qs.filter(assignee_id=int(assignee_filter))

    today = timezone.now().date()
    base_tenant_qs = ManagementReviewAction.objects.filter(tenant=request.tenant)
    stats = base_tenant_qs.aggregate(
        open_count=Count("id", filter=Q(status__in=["open", "in_progress", "pending_verification"])),
        overdue_count=Count("id", filter=Q(status__in=["open", "in_progress", "pending_verification"], due_date__lt=today)),
        completed_count=Count("id", filter=Q(status="completed")),
    )
    open_count = stats["open_count"]
    overdue_count = stats["overdue_count"]
    completed_count = stats["completed_count"]

    paginator = Paginator(qs, PAGE_SIZE)
    total_count = paginator.count
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    filter_querystring = query_params.urlencode()

    reviews = ManagementReview.objects.filter(tenant=request.tenant).order_by("-scheduled_date")
    assignees = User.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "last_name", "username")

    context = {
        "actions": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "filter_querystring": filter_querystring,
        "total_count": total_count,
        "open_count": open_count,
        "overdue_count": overdue_count,
        "completed_count": completed_count,
        "action_type_choices": ManagementReviewAction.ACTION_TYPE_CHOICES,
        "priority_choices": ManagementReviewAction.PRIORITY_CHOICES,
        "status_choices": ManagementReviewAction.STATUS_CHOICES,
        "reviews": reviews,
        "assignees": assignees,
        "q": q,
        "selected_type": type_filter,
        "selected_priority": priority_filter,
        "selected_status": status_filter,
        "selected_review": review_filter,
        "selected_assignee": assignee_filter,
    }
    return render(request, "quality/managementreview/management_review_action/list.html", context)


@login_required
def management_review_action_detail(request, pk):
    action_item = quality_object(
        request,
        ManagementReviewAction,
        pk,
        select_related=("management_review", "assignee", "verified_by", "spawned_capa", "spawned_change_order"),
    )

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request.user, "is_staff", False)
    can_start = action_item.status == "open"
    can_complete = action_item.status in ["open", "in_progress"]
    can_verify = action_item.status == "pending_verification" and (action_item.assignee_id != request.user.id or is_admin)
    can_escalate_capa = action_item.spawned_capa is None and action_item.status not in ["completed", "cancelled"]

    complete_form = ManagementReviewActionCompleteForm(initial={"resolution_summary": action_item.resolution_summary})
    verify_form = ManagementReviewActionVerifyForm(initial={"verification_notes": action_item.verification_notes})

    context = {
        "action_item": action_item,
        "is_overdue": action_item.is_overdue,
        "days_open": action_item.days_open,
        "can_start": can_start,
        "can_complete": can_complete,
        "can_verify": can_verify,
        "can_escalate_capa": can_escalate_capa,
        "complete_form": complete_form,
        "verify_form": verify_form,
    }
    return render(request, "quality/managementreview/management_review_action/detail.html", context)


@login_required
def management_review_action_create(request):
    review_id = request.GET.get("review_id", "").strip()
    initial = {}
    parent_review = None
    if review_id and review_id.isdigit():
        parent_review = quality_object(request, ManagementReview, int(review_id))
        if parent_review.status in ["approved", "cancelled"]:
            messages.error(request, f"Cannot create action items under a {parent_review.get_status_display().lower()} management review.")
            return redirect("quality:management_review_detail", pk=parent_review.pk)
        initial["management_review"] = parent_review.pk
        initial["due_date"] = timezone.now().date() + timezone.timedelta(days=30)

    if request.method == "POST":
        form = ManagementReviewActionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.management_review.status in ["approved", "cancelled"]:
                messages.error(request, f"Cannot create action items under a {obj.management_review.get_status_display().lower()} management review.")
                return redirect("quality:management_review_detail", pk=obj.management_review.pk)
            with transaction.atomic():
                obj.tenant = request.tenant
                obj.status = "open"
                obj.save()
                write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Review action item {obj.number} created successfully.")
            return redirect("quality:management_review_detail", pk=obj.management_review.pk)
    else:
        form = ManagementReviewActionForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "action_item": None,
        "is_edit": False,
        "parent_review": parent_review,
        "review": parent_review,
    }
    return render(request, "quality/managementreview/management_review_action/form.html", context)


@login_required
def management_review_action_edit(request, pk):
    action_item = quality_object(request, ManagementReviewAction, pk)
    if action_item.status in ["completed", "cancelled"]:
        messages.error(request, f"Action item {action_item.number} cannot be edited because it is {action_item.get_status_display().lower()}.")
        return redirect("quality:management_review_action_detail", pk=action_item.pk)

    if request.method == "POST":
        form = ManagementReviewActionForm(request.POST, instance=action_item, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.management_review.status in ["approved", "cancelled"] and obj.management_review_id != action_item.management_review_id:
                messages.error(request, f"Cannot reassign action items to a {obj.management_review.get_status_display().lower()} management review.")
                return redirect("quality:management_review_action_detail", pk=action_item.pk)
            with transaction.atomic():
                obj.save()
                write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Review action {obj.number} updated successfully.")
            return redirect("quality:management_review_action_detail", pk=obj.pk)
    else:
        form = ManagementReviewActionForm(instance=action_item, tenant=request.tenant)

    context = {
        "form": form,
        "action_item": action_item,
        "is_edit": True,
        "parent_review": action_item.management_review,
        "review": action_item.management_review,
    }
    return render(request, "quality/managementreview/management_review_action/form.html", context)


@login_required
@require_POST
def management_review_action_delete(request, pk):
    action_item = quality_object(request, ManagementReviewAction, pk, select_related=("management_review",))
    if action_item.management_review.status in ["approved", "cancelled"]:
        messages.error(request, f"Action items belonging to a {action_item.management_review.get_status_display().lower()} management review cannot be deleted.")
        return redirect("quality:management_review_action_detail", pk=action_item.pk)

    if action_item.status == "completed":
        messages.error(request, "Closed review action items cannot be deleted.")
        return redirect("quality:management_review_action_detail", pk=action_item.pk)

    parent_id = action_item.management_review_id
    number = action_item.number
    with transaction.atomic():
        write_audit_log(request.user, action_item, "delete", tenant=request.tenant)
        action_item.delete()
    messages.success(request, f"Review action item {number} has been deleted.")
    return redirect("quality:management_review_detail", pk=parent_id)


@login_required
@require_POST
def management_review_action_start(request, pk):
    action_item = quality_object(request, ManagementReviewAction, pk)
    if action_item.status != "open":
        messages.warning(request, f"Action item {action_item.number} is already {action_item.get_status_display().lower()}.")
        return redirect("quality:management_review_action_detail", pk=action_item.pk)

    with transaction.atomic():
        action_item.status = "in_progress"
        action_item.save()
        write_audit_log(request.user, action_item, "update", tenant=request.tenant)
    messages.success(request, f"Action item {action_item.number} marked In Progress.")
    return redirect("quality:management_review_action_detail", pk=action_item.pk)


@login_required
@require_POST
def management_review_action_complete(request, pk):
    action_item = quality_object(request, ManagementReviewAction, pk)
    if action_item.status not in ["open", "in_progress"]:
        messages.warning(request, f"Action item {action_item.number} cannot be completed because it is {action_item.get_status_display().lower()}.")
        return redirect("quality:management_review_action_detail", pk=action_item.pk)

    form = ManagementReviewActionCompleteForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            action_item.resolution_summary = form.cleaned_data["resolution_summary"]
            action_item.completion_date = timezone.now().date()
            action_item.status = "pending_verification"
            action_item.save()
            write_audit_log(request.user, action_item, "complete", tenant=request.tenant)
        messages.success(request, f"Action item {action_item.number} completed and submitted for QA verification.")
    else:
        messages.error(request, "Please provide an implementation resolution summary.")
    return redirect("quality:management_review_action_detail", pk=action_item.pk)


@login_required
@require_POST
def management_review_action_verify(request, pk):
    action_item = quality_object(request, ManagementReviewAction, pk)
    if action_item.status != "pending_verification":
        messages.error(request, f"Only actions pending verification can be verified (current: {action_item.get_status_display().lower()}).")
        return redirect("quality:management_review_action_detail", pk=action_item.pk)

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request.user, "is_staff", False)
    if action_item.assignee_id == request.user.id and not is_admin:
        messages.error(request, "Independent QA verification is required. Assignee cannot self-verify.")
        return redirect("quality:management_review_action_detail", pk=action_item.pk)

    form = ManagementReviewActionVerifyForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            action_item.verification_notes = form.cleaned_data["verification_notes"]
            action_item.verified_by = request.user
            action_item.status = "completed"
            action_item.save()
            write_audit_log(request.user, action_item, "verify", tenant=request.tenant)
        messages.success(request, f"Action item {action_item.number} verified by QA and formally closed.")
    else:
        messages.error(request, "Please provide independent QA verification notes.")
    return redirect("quality:management_review_action_detail", pk=action_item.pk)


@login_required
@require_POST
def management_review_action_escalate_capa(request, pk):
    with transaction.atomic():
        action_item = quality_object(
            request,
            ManagementReviewAction,
            pk,
            queryset=ManagementReviewAction.objects.filter(tenant=request.tenant).select_for_update(),
            select_related=("management_review", "spawned_capa"),
        )
        if action_item.spawned_capa:
            messages.info(request, f"Action already escalated to CAPA {action_item.spawned_capa.number}.")
            return redirect("quality:management_review_action_detail", pk=action_item.pk)

        if action_item.status in ["completed", "cancelled"]:
            messages.error(request, f"Cannot escalate an action that is already {action_item.get_status_display().lower()}.")
            return redirect("quality:management_review_action_detail", pk=action_item.pk)

        capa = CapaInvestigation.objects.create(
            tenant=request.tenant,
            title=f"Management Review Action: {action_item.title}",
            source_type="management_review",
            source_reference=action_item.number,
            lead_investigator=request.user,
            quality_owner=request.user,
            issue_summary=f"Escalated from Management Review Action {action_item.number} (Review {action_item.management_review.number}).\n\n{action_item.description}",
            containment_actions="Executive action item escalated into formal systemic CAPA investigation.",
            status="under_investigation",
        )
        action_item.spawned_capa = capa
        action_item.status = "in_progress"
        action_item.save()
        write_audit_log(request.user, action_item, "update", tenant=request.tenant)
        write_audit_log(request.user, capa, "create", tenant=request.tenant)

    messages.success(request, f"Spawned formal CAPA investigation {capa.number} from action {action_item.number}.")
    return redirect("quality:management_review_action_detail", pk=action_item.pk)


@login_required
def management_review_action_export_csv(request):
    qs = quality_scope(ManagementReviewAction.objects.all(), request).select_related(
        "management_review", "assignee", "verified_by", "spawned_capa"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="management_review_actions.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Action Number",
        "Review Session",
        "Action Title",
        "Type",
        "Priority",
        "Assignee",
        "Due Date",
        "Status",
        "Budget Allocated",
        "Completion Date",
        "Verified By",
        "Spawned CAPA",
    ])

    for act in qs:
        writer.writerow([
            _csv_safe(act.number),
            _csv_safe(act.management_review.number),
            _csv_safe(act.title),
            _csv_safe(act.get_action_type_display()),
            _csv_safe(act.get_priority_display()),
            _csv_safe(act.assignee.get_full_name() or act.assignee.username if act.assignee else ""),
            _csv_safe(act.due_date),
            _csv_safe(act.get_status_display()),
            _csv_safe(act.budget_allocated),
            _csv_safe(act.completion_date),
            _csv_safe(act.verified_by.get_full_name() or act.verified_by.username if act.verified_by else ""),
            _csv_safe(act.spawned_capa.number if act.spawned_capa else ""),
        ])

    return response
