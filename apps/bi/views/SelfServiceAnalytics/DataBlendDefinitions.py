from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.SelfServiceAnalytics.DataBlendDefinitions import DataBlendDefinitionForm
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SelfServiceAnalytics.AdHocQueries import AdHocQuery
from apps.bi.models.SelfServiceAnalytics.DataBlendDefinitions import DataBlendDefinition
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def data_blend_definition_list(request):
    qs = bi_scope(DataBlendDefinition.objects.all(), request, owner_field="created_by").select_related(
        "primary_semantic_model",
        "primary_warehouse_table",
        "secondary_semantic_model",
        "secondary_warehouse_table",
        "created_by",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(slug__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    join_type = request.GET.get("join_type", "").strip()
    if join_type:
        qs = qs.filter(join_type=join_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "bi/self_service_analytics/data_blend_definition/list.html",
        {
            "blends": page_obj.object_list,
            "page_obj": page_obj,
            "join_type_choices": DataBlendDefinition.JOIN_TYPE_CHOICES,
            "status_choices": DataBlendDefinition.STATUS_CHOICES,
        },
    )


@login_required
def data_blend_definition_detail(request, pk):
    blend = bi_object(
        request,
        DataBlendDefinition,
        pk,
        select_related=(
            "primary_semantic_model",
            "primary_warehouse_table",
            "secondary_semantic_model",
            "secondary_warehouse_table",
            "created_by",
        ),
    )

    queries = AdHocQuery.objects.filter(tenant=request.tenant, data_blend=blend).order_by("-created_at")

    return render(
        request,
        "bi/self_service_analytics/data_blend_definition/detail.html",
        {
            "blend": blend,
            "queries": queries,
        },
    )


@login_required
def data_blend_definition_create(request):
    semantic_models = SemanticModel.objects.filter(tenant=request.tenant, is_active=True)
    warehouse_tables = WarehouseTable.objects.filter(tenant=request.tenant, is_active=True)

    if request.method == "POST":
        form = DataBlendDefinitionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            blend = form.save(commit=False)
            blend.tenant = request.tenant
            blend.created_by = request.user
            blend.save()

            write_audit_log(
                request,
                action="create",
                instance=blend,
                description=f"Created data blend definition {blend.name} ({blend.number})",
            )
            messages.success(request, f"Data blend '{blend.name}' created successfully.")
            return redirect("bi:data_blend_definition_detail", pk=blend.pk)
    else:
        form = DataBlendDefinitionForm(tenant=request.tenant)

    return render(
        request,
        "bi/self_service_analytics/data_blend_definition/form.html",
        {
            "form": form,
            "is_edit": False,
            "semantic_models": semantic_models,
            "warehouse_tables": warehouse_tables,
        },
    )


@login_required
def data_blend_definition_edit(request, pk):
    blend = bi_object(request, DataBlendDefinition, pk)
    semantic_models = SemanticModel.objects.filter(tenant=request.tenant, is_active=True)
    warehouse_tables = WarehouseTable.objects.filter(tenant=request.tenant, is_active=True)

    if request.method == "POST":
        form = DataBlendDefinitionForm(request.POST, instance=blend, tenant=request.tenant)
        if form.is_valid():
            blend = form.save()
            write_audit_log(
                request,
                action="update",
                instance=blend,
                description=f"Updated data blend definition {blend.name} ({blend.number})",
            )
            messages.success(request, f"Data blend '{blend.name}' updated successfully.")
            return redirect("bi:data_blend_definition_detail", pk=blend.pk)
    else:
        form = DataBlendDefinitionForm(instance=blend, tenant=request.tenant)

    return render(
        request,
        "bi/self_service_analytics/data_blend_definition/form.html",
        {
            "form": form,
            "blend": blend,
            "is_edit": True,
            "semantic_models": semantic_models,
            "warehouse_tables": warehouse_tables,
        },
    )


@login_required
@require_POST
def data_blend_definition_delete(request, pk):
    blend = bi_object(request, DataBlendDefinition, pk)
    name = blend.name
    number = blend.number

    write_audit_log(
        request,
        action="delete",
        instance=blend,
        description=f"Deleted data blend definition {name} ({number})",
    )
    blend.delete()
    messages.success(request, f"Data blend '{name}' ({number}) deleted.")
    return redirect("bi:data_blend_definition_list")


@login_required
def data_blend_definition_preview(request, pk):
    blend = bi_object(
        request,
        DataBlendDefinition,
        pk,
        select_related=(
            "primary_semantic_model",
            "primary_warehouse_table",
            "secondary_semantic_model",
            "secondary_warehouse_table",
        ),
    )

    preview_cols = ["Primary Key", "Primary Name", "Secondary Attribute", "Secondary Value", "Blend Match"]
    preview_rows = [
        ["CUST-001", "Acme Corporation", "Active POs", "12", "Exact Match"],
        ["CUST-002", "Globex Global", "Active POs", "5", "Exact Match"],
        ["CUST-003", "Stark Industries", "Active POs", "28", "Exact Match"],
        ["CUST-004", "Wayne Enterprises", "Active POs", "17", "Exact Match"],
    ]

    return render(
        request,
        "bi/self_service_analytics/data_blend_definition/detail.html",
        {
            "blend": blend,
            "preview_cols": preview_cols,
            "preview_rows": preview_rows,
            "is_preview": True,
        },
    )
