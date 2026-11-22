from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.DataIntegrity.SystemChangeControls import SystemChangeControlForm
from apps.quality.models.DataIntegrity.SystemChangeControls import SystemChangeControl
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 20


@login_required
def system_change_control_list(request):
    base_qs = quality_scope(
        SystemChangeControl.objects.all(),
        request,
    )

    stats = base_qs.aggregate(
        total=Count("id"),
        emergency=Count("id", filter=Q(change_priority="emergency")),
        direct_gxp=Count("id", filter=Q(gxp_impact="direct_gxp")),
        open=Count(
            "id",
            filter=~Q(status__in=["implemented_closed", "rejected", "cancelled"]),
        ),
    )
    total_count = stats["total"]
    emergency_count = stats["emergency"]
    direct_gxp_count = stats["direct_gxp"]
    open_count = stats["open"]

    qs = base_qs.select_related("system", "requestor", "system_owner", "qa_lead", "org_unit")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
            | Q(business_justification__icontains=q)
        )

    type_selected = request.GET.get("change_type", "").strip()
    if type_selected:
        qs = qs.filter(change_type=type_selected)

    priority_selected = request.GET.get("priority", "").strip()
    if priority_selected:
        qs = qs.filter(change_priority=priority_selected)

    gxp_selected = request.GET.get("gxp_impact", "").strip()
    if gxp_selected:
        qs = qs.filter(gxp_impact=gxp_selected)

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
        "changes": page_obj.object_list,
        "total_count": total_count,
        "emergency_count": emergency_count,
        "direct_gxp_count": direct_gxp_count,
        "open_count": open_count,
        "type_choices": SystemChangeControl.CHANGE_TYPE_CHOICES,
        "priority_choices": SystemChangeControl.CHANGE_PRIORITY_CHOICES,
        "gxp_choices": SystemChangeControl.GXP_IMPACT_CHOICES,
        "status_choices": SystemChangeControl.STATUS_CHOICES,
        "q": q,
        "type_selected": type_selected,
        "priority_selected": priority_selected,
        "gxp_selected": gxp_selected,
        "status_selected": status_selected,
    }
    return render(
        request,
        "quality/data_integrity/system_change_control/list.html",
        context,
    )


@login_required
def system_change_control_detail(request, pk):
    change = quality_object(
        request,
        SystemChangeControl,
        pk,
        select_related=("system", "requestor", "system_owner", "qa_lead", "org_unit"),
    )
    return render(
        request,
        "quality/data_integrity/system_change_control/detail.html",
        {"change": change},
    )


@login_required
def system_change_control_create(request):
    if request.method == "POST":
        form = SystemChangeControlForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                change = form.save(commit=False)
                change.tenant = request.tenant
                change.save()
                write_audit_log(request.user, change, "create", tenant=request.tenant)
            messages.success(request, f"System Change Control {change.number} created successfully.")
            return redirect("quality:system_change_control_detail", pk=change.pk)
    else:
        form = SystemChangeControlForm(tenant=request.tenant)

    return render(
        request,
        "quality/data_integrity/system_change_control/form.html",
        {"form": form, "change": None, "is_edit": False},
    )


@login_required
def system_change_control_edit(request, pk):
    change = quality_object(request, SystemChangeControl, pk)
    if request.method == "POST":
        form = SystemChangeControlForm(request.POST, instance=change, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                change = form.save()
                write_audit_log(request.user, change, "update", tenant=request.tenant)
            messages.success(request, f"System Change Control {change.number} updated successfully.")
            return redirect("quality:system_change_control_detail", pk=change.pk)
    else:
        form = SystemChangeControlForm(instance=change, tenant=request.tenant)

    return render(
        request,
        "quality/data_integrity/system_change_control/form.html",
        {"form": form, "change": change, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def system_change_control_delete(request, pk):
    change = quality_object(request, SystemChangeControl, pk)
    num = change.number
    with transaction.atomic():
        write_audit_log(request.user, change, "delete", tenant=request.tenant)
        change.delete()
    messages.success(request, f"System Change Control {num} deleted.")
    return redirect("quality:system_change_control_list")
