from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.IntegrationApiHub.AssetGisMappings import (
    AssetGisMappingForm,
)
from apps.assets.models.IntegrationApiHub.AssetGisMappings import (
    AssetGisMapping,
)
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnector,
)
from apps.assets.views._common import assets_object, assets_scope
from apps.core.utils import write_audit_log
from apps.scm.models import Asset


@login_required
def mapping_list(request):
    """List tenant-scoped GIS Asset Mappings with spatial drift KPIs and filters."""
    base_qs = assets_scope(
        AssetGisMapping.objects.select_related(
            "connector",
            "operational_asset",
            "location",
            "org_unit",
            "gis_custodian",
        ),
        request,
    )

    kpis = base_qs.aggregate(
        total=Count("id"),
        in_sync=Count("id", filter=Q(drift_status="in_sync")),
        drift=Count(
            "id", filter=Q(drift_status__in=("location_drift", "attribute_drift"))
        ),
        linear=Count("id", filter=Q(is_linear_asset=True)),
    )

    qs = base_qs
    q = (request.GET.get("q") or "").strip()
    connector_id = (request.GET.get("connector") or "").strip()
    asset_id = (request.GET.get("operational_asset") or "").strip()
    geometry_type = (request.GET.get("geometry_type") or "").strip()
    drift_status = (request.GET.get("drift_status") or "").strip()
    status = (request.GET.get("status") or "").strip()

    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(external_feature_id__icontains=q)
            | Q(layer_name__icontains=q)
            | Q(lrs_route_id__icontains=q)
            | Q(connector__number__icontains=q)
        )
    if connector_id.isdigit():
        qs = qs.filter(connector_id=int(connector_id))
    if asset_id.isdigit():
        qs = qs.filter(operational_asset_id=int(asset_id))
    if geometry_type in dict(AssetGisMapping.GEOMETRY_TYPE_CHOICES):
        qs = qs.filter(geometry_type=geometry_type)
    if drift_status in dict(AssetGisMapping.DRIFT_STATUS_CHOICES):
        qs = qs.filter(drift_status=drift_status)
    if status in dict(AssetGisMapping.STATUS_CHOICES):
        qs = qs.filter(status=status)

    paginator = Paginator(qs.order_by("number"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    connectors = assets_scope(AssetIntegrationConnector.objects.all(), request).order_by(
        "number"
    )
    assets_list = assets_scope(Asset.objects.all(), request).order_by("code")

    context = {
        "mappings": page_obj,
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": kpis["total"] or 0,
        "in_sync_count": kpis["in_sync"] or 0,
        "drift_count": kpis["drift"] or 0,
        "linear_count": kpis["linear"] or 0,
        "connectors": connectors,
        "assets_list": assets_list,
        "geometry_choices": AssetGisMapping.GEOMETRY_TYPE_CHOICES,
        "drift_choices": AssetGisMapping.DRIFT_STATUS_CHOICES,
        "status_choices": AssetGisMapping.STATUS_CHOICES,
        "search_query": q,
    }
    return render(
        request,
        "assets/integrationapihub/asset_gis_mapping/list.html",
        context,
    )


@login_required
def mapping_create(request):
    """Create a new GIS Asset Spatial Mapping."""
    if request.method == "POST":
        if request.tenant is None:
            messages.error(
                request,
                "An active tenant workspace is required to create a GIS mapping.",
            )
            return redirect("assets:asset_gis_mapping_list")
        form = AssetGisMappingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                mapping = form.save(commit=False)
                mapping.tenant = request.tenant
                mapping.save()
                write_audit_log(
                    request.user,
                    mapping,
                    "create",
                    changes={
                        "number": mapping.number,
                        "layer_name": mapping.layer_name,
                        "external_feature_id": mapping.external_feature_id,
                    },
                    tenant=request.tenant,
                )
            messages.success(
                request, f"GIS mapping {mapping.number} created successfully."
            )
            return redirect("assets:asset_gis_mapping_detail", pk=mapping.pk)
    else:
        initial = {}
        connector_id = (request.GET.get("connector") or "").strip()
        if connector_id.isdigit():
            initial["connector"] = int(connector_id)
        form = AssetGisMappingForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/integrationapihub/asset_gis_mapping/form.html",
        {
            "form": form,
            "mapping": None,
            "is_edit": False,
            "title": "New GIS Spatial Mapping",
        },
    )


@login_required
def mapping_detail(request, pk):
    """Display GIS spatial mapping metadata, LRS profile, and GeoJSON envelope."""
    mapping = assets_object(
        request,
        AssetGisMapping,
        pk,
        select_related=(
            "connector",
            "operational_asset",
            "location",
            "org_unit",
            "gis_custodian",
        ),
    )
    return render(
        request,
        "assets/integrationapihub/asset_gis_mapping/detail.html",
        {"mapping": mapping},
    )


@login_required
def mapping_edit(request, pk):
    """Edit an existing GIS Asset Spatial Mapping."""
    mapping = assets_object(request, AssetGisMapping, pk)
    if request.method == "POST":
        form = AssetGisMappingForm(
            request.POST, instance=mapping, tenant=mapping.tenant
        )
        if form.is_valid():
            with transaction.atomic():
                mapping = form.save()
                write_audit_log(
                    request.user,
                    mapping,
                    "update",
                    changes={
                        "number": mapping.number,
                        "drift_status": mapping.drift_status,
                    },
                    tenant=mapping.tenant,
                )
            messages.success(
                request, f"GIS mapping {mapping.number} updated successfully."
            )
            return redirect("assets:asset_gis_mapping_detail", pk=mapping.pk)
    else:
        form = AssetGisMappingForm(instance=mapping, tenant=mapping.tenant)

    return render(
        request,
        "assets/integrationapihub/asset_gis_mapping/form.html",
        {
            "form": form,
            "mapping": mapping,
            "is_edit": True,
            "title": f"Edit {mapping.number} — {mapping.layer_name}",
        },
    )


@login_required
@require_POST
def mapping_delete(request, pk):
    """Delete a tenant-scoped Asset GIS Mapping."""
    mapping = assets_object(request, AssetGisMapping, pk)
    label = str(mapping)
    with transaction.atomic():
        write_audit_log(
            request.user,
            mapping,
            "delete",
            changes={
                "number": mapping.number,
                "external_feature_id": mapping.external_feature_id,
            },
            tenant=mapping.tenant,
        )
        mapping.delete()
    messages.success(request, f"GIS mapping {label} deleted.")
    return redirect("assets:asset_gis_mapping_list")


@login_required
@require_POST
def verify_spatial_sync(request, pk):
    """Verify spatial coordinates / LRS / asset linkage and update drift status locally."""
    mapping = assets_object(
        request,
        AssetGisMapping,
        pk,
        select_related=("connector", "operational_asset", "location"),
    )
    now = timezone.now()
    new_drift = mapping.compute_spatial_drift_status()

    with transaction.atomic():
        mapping.drift_status = new_drift
        mapping.last_spatial_sync_at = now
        mapping.save(
            update_fields=["drift_status", "last_spatial_sync_at", "updated_at"]
        )
        write_audit_log(
            request.user,
            mapping,
            "verify",
            changes={
                "drift_status": mapping.drift_status,
                "srid": mapping.coordinate_system_srid,
            },
            tenant=mapping.tenant,
        )

    if new_drift == "in_sync":
        messages.success(
            request,
            f"Spatial sync verified for {mapping.number}: coordinates and ERP asset link are In Sync.",
        )
    else:
        messages.warning(
            request,
            f"Spatial check for {mapping.number} flagged {mapping.get_drift_status_display()}.",
        )
    return redirect("assets:asset_gis_mapping_detail", pk=mapping.pk)
