from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.PredictiveAnalytics.ForecastExecutions import ForecastExecutionForm
from apps.bi.models.PredictiveAnalytics.ForecastExecutions import ForecastExecution
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def forecast_execution_list(request):
    qs = bi_scope(ForecastExecution.objects.all(), request, owner_field="executed_by").select_related(
        "model", "semantic_model", "kpi_definition", "executed_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status="completed")),
        monthly=Count("id", filter=Q(cadence="monthly")),
    )
    total_count = counts["total"] or 0
    completed_count = counts["completed"] or 0
    monthly_count = counts["monthly"] or 0

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(notes__icontains=q)
        )

    cadence = request.GET.get("cadence", "").strip()
    if cadence:
        qs = qs.filter(cadence=cadence)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(
        request,
        "bi/predictive_analytics/forecast_execution/list.html",
        {
            "forecast_executions": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "completed_count": completed_count,
            "monthly_count": monthly_count,
            "cadence_choices": ForecastExecution.CADENCE_CHOICES,
            "status_choices": ForecastExecution.STATUS_CHOICES,
        },
    )


@login_required
def forecast_execution_detail(request, pk):
    execution = bi_object(
        request,
        ForecastExecution,
        pk,
        select_related=["model", "semantic_model", "kpi_definition", "executed_by"],
    )

    return render(
        request,
        "bi/predictive_analytics/forecast_execution/detail.html",
        {
            "forecast_obj": execution,
        },
    )


@login_required
def forecast_execution_create(request):
    initial = {}
    model_id = request.GET.get("model", "")
    if model_id.isdigit():
        initial["model"] = model_id

    if request.method == "POST":
        form = ForecastExecutionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            execution = form.save(commit=False)
            execution.tenant = request.tenant
            execution.executed_by = request.user
            execution.generate_forecast_points(save=False)
            execution.save()
            write_audit_log(request.user, execution, "create", changes={"name": execution.name, "number": execution.number}, tenant=request.tenant)
            messages.success(request, f"Forecast run '{execution.name}' ({execution.number}) projected successfully.")
            return redirect("bi:forecast_execution_detail", pk=execution.pk)
    else:
        form = ForecastExecutionForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "bi/predictive_analytics/forecast_execution/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def forecast_execution_edit(request, pk):
    execution = bi_object(request, ForecastExecution, pk)
    if request.method == "POST":
        form = ForecastExecutionForm(request.POST, instance=execution, tenant=request.tenant)
        if form.is_valid():
            execution = form.save()
            write_audit_log(request.user, execution, "update", changes={"name": execution.name, "number": execution.number}, tenant=request.tenant)
            messages.success(request, f"Forecast '{execution.name}' updated successfully.")
            return redirect("bi:forecast_execution_detail", pk=execution.pk)
    else:
        form = ForecastExecutionForm(instance=execution, tenant=request.tenant)

    return render(
        request,
        "bi/predictive_analytics/forecast_execution/form.html",
        {
            "form": form,
            "forecast_obj": execution,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def forecast_execution_delete(request, pk):
    execution = bi_object(request, ForecastExecution, pk)
    name = execution.name
    number = execution.number
    execution.delete()
    write_audit_log(request.user, execution, "delete", changes={"name": name, "number": number}, tenant=request.tenant)
    messages.success(request, f"Forecast '{name}' ({number}) deleted successfully.")
    return redirect("bi:forecast_execution_list")
