import hashlib
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.SemanticLayer.SemanticModels import (
    SemanticModelCertificationForm,
    SemanticModelForm,
)
from apps.bi.models.DataWarehouse.DataMarts import DataMart
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def semantic_model_list(request):
    queryset = (
        bi_scope(SemanticModel.objects.all(), request)
        .select_related("warehouse_table", "data_mart", "owner")
        .annotate(
            measure_count=Count("measures", distinct=True),
        )
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(primary_key_column__icontains=q)
            | Q(natural_key_columns__icontains=q)
            | Q(description__icontains=q)
        )

    model_type_filter = request.GET.get("model_type", "").strip()
    if model_type_filter:
        queryset = queryset.filter(model_type=model_type_filter)

    certification_status_filter = request.GET.get("certification_status", "").strip()
    if certification_status_filter:
        queryset = queryset.filter(certification_status=certification_status_filter)

    scd_type_filter = request.GET.get("scd_type", "").strip()
    if scd_type_filter:
        queryset = queryset.filter(scd_type=scd_type_filter)

    mart_filter = request.GET.get("data_mart", "").strip()
    if mart_filter.isdigit():
        queryset = queryset.filter(data_mart_id=mart_filter)

    is_active_filter = request.GET.get("is_active", "").strip()
    if is_active_filter in ("1", "true", "True"):
        queryset = queryset.filter(is_active=True)
    elif is_active_filter in ("0", "false", "False"):
        queryset = queryset.filter(is_active=False)

    total_count = queryset.count()
    paginator = Paginator(queryset.order_by("-created_at"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    data_marts = bi_scope(DataMart.objects.all(), request).order_by("name")

    context = {
        "models": page_obj,
        "semantic_models": page_obj,
        "object_list": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "search_query": q,
        "model_type_filter": model_type_filter,
        "certification_status_filter": certification_status_filter,
        "scd_type_filter": scd_type_filter,
        "data_mart_filter": mart_filter,
        "is_active_filter": is_active_filter,
        "model_type_choices": SemanticModel.MODEL_TYPE_CHOICES,
        "certification_status_choices": SemanticModel.CERTIFICATION_STATUS_CHOICES,
        "scd_type_choices": SemanticModel.SCD_TYPE_CHOICES,
        "data_marts": data_marts,
    }
    return render(request, "bi/semantic_layer/semantic_model/list.html", context)


@login_required
def semantic_model_detail(request, pk):
    model = bi_object(
        request,
        SemanticModel,
        pk,
        select_related=("warehouse_table", "data_mart", "owner", "certified_by"),
    )
    measures = list(model.measures.filter(tenant=request.tenant).select_related("glossary_term"))
    drill_hierarchies = list(model.drill_hierarchies.filter(tenant=request.tenant))

    certify_form = SemanticModelCertificationForm(
        initial={
            "certification_status": model.certification_status,
            "certification_notes": model.certification_notes,
        }
    )

    context = {
        "model": model,
        "semantic_model": model,
        "object": model,
        "measures": measures,
        "drill_hierarchies": drill_hierarchies,
        "certify_form": certify_form,
    }
    return render(request, "bi/semantic_layer/semantic_model/detail.html", context)


@login_required
def semantic_model_create(request):
    if request.method == "POST":
        form = SemanticModelForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            model = form.save(commit=False)
            model.tenant = request.tenant
            if not model.owner:
                model.owner = request.user
            model.save()
            write_audit_log(request.user, model, "create", tenant=request.tenant)
            messages.success(request, f"Semantic Model '{model.name}' created successfully.")
            return redirect("bi:semantic_model_detail", pk=model.pk)
    else:
        form = SemanticModelForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "bi/semantic_layer/semantic_model/form.html", context)


@login_required
def semantic_model_edit(request, pk):
    model = bi_object(request, SemanticModel, pk)
    if request.method == "POST":
        form = SemanticModelForm(request.POST, instance=model, tenant=request.tenant)
        if form.is_valid():
            model = form.save()
            write_audit_log(request.user, model, "update", tenant=request.tenant)
            messages.success(request, f"Semantic Model '{model.name}' updated successfully.")
            return redirect("bi:semantic_model_detail", pk=model.pk)
    else:
        form = SemanticModelForm(instance=model, tenant=request.tenant)

    context = {
        "form": form,
        "model": model,
        "semantic_model": model,
        "object": model,
        "is_edit": True,
    }
    return render(request, "bi/semantic_layer/semantic_model/form.html", context)


@login_required
@require_POST
def semantic_model_delete(request, pk):
    model = bi_object(request, SemanticModel, pk)
    name = model.name
    num = model.number
    write_audit_log(request.user, model, "delete", tenant=request.tenant)
    model.delete()
    messages.success(request, f"Semantic Model '{name}' ({num}) deleted successfully.")
    return redirect("bi:semantic_model_list")


@login_required
@require_POST
def semantic_model_certify(request, pk):
    model = bi_object(request, SemanticModel, pk)
    form = SemanticModelCertificationForm(request.POST)
    if form.is_valid():
        new_status = form.cleaned_data["certification_status"]
        notes = form.cleaned_data.get("certification_notes", "")
        old_status = model.certification_status
        model.certification_status = new_status
        model.certification_notes = notes
        if new_status == "certified":
            model.certified_by = request.user
            model.certified_at = timezone.now()
        else:
            model.certified_by = None
            model.certified_at = None
        model.save(update_fields=["certification_status", "certification_notes", "certified_by", "certified_at", "updated_at"])
        write_audit_log(request.user, model, "certify", tenant=request.tenant)
        messages.success(request, f"Certification status updated to '{model.get_certification_status_display()}'.")
    else:
        messages.error(request, "Invalid certification status submitted.")
    return redirect("bi:semantic_model_detail", pk=model.pk)


@login_required
@require_POST
def semantic_model_introspect(request, pk):
    model = bi_object(request, SemanticModel, pk, select_related=("warehouse_table",))
    if not model.warehouse_table:
        messages.error(request, "No underlying warehouse table is bound to this semantic model.")
        return redirect("bi:semantic_model_detail", pk=model.pk)

    table = model.warehouse_table
    if table.tenant_id != request.tenant.pk:
        messages.error(request, "Warehouse table belongs to another workspace.")
        return redirect("bi:semantic_model_detail", pk=model.pk)

    schema_def = table.schema_definition or []
    payload = json.dumps(schema_def, sort_keys=True).encode("utf-8")
    fingerprint = hashlib.sha256(payload).hexdigest()[:16]

    model.source_fingerprint = fingerprint
    model.last_introspected_at = timezone.now()
    if not model.primary_key_column and table.primary_key_column:
        model.primary_key_column = table.primary_key_column
    if not model.natural_key_columns and table.natural_key_column:
        model.natural_key_columns = table.natural_key_column

    model.save(update_fields=["source_fingerprint", "last_introspected_at", "primary_key_column", "natural_key_columns", "updated_at"])

    write_audit_log(request.user, model, "introspect", tenant=request.tenant)
    messages.success(
        request,
        f"Schema introspected from '{table.name}'. Found {len(schema_def)} column definitions (Hash: {fingerprint}).",
    )
    return redirect("bi:semantic_model_detail", pk=model.pk)
