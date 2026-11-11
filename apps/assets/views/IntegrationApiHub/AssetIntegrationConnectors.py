from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnectorForm,
)
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnector,
    validate_connector_endpoint_url,
)
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def connector_list(request):
    """List tenant-scoped Asset Integration Connectors with KPI counts and filters."""
    base_qs = assets_scope(
        AssetIntegrationConnector.objects.select_related(
            "vendor_partner", "default_org_unit", "default_currency", "owner"
        ),
        request,
    )

    kpis = base_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        healthy=Count("id", filter=Q(health_status="healthy")),
        errors=Count(
            "id", filter=Q(status="error") | Q(health_status="unreachable")
        ),
    )

    qs = base_qs
    q = (request.GET.get("q") or "").strip()
    connector_category = (request.GET.get("connector_category") or "").strip()
    provider = (request.GET.get("provider") or "").strip()
    status = (request.GET.get("status") or "").strip()
    health_status = (request.GET.get("health_status") or "").strip()

    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(endpoint_url__icontains=q)
            | Q(api_key_prefix__icontains=q)
        )
    if connector_category in dict(AssetIntegrationConnector.CATEGORY_CHOICES):
        qs = qs.filter(connector_category=connector_category)
    if provider in dict(AssetIntegrationConnector.PROVIDER_CHOICES):
        qs = qs.filter(provider=provider)
    if status in dict(AssetIntegrationConnector.STATUS_CHOICES):
        qs = qs.filter(status=status)
    if health_status in dict(AssetIntegrationConnector.HEALTH_STATUS_CHOICES):
        qs = qs.filter(health_status=health_status)

    paginator = Paginator(qs.order_by("number"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "connectors": page_obj,
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": kpis["total"] or 0,
        "active_count": kpis["active"] or 0,
        "healthy_count": kpis["healthy"] or 0,
        "error_count": kpis["errors"] or 0,
        "category_choices": AssetIntegrationConnector.CATEGORY_CHOICES,
        "provider_choices": AssetIntegrationConnector.PROVIDER_CHOICES,
        "status_choices": AssetIntegrationConnector.STATUS_CHOICES,
        "health_choices": AssetIntegrationConnector.HEALTH_STATUS_CHOICES,
        "search_query": q,
    }
    return render(
        request,
        "assets/integrationapihub/asset_integration_connector/list.html",
        context,
    )


@tenant_admin_required
def connector_create(request):
    """Create a new Asset Integration Connector."""
    if request.tenant is None:
        messages.error(
            request,
            "An active tenant workspace is required to create an integration connector.",
        )
        return redirect("assets:asset_integration_connector_list")
    if request.method == "POST":
        form = AssetIntegrationConnectorForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                connector = form.save(commit=False)
                connector.tenant = request.tenant
                connector.save()
                write_audit_log(
                    request.user,
                    connector,
                    "create",
                    changes={
                        "number": connector.number,
                        "category": connector.connector_category,
                        "provider": connector.provider,
                    },
                    tenant=request.tenant,
                )
            messages.success(
                request, f"Connector {connector.number} created successfully."
            )
            return redirect(
                "assets:asset_integration_connector_detail", pk=connector.pk
            )
    else:
        form = AssetIntegrationConnectorForm(tenant=request.tenant)

    return render(
        request,
        "assets/integrationapihub/asset_integration_connector/form.html",
        {
            "form": form,
            "connector": None,
            "is_edit": False,
            "title": "New Integration Connector",
        },
    )


@login_required
def connector_detail(request, pk):
    """Display connector details, one-time rotated secret reveal, and linked children."""
    connector = assets_object(
        request,
        AssetIntegrationConnector,
        pk,
        select_related=(
            "vendor_partner",
            "default_org_unit",
            "default_currency",
            "owner",
        ),
    )

    plaintext_once = None
    reveal = request.session.get("_aicn_secret_reveal")
    if isinstance(reveal, dict) and reveal.get("pk") == connector.pk:
        request.session.pop("_aicn_secret_reveal", None)
        plaintext_once = reveal.get("secret")

    streams = connector.telemetry_streams.select_related(
        "operational_asset", "fixed_asset"
    ).order_by("number")[:10]
    gl_batches = connector.gl_sync_batches.select_related(
        "fiscal_period", "journal_entry"
    ).order_by("-batch_date", "-number")[:10]
    gis_mappings = connector.gis_mappings.select_related(
        "operational_asset", "location"
    ).order_by("number")[:10]

    return render(
        request,
        "assets/integrationapihub/asset_integration_connector/detail.html",
        {
            "connector": connector,
            "plaintext_once": plaintext_once,
            "streams": streams,
            "gl_batches": gl_batches,
            "gis_mappings": gis_mappings,
        },
    )


@tenant_admin_required
def connector_edit(request, pk):
    """Edit an existing Asset Integration Connector."""
    connector = assets_object(request, AssetIntegrationConnector, pk)
    if request.method == "POST":
        form = AssetIntegrationConnectorForm(
            request.POST, instance=connector, tenant=connector.tenant
        )
        if form.is_valid():
            with transaction.atomic():
                connector = form.save()
                write_audit_log(
                    request.user,
                    connector,
                    "update",
                    changes={"number": connector.number, "status": connector.status},
                    tenant=connector.tenant,
                )
            messages.success(
                request, f"Connector {connector.number} updated successfully."
            )
            return redirect(
                "assets:asset_integration_connector_detail", pk=connector.pk
            )
    else:
        form = AssetIntegrationConnectorForm(
            instance=connector, tenant=connector.tenant
        )

    return render(
        request,
        "assets/integrationapihub/asset_integration_connector/form.html",
        {
            "form": form,
            "connector": connector,
            "is_edit": True,
            "title": f"Edit {connector.number} — {connector.name}",
        },
    )


@tenant_admin_required
@require_POST
def connector_delete(request, pk):
    """Delete an Asset Integration Connector unless protected children exist."""
    connector = assets_object(request, AssetIntegrationConnector, pk)
    label = str(connector)
    try:
        with transaction.atomic():
            write_audit_log(
                request.user,
                connector,
                "delete",
                changes={"number": connector.number, "name": connector.name},
                tenant=connector.tenant,
            )
            connector.delete()
    except ProtectedError:
        messages.error(
            request,
            f"Cannot delete {connector.number}: linked telemetry streams, GL sync batches, or GIS mappings still reference it.",
        )
        return redirect(
            "assets:asset_integration_connector_detail", pk=connector.pk
        )

    messages.success(request, f"Connector {label} deleted.")
    return redirect("assets:asset_integration_connector_list")


@login_required
@require_POST
def test_connection(request, pk):
    """Validate connector URI & configuration locally (zero outbound HTTP) and log heartbeat."""
    connector = assets_object(request, AssetIntegrationConnector, pk)
    now = timezone.now()

    try:
        validate_connector_endpoint_url(connector.endpoint_url)
    except ValidationError as exc:
        with transaction.atomic():
            connector.health_status = "unreachable"
            connector.last_heartbeat_at = now
            connector.consecutive_failures = (connector.consecutive_failures or 0) + 1
            connector.last_error_message = "; ".join(exc.messages)
            connector.save(
                update_fields=[
                    "health_status",
                    "last_heartbeat_at",
                    "consecutive_failures",
                    "last_error_message",
                    "updated_at",
                ]
            )
            write_audit_log(
                request.user,
                connector,
                "test",
                changes={
                    "health_status": connector.health_status,
                    "error": connector.last_error_message,
                },
                tenant=connector.tenant,
            )
        messages.error(
            request,
            f"Connection check failed for {connector.number}: {connector.last_error_message}",
        )
        return redirect("assets:asset_integration_connector_detail", pk=connector.pk)

    with transaction.atomic():
        if connector.status in ("paused", "decommissioned"):
            connector.health_status = "degraded"
            connector.last_heartbeat_at = now
            connector.last_error_message = (
                f"Connector status is {connector.get_status_display()}; probe marked degraded."
            )
        else:
            connector.health_status = "healthy"
            connector.last_heartbeat_at = now
            connector.consecutive_failures = 0
            connector.last_error_message = ""
        connector.save(
            update_fields=[
                "health_status",
                "last_heartbeat_at",
                "consecutive_failures",
                "last_error_message",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            connector,
            "test",
            changes={"health_status": connector.health_status},
            tenant=connector.tenant,
        )

    messages.success(
        request,
        f"Endpoint configuration check completed for {connector.number}: {connector.get_health_status_display()}.",
    )
    return redirect("assets:asset_integration_connector_detail", pk=connector.pk)


@tenant_admin_required
@require_POST
def rotate_secret(request, pk):
    """Rotate connector credential (admin only), storing prefix + SHA-256 hash and revealing once."""
    connector = assets_object(request, AssetIntegrationConnector, pk)
    with transaction.atomic():
        plaintext = connector.issue_new_secret()
        connector.save(
            update_fields=["api_key_prefix", "api_key_hash", "updated_at"]
        )
        write_audit_log(
            request.user,
            connector,
            "rotate",
            changes={"api_key_prefix": connector.api_key_prefix},
            tenant=connector.tenant,
        )

    request.session["_aicn_secret_reveal"] = {
        "pk": connector.pk,
        "secret": plaintext,
    }
    messages.success(
        request,
        f"Credential rotated for {connector.number} (prefix {connector.api_key_prefix}). Copy the one-time secret below.",
    )
    return redirect("assets:asset_integration_connector_detail", pk=connector.pk)
