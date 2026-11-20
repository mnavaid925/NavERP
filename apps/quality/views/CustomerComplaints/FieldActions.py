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
from apps.quality.forms.CustomerComplaints.FieldActions import FieldActionForm
from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
from apps.quality.models.CustomerComplaints.FieldActions import FieldAction
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def field_action_list(request):
    qs = quality_scope(FieldAction.objects.all(), request).select_related(
        "initiating_complaint", "coordinator", "fsn_document"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(affected_product_code__icontains=q)
            | Q(affected_product_name__icontains=q)
            | Q(affected_lot_numbers__icontains=q)
            | Q(regulatory_recall_number__icontains=q)
            | Q(reason_for_action__icontains=q)
        )

    action_type_filter = request.GET.get("action_type", "").strip()
    if action_type_filter:
        qs = qs.filter(action_type=action_type_filter)

    recall_class_filter = request.GET.get("recall_class", "").strip()
    if recall_class_filter:
        qs = qs.filter(recall_class=recall_class_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    complaint_filter = request.GET.get("complaint", "").strip()
    if complaint_filter and complaint_filter.isdigit():
        qs = qs.filter(initiating_complaint_id=int(complaint_filter))

    total_count = qs.count()

    base_tenant_qs = FieldAction.objects.filter(tenant=request.tenant)
    active_recall_count = base_tenant_qs.exclude(status__in=["closed_terminated", "cancelled"]).count()
    class_i_count = base_tenant_qs.filter(recall_class="class_i_critical").count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    filter_querystring = query_params.urlencode()

    context = {
        "field_actions": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "filter_querystring": filter_querystring,
        "total_count": total_count,
        "active_recall_count": active_recall_count,
        "class_i_count": class_i_count,
        "action_type_choices": FieldAction.ACTION_TYPE_CHOICES,
        "recall_class_choices": FieldAction.RECALL_CLASS_CHOICES,
        "status_choices": FieldAction.ACTION_STATUS_CHOICES,
    }
    return render(
        request,
        "quality/customercomplaints/field_action/list.html",
        context,
    )


@login_required
def field_action_detail(request, pk):
    field_action = quality_object(
        request,
        FieldAction,
        pk,
        select_related=("initiating_complaint", "coordinator", "fsn_document"),
    )
    return render(
        request,
        "quality/customercomplaints/field_action/detail.html",
        {"field_action": field_action},
    )


@login_required
def field_action_create(request):
    initial = {
        "initiation_date": timezone.now().date(),
        "status": "planning",
        "action_type": "recall_removal",
        "recall_class": "class_ii_moderate",
    }
    complaint_pk = request.GET.get("complaint", "").strip()
    if complaint_pk and complaint_pk.isdigit():
        complaint = get_object_or_404(CustomerComplaint, pk=int(complaint_pk), tenant=request.tenant)
        initial["initiating_complaint"] = complaint
        initial["title"] = f"Recall / Field Action: {complaint.item_name}"
        initial["affected_product_code"] = complaint.item_code
        initial["affected_product_name"] = complaint.item_name
        initial["affected_lot_numbers"] = complaint.lot_number
        initial["reason_for_action"] = complaint.problem_description

    if request.method == "POST":
        form = FieldActionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                field_action = form.save(commit=False)
                field_action.tenant = request.tenant
                field_action.save()
                write_audit_log(request.user, field_action, "create", tenant=request.tenant)
            messages.success(request, f"Field Action {field_action.number} initiated.")
            return redirect("quality:field_action_detail", pk=field_action.pk)
    else:
        form = FieldActionForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "quality/customercomplaints/field_action/form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def field_action_edit(request, pk):
    field_action = quality_object(request, FieldAction, pk)

    if request.method == "POST":
        form = FieldActionForm(request.POST, instance=field_action, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                field_action = form.save()
                write_audit_log(request.user, field_action, "update", tenant=request.tenant)
            messages.success(request, f"Field Action {field_action.number} updated.")
            return redirect("quality:field_action_detail", pk=field_action.pk)
    else:
        form = FieldActionForm(instance=field_action, tenant=request.tenant)

    return render(
        request,
        "quality/customercomplaints/field_action/form.html",
        {"form": form, "field_action": field_action, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def field_action_delete(request, pk):
    field_action = quality_object(request, FieldAction, pk)
    number = field_action.number
    complaint_pk = field_action.initiating_complaint_id
    with transaction.atomic():
        write_audit_log(request.user, field_action, "delete", tenant=request.tenant)
        field_action.delete()
    messages.success(request, f"Field Action {number} deleted.")
    if complaint_pk:
        return redirect("quality:customer_complaint_detail", pk=complaint_pk)
    return redirect("quality:field_action_list")


@login_required
@require_POST
def field_action_close(request, pk):
    field_action = quality_object(request, FieldAction, pk)
    closure_summary = request.POST.get("closure_summary", "").strip()

    with transaction.atomic():
        field_action.status = "closed_terminated"
        field_action.termination_date = timezone.now().date()
        if closure_summary:
            field_action.closure_summary = closure_summary
        field_action.save()
        write_audit_log(request.user, field_action, "close", tenant=request.tenant)

    messages.success(request, f"Recall {field_action.number} formally terminated and closed.")
    return redirect("quality:field_action_detail", pk=field_action.pk)


@login_required
def field_action_export_csv(request):
    qs = quality_scope(FieldAction.objects.all(), request).select_related(
        "initiating_complaint", "coordinator"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="field_actions_recalls.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Action #",
        "Title",
        "Action Type",
        "Recall Class",
        "Status",
        "Coordinator",
        "Affected SKU",
        "Affected Product",
        "Recalled Lots",
        "Units Distributed",
        "Quarantined",
        "Recovered / Destroyed",
        "Reconciliation %",
        "Consignees Targeted",
        "Consignees Responded",
        "Response %",
        "Agency Recall #",
        "Initiation Date",
        "Termination Date",
    ])

    for fa in qs.iterator():
        writer.writerow([
            _csv_safe(fa.number),
            _csv_safe(fa.title),
            _csv_safe(fa.get_action_type_display()),
            _csv_safe(fa.get_recall_class_display()),
            _csv_safe(fa.get_status_display()),
            _csv_safe(fa.coordinator.get_full_name() or fa.coordinator.username if fa.coordinator else ""),
            _csv_safe(fa.affected_product_code),
            _csv_safe(fa.affected_product_name),
            _csv_safe(fa.affected_lot_numbers),
            _csv_safe(fa.total_units_distributed),
            _csv_safe(fa.units_quarantined_field),
            _csv_safe(fa.units_recovered_destroyed),
            _csv_safe(f"{fa.reconciliation_rate}%"),
            _csv_safe(fa.consignees_targeted),
            _csv_safe(fa.consignees_responded),
            _csv_safe(f"{fa.consignee_response_rate}%"),
            _csv_safe(fa.regulatory_recall_number),
            _csv_safe(fa.initiation_date),
            _csv_safe(fa.termination_date),
        ])

    return response
