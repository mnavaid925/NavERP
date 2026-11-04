from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.SemanticLayer.CalculatedMeasureForms import CalculatedMeasureForm
from apps.bi.models.SemanticLayer.CalculatedMeasures import CalculatedMeasure
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def calculated_measure_list(request):
    queryset = (
        bi_scope(CalculatedMeasure.objects.all(), request)
        .select_related("semantic_model", "glossary_term")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(source_column__icontains=q)
            | Q(formula_expression__icontains=q)
            | Q(description__icontains=q)
        )

    model_filter = request.GET.get("model", "").strip()
    if model_filter:
        queryset = queryset.filter(semantic_model_id=model_filter)

    aggregation_filter = request.GET.get("aggregation", "").strip()
    if aggregation_filter:
        queryset = queryset.filter(aggregation_type=aggregation_filter)

    time_intelligence_filter = request.GET.get("time_intelligence", "").strip()
    if time_intelligence_filter:
        queryset = queryset.filter(time_intelligence=time_intelligence_filter)

    is_active_filter = request.GET.get("is_active", "").strip()
    if is_active_filter in ("1", "true", "True"):
        queryset = queryset.filter(is_active=True)
    elif is_active_filter in ("0", "false", "False"):
        queryset = queryset.filter(is_active=False)

    total_count = queryset.count()
    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    semantic_models = bi_scope(SemanticModel.objects.all(), request).order_by("name")

    context = {
        "measures": page_obj,
        "calculated_measures": page_obj,
        "object_list": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "search_query": q,
        "model_filter": model_filter,
        "aggregation_filter": aggregation_filter,
        "time_intelligence_filter": time_intelligence_filter,
        "is_active_filter": is_active_filter,
        "aggregation_type_choices": CalculatedMeasure.AGGREGATION_TYPE_CHOICES,
        "time_intelligence_choices": CalculatedMeasure.TIME_INTELLIGENCE_CHOICES,
        "semantic_models": semantic_models,
    }
    return render(request, "bi/semantic_layer/calculated_measure/list.html", context)


@login_required
def calculated_measure_detail(request, pk):
    measure = bi_object(
        request,
        CalculatedMeasure,
        pk,
        select_related=("semantic_model", "glossary_term"),
    )

    context = {
        "measure": measure,
        "calculated_measure": measure,
        "object": measure,
    }
    return render(request, "bi/semantic_layer/calculated_measure/detail.html", context)


@login_required
def calculated_measure_create(request):
    initial = {}
    model_param = request.GET.get("model")
    if model_param:
        initial["semantic_model"] = model_param
    term_param = request.GET.get("glossary_term")
    if term_param:
        initial["glossary_term"] = term_param

    if request.method == "POST":
        form = CalculatedMeasureForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            measure = form.save(commit=False)
            measure.tenant = request.tenant
            measure.save()
            write_audit_log(
                request.tenant,
                request.user,
                "create",
                "CalculatedMeasure",
                measure.pk,
                f"Created calculated measure {measure.name} ({measure.number})",
            )
            messages.success(request, f"Calculated Measure '{measure.name}' created successfully.")
            return redirect("bi:calculated_measure_detail", pk=measure.pk)
    else:
        form = CalculatedMeasureForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "bi/semantic_layer/calculated_measure/form.html", context)


@login_required
def calculated_measure_edit(request, pk):
    measure = bi_object(request, CalculatedMeasure, pk)
    if request.method == "POST":
        form = CalculatedMeasureForm(request.POST, instance=measure, tenant=request.tenant)
        if form.is_valid():
            measure = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "update",
                "CalculatedMeasure",
                measure.pk,
                f"Updated calculated measure {measure.name} ({measure.number})",
            )
            messages.success(request, f"Calculated Measure '{measure.name}' updated successfully.")
            return redirect("bi:calculated_measure_detail", pk=measure.pk)
    else:
        form = CalculatedMeasureForm(instance=measure, tenant=request.tenant)

    context = {
        "form": form,
        "measure": measure,
        "calculated_measure": measure,
        "object": measure,
        "is_edit": True,
    }
    return render(request, "bi/semantic_layer/calculated_measure/form.html", context)


@login_required
@require_POST
def calculated_measure_delete(request, pk):
    measure = bi_object(request, CalculatedMeasure, pk)
    name = measure.name
    num = measure.number
    model_pk = measure.semantic_model_id
    measure.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "delete",
        "CalculatedMeasure",
        pk,
        f"Deleted calculated measure {name} ({num})",
    )
    messages.success(request, f"Calculated Measure '{name}' ({num}) deleted successfully.")
    return redirect("bi:calculated_measure_list")
