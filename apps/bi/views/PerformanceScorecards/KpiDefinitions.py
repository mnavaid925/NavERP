from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.PerformanceScorecards.KpiDefinitions import (
    KpiDefinitionForm,
    KpiDefinitionRefreshForm,
)
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log


@login_required
def kpi_definition_list(request):
    qs = bi_scope(KpiDefinition.objects.all(), request, owner_field="owner").select_related(
        "semantic_measure", "department", "owner"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        under_review=Count("id", filter=Q(status="under_review")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    under_review_count = counts["under_review"] or 0

    # Calculate on-target count in python or query
    on_target_count = sum(1 for k in qs if k.calculate_rag_status() == "green")

    # Filters
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(category__icontains=q)
            | Q(description__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    perspective = request.GET.get("perspective", "").strip()
    if perspective:
        qs = qs.filter(perspective=perspective)

    target_direction = request.GET.get("target_direction", "").strip()
    if target_direction:
        qs = qs.filter(target_direction=target_direction)

    calculation_type = request.GET.get("calculation_type", "").strip()
    if calculation_type:
        qs = qs.filter(calculation_type=calculation_type)

    department = request.GET.get("department", "").strip()
    if department:
        qs = qs.filter(department_id=department)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    kpis = paginator.get_page(page_number)

    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "kpis": kpis,
        "status_choices": KpiDefinition.STATUS_CHOICES,
        "perspective_choices": KpiDefinition.PERSPECTIVE_CHOICES,
        "direction_choices": KpiDefinition.DIRECTION_CHOICES,
        "calc_type_choices": KpiDefinition.CALC_TYPE_CHOICES,
        "departments": departments,
        "stats": {
            "total": total_count,
            "active": active_count,
            "under_review": under_review_count,
            "on_target": on_target_count,
        },
    }
    return render(request, "bi/kpi_performance_scorecards/kpi_definition/list.html", context)


@login_required
def kpi_definition_detail(request, pk):
    kpi = bi_object(
        request,
        KpiDefinition,
        pk,
        select_related=("semantic_measure", "department", "owner"),
        prefetch_related=("scorecard_assignments__scorecard", "scorecard_assignments__objective"),
    )
    assignments = kpi.scorecard_assignments.all().order_by("scorecard__name")

    context = {
        "kpi": kpi,
        "assignments": assignments,
        "rag_status": kpi.calculate_rag_status(),
        "refresh_form": KpiDefinitionRefreshForm(initial={"new_value": kpi.current_value}),
    }
    return render(request, "bi/kpi_performance_scorecards/kpi_definition/detail.html", context)


@login_required
@tenant_admin_required
def kpi_definition_create(request):
    if request.method == "POST":
        form = KpiDefinitionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            kpi = form.save(commit=False)
            kpi.tenant = request.tenant
            if not kpi.owner:
                kpi.owner = request.user
            kpi.save()
            write_audit_log(
                request.user,
                kpi,
                "create",
                changes={"summary": f"Created KPI Definition {kpi.number} ({kpi.name})"},
                tenant=request.tenant,
            )
            messages.success(request, f"KPI '{kpi.name}' created successfully.")
            return redirect(kpi.get_absolute_url())
    else:
        form = KpiDefinitionForm(tenant=request.tenant)

    context = {
        "form": form,
        "kpi": None,
        "is_edit": False,
    }
    return render(request, "bi/kpi_performance_scorecards/kpi_definition/form.html", context)


@login_required
@tenant_admin_required
def kpi_definition_edit(request, pk):
    kpi = bi_object(request, KpiDefinition, pk)
    if request.method == "POST":
        form = KpiDefinitionForm(request.POST, instance=kpi, tenant=request.tenant)
        if form.is_valid():
            kpi = form.save()
            write_audit_log(
                request.user,
                kpi,
                "update",
                changes={"summary": f"Updated KPI Definition {kpi.number} ({kpi.name})"},
                tenant=request.tenant,
            )
            messages.success(request, f"KPI '{kpi.name}' updated successfully.")
            return redirect(kpi.get_absolute_url())
    else:
        form = KpiDefinitionForm(instance=kpi, tenant=request.tenant)

    context = {
        "form": form,
        "kpi": kpi,
        "is_edit": True,
    }
    return render(request, "bi/kpi_performance_scorecards/kpi_definition/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def kpi_definition_delete(request, pk):
    kpi = bi_object(request, KpiDefinition, pk)
    kpi_name = kpi.name
    kpi_num = kpi.number
    write_audit_log(
        request.user,
        kpi,
        "delete",
        changes={"summary": f"Deleted KPI Definition {kpi_num} ({kpi_name})"},
        tenant=request.tenant,
    )
    kpi.delete()
    messages.success(request, f"KPI '{kpi_name}' deleted.")
    return redirect("bi:kpi_definition_list")


@login_required
@require_POST
def kpi_definition_refresh(request, pk):
    kpi = bi_object(request, KpiDefinition, pk)
    form = KpiDefinitionRefreshForm(request.POST)
    if form.is_valid():
        new_val = form.cleaned_data["new_value"]
        notes = form.cleaned_data.get("notes", "")
        kpi.previous_value = kpi.current_value
        kpi.current_value = new_val
        kpi.last_calculated_at = timezone.now()
        kpi.save(update_fields=["previous_value", "current_value", "last_calculated_at", "updated_at"])

        write_audit_log(
            request.user,
            kpi,
            "update",
            changes={"summary": f"Refreshed KPI {kpi.number} to {new_val} (was {kpi.previous_value}). Notes: {notes}"},
            tenant=request.tenant,
        )
        messages.success(request, f"KPI '{kpi.name}' value updated to {new_val}.")
    else:
        messages.error(request, "Invalid measurement value entered.")
    return redirect(kpi.get_absolute_url())
