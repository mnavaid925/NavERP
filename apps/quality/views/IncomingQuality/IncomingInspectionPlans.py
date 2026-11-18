import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.quality.forms.IncomingQuality.IncomingInspectionPlans import (
    IncomingInspectionPlanForm,
)
from apps.quality.models.IncomingQuality.IncomingInspectionPlans import (
    IncomingInspectionPlan,
)

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def incoming_inspection_plan_list(request):
    qs = IncomingInspectionPlan.objects.filter(tenant=request.tenant).select_related(
        "supplier", "sop_document", "assigned_team"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(item_code__icontains=search_query)
            | Q(item_name__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_frequency = request.GET.get("frequency", "").strip()
    if current_frequency:
        qs = qs.filter(inspection_frequency=current_frequency)

    current_supplier = request.GET.get("supplier", "").strip()
    if current_supplier.isdigit():
        qs = qs.filter(supplier_id=int(current_supplier))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    suppliers = list(
        Party.objects.filter(
            tenant=request.tenant, roles__role__in=("supplier", "vendor")
        ).only("id", "name").distinct().order_by("name")
    )

    context = {
        "plans": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "status_choices": IncomingInspectionPlan.STATUS_CHOICES,
        "frequency_choices": IncomingInspectionPlan.INSPECTION_FREQUENCY_CHOICES,
        "suppliers": suppliers,
        "current_status": current_status,
        "current_frequency": current_frequency,
        "current_supplier": current_supplier,
        "search_query": search_query,
    }
    return render(request, "quality/incoming_quality/incoming_inspection_plan/list.html", context)


@login_required
def incoming_inspection_plan_detail(request, pk):
    plan = get_object_or_404(
        IncomingInspectionPlan.objects.filter(tenant=request.tenant).select_related(
            "supplier", "sop_document", "assigned_team"
        ),
        pk=pk,
    )
    context = {
        "plan": plan,
        "obj": plan,
        "status_css": IncomingInspectionPlan.STATUS_CSS,
        "freq_css": IncomingInspectionPlan.FREQUENCY_CSS,
    }
    return render(request, "quality/incoming_quality/incoming_inspection_plan/detail.html", context)


@login_required
def incoming_inspection_plan_create(request):
    if request.method == "POST":
        form = IncomingInspectionPlanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            plan = form.save()
            write_audit_log(request.user, plan, "create", tenant=request.tenant)
            messages.success(request, f"Incoming inspection plan {plan.number} created successfully.")
            return redirect("quality:incoming_inspection_plan_detail", pk=plan.pk)
    else:
        form = IncomingInspectionPlanForm(tenant=request.tenant)

    return render(
        request,
        "quality/incoming_quality/incoming_inspection_plan/form.html",
        {"form": form, "title": "Create Incoming Inspection Plan"},
    )


@login_required
def incoming_inspection_plan_edit(request, pk):
    plan = get_object_or_404(IncomingInspectionPlan.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = IncomingInspectionPlanForm(request.POST, instance=plan, tenant=request.tenant)
        if form.is_valid():
            plan = form.save()
            write_audit_log(request.user, plan, "update", tenant=request.tenant)
            messages.success(request, f"Incoming inspection plan {plan.number} updated successfully.")
            return redirect("quality:incoming_inspection_plan_detail", pk=plan.pk)
    else:
        form = IncomingInspectionPlanForm(instance=plan, tenant=request.tenant)

    return render(
        request,
        "quality/incoming_quality/incoming_inspection_plan/form.html",
        {"form": form, "plan": plan, "obj": plan, "title": f"Edit {plan.number}"},
    )


@require_POST
@login_required
@tenant_admin_required
def incoming_inspection_plan_delete(request, pk):
    plan = get_object_or_404(IncomingInspectionPlan.objects.filter(tenant=request.tenant), pk=pk)
    num = plan.number
    write_audit_log(request.user, plan, "delete", tenant=request.tenant)
    plan.delete()
    messages.success(request, f"Incoming inspection plan {num} was deleted.")
    return redirect("quality:incoming_inspection_plan_list")


@login_required
def incoming_inspection_plan_export(request):
    qs = IncomingInspectionPlan.objects.filter(tenant=request.tenant).select_related("supplier")

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(item_code__icontains=search_query)
            | Q(item_name__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="incoming_inspection_plans.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Plan Number",
        "Title",
        "Item Code",
        "Item Name",
        "Revision",
        "Supplier",
        "Sampling Standard",
        "Inspection Level",
        "Inspection Frequency",
        "AQL Critical",
        "AQL Major",
        "AQL Minor",
        "Requires CoA",
        "Status",
        "Created At",
    ])

    for p in qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(p.number),
            _csv_safe(p.title),
            _csv_safe(p.item_code),
            _csv_safe(p.item_name),
            _csv_safe(p.revision),
            _csv_safe(p.supplier.name if p.supplier else ""),
            _csv_safe(p.get_sampling_standard_display()),
            _csv_safe(p.get_inspection_level_display()),
            _csv_safe(p.get_inspection_frequency_display()),
            _csv_safe(p.aql_critical),
            _csv_safe(p.aql_major),
            _csv_safe(p.aql_minor),
            _csv_safe("Yes" if p.requires_coa else "No"),
            _csv_safe(p.get_status_display()),
            _csv_safe(p.created_at.strftime("%Y-%m-%d")),
        ])

    return response
