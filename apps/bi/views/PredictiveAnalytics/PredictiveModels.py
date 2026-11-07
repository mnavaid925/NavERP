from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.PredictiveAnalytics.PredictiveModels import PredictiveModelForm
from apps.bi.models.PredictiveAnalytics.PredictiveModels import PredictiveModel
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def predictive_model_list(request):
    qs = bi_scope(PredictiveModel.objects.all(), request, owner_field="created_by").select_related(
        "semantic_model", "warehouse_table", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        forecast=Count("id", filter=Q(problem_type="time_series_forecast")),
        anomaly=Count("id", filter=Q(problem_type="anomaly_detection")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    forecast_count = counts["forecast"] or 0
    anomaly_count = counts["anomaly"] or 0

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(slug__icontains=q)
            | Q(number__icontains=q)
            | Q(target_metric__icontains=q)
            | Q(description__icontains=q)
        )

    problem_type = request.GET.get("problem_type", "").strip()
    if problem_type:
        qs = qs.filter(problem_type=problem_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(
        request,
        "bi/predictive_analytics/predictive_model/list.html",
        {
            "predictive_models": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "active_count": active_count,
            "forecast_count": forecast_count,
            "anomaly_count": anomaly_count,
            "problem_type_choices": PredictiveModel.PROBLEM_TYPE_CHOICES,
            "status_choices": PredictiveModel.STATUS_CHOICES,
        },
    )


@login_required
def predictive_model_detail(request, pk):
    model = bi_object(
        request,
        PredictiveModel,
        pk,
        select_related=["semantic_model", "warehouse_table", "created_by"],
    )
    executions = model.forecast_executions.filter(tenant=request.tenant).order_by("-executed_at")[:10]
    anomalies = model.detected_anomalies.filter(tenant=request.tenant).order_by("-anomaly_timestamp")[:10]

    return render(
        request,
        "bi/predictive_analytics/predictive_model/detail.html",
        {
            "model_obj": model,
            "executions": executions,
            "anomalies": anomalies,
            "executions_count": model.forecast_executions.filter(tenant=request.tenant).count(),
            "anomalies_count": model.detected_anomalies.filter(tenant=request.tenant).count(),
        },
    )


@login_required
def predictive_model_create(request):
    if request.method == "POST":
        form = PredictiveModelForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            model = form.save(commit=False)
            model.tenant = request.tenant
            model.created_by = request.user
            model.save()
            write_audit_log(request.user, model, "create", changes={"name": model.name, "number": model.number}, tenant=request.tenant)
            messages.success(request, f"Predictive Model '{model.name}' ({model.number}) created successfully.")
            return redirect("bi:predictive_model_detail", pk=model.pk)
    else:
        form = PredictiveModelForm(tenant=request.tenant)

    return render(
        request,
        "bi/predictive_analytics/predictive_model/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def predictive_model_edit(request, pk):
    model = bi_object(request, PredictiveModel, pk)
    if request.method == "POST":
        form = PredictiveModelForm(request.POST, instance=model, tenant=request.tenant)
        if form.is_valid():
            model = form.save()
            write_audit_log(request.user, model, "update", changes={"name": model.name, "number": model.number}, tenant=request.tenant)
            messages.success(request, f"Predictive Model '{model.name}' updated successfully.")
            return redirect("bi:predictive_model_detail", pk=model.pk)
    else:
        form = PredictiveModelForm(instance=model, tenant=request.tenant)

    return render(
        request,
        "bi/predictive_analytics/predictive_model/form.html",
        {
            "form": form,
            "model_obj": model,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def predictive_model_delete(request, pk):
    model = bi_object(request, PredictiveModel, pk)
    name = model.name
    number = model.number
    model.delete()
    write_audit_log(request.user, model, "delete", changes={"name": name, "number": number}, tenant=request.tenant)
    messages.success(request, f"Predictive Model '{name}' ({number}) deleted successfully.")
    return redirect("bi:predictive_model_list")


@login_required
@require_POST
def predictive_model_train(request, pk):
    model = bi_object(request, PredictiveModel, pk)
    model.trigger_training()
    write_audit_log(
        request.user,
        model,
        "train",
        changes={
            "accuracy_metric_name": model.accuracy_metric_name,
            "accuracy_metric_value": str(model.accuracy_metric_value),
        },
        tenant=request.tenant,
    )
    messages.success(
        request,
        f"AutoML fitting completed for '{model.name}'. Validation Score: {model.accuracy_metric_name} = {model.accuracy_metric_value}.",
    )
    return redirect("bi:predictive_model_detail", pk=model.pk)
