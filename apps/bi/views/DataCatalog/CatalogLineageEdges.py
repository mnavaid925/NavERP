from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.DataCatalog.CatalogLineageEdges import CatalogLineageEdgeForm
from apps.bi.models.DataCatalog.CatalogAssets import CatalogAsset
from apps.bi.models.DataCatalog.CatalogLineageEdges import CatalogLineageEdge
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def catalog_lineage_edge_list(request):
    queryset = (
        bi_scope(CatalogLineageEdge.objects.all(), request)
        .select_related("upstream_asset", "downstream_asset", "etl_pipeline")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(upstream_column__icontains=q)
            | Q(downstream_column__icontains=q)
            | Q(transformation_rule__icontains=q)
            | Q(upstream_asset__name__icontains=q)
            | Q(downstream_asset__name__icontains=q)
        )

    lineage_type_filter = request.GET.get("lineage_type", "").strip()
    if lineage_type_filter:
        queryset = queryset.filter(lineage_type=lineage_type_filter)

    impact_filter = request.GET.get("impact", "").strip()
    if impact_filter:
        queryset = queryset.filter(impact_criticality=impact_filter)

    asset_filter = request.GET.get("asset", "").strip()
    if asset_filter and asset_filter.isdigit():
        asset_id = int(asset_filter)
        queryset = queryset.filter(Q(upstream_asset_id=asset_id) | Q(downstream_asset_id=asset_id))

    all_tenant_edges = bi_scope(CatalogLineageEdge.objects.all(), request)
    counts = all_tenant_edges.aggregate(
        total=Count("id"),
        table_count=Count("id", filter=Q(lineage_type="table_level")),
        col_count=Count("id", filter=Q(lineage_type="column_level")),
        crit_count=Count("id", filter=Q(impact_criticality="critical")),
    )
    total_count = counts["total"] or 0
    table_lineage_count = counts["table_count"] or 0
    column_lineage_count = counts["col_count"] or 0
    critical_count = counts["crit_count"] or 0

    paginator = Paginator(queryset.order_by("-created_at"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "lineage_edges": page_obj,
        "lineage_type_choices": CatalogLineageEdge.LINEAGE_TYPE_CHOICES,
        "impact_choices": CatalogLineageEdge.IMPACT_CRITICALITY_CHOICES,
        "total_count": total_count,
        "table_lineage_count": table_lineage_count,
        "column_lineage_count": column_lineage_count,
        "critical_count": critical_count,
    }
    return render(request, "bi/data_catalog/catalog_lineage_edge/list.html", context)


@login_required
def catalog_lineage_edge_detail(request, pk):
    edge = bi_object(
        request,
        CatalogLineageEdge,
        pk,
        select_related=(
            "upstream_asset",
            "downstream_asset",
            "etl_pipeline",
            "transformation_step",
        ),
    )
    context = {
        "edge": edge,
    }
    return render(request, "bi/data_catalog/catalog_lineage_edge/detail.html", context)


@login_required
def catalog_lineage_edge_create(request):
    initial = {}
    downstream_param = request.GET.get("downstream")
    if downstream_param and downstream_param.isdigit():
        initial["downstream_asset"] = downstream_param
    upstream_param = request.GET.get("upstream")
    if upstream_param and upstream_param.isdigit():
        initial["upstream_asset"] = upstream_param

    if request.method == "POST":
        form = CatalogLineageEdgeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            edge = form.save(commit=False)
            edge.tenant = request.tenant
            edge.save()
            write_audit_log(
                request.user,
                edge,
                "create",
                changes=f"Created lineage edge {edge.number}: {edge.upstream_asset.code} -> {edge.downstream_asset.code}",
                tenant=request.tenant,
            )
            messages.success(request, f"Lineage edge {edge.number} registered successfully.")
            return redirect("bi:catalog_lineage_edge_detail", pk=edge.pk)
    else:
        form = CatalogLineageEdgeForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "edge": None,
        "is_edit": False,
    }
    return render(request, "bi/data_catalog/catalog_lineage_edge/form.html", context)


@login_required
def catalog_lineage_edge_edit(request, pk):
    edge = bi_object(request, CatalogLineageEdge, pk)
    if request.method == "POST":
        form = CatalogLineageEdgeForm(request.POST, instance=edge, tenant=request.tenant)
        if form.is_valid():
            edge = form.save()
            write_audit_log(
                request.user,
                edge,
                "update",
                changes=f"Updated lineage edge {edge.number}",
                tenant=request.tenant,
            )
            messages.success(request, f"Lineage edge {edge.number} updated successfully.")
            return redirect("bi:catalog_lineage_edge_detail", pk=edge.pk)
    else:
        form = CatalogLineageEdgeForm(instance=edge, tenant=request.tenant)

    context = {
        "form": form,
        "edge": edge,
        "is_edit": True,
    }
    return render(request, "bi/data_catalog/catalog_lineage_edge/form.html", context)


@login_required
@require_POST
def catalog_lineage_edge_delete(request, pk):
    edge = bi_object(request, CatalogLineageEdge, pk)
    edge_number = edge.number
    edge.delete()
    write_audit_log(
        request.user,
        edge,
        "delete",
        changes=f"Deleted lineage edge {edge_number}",
        tenant=request.tenant,
    )
    messages.success(request, f"Lineage edge {edge_number} was deleted.")
    return redirect("bi:catalog_lineage_edge_list")
