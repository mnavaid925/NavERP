"""Inventory 5.19 Third-Party Integrations & API — IntegrationChannel views.

CRUD plus the two admin POST verbs: ``rotate-key`` (new plaintext revealed exactly ONCE in
the flash message — only prefix+hash persist) and ``sync`` (records a SIMULATED
StockSyncRun through ``StockSyncRun.record`` — nothing leaves the process and NO stock,
``last_sync_at`` or accounting row is ever touched).
"""
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.decorators import tenant_admin_required
from apps.inventory.forms.ThirdPartyIntegrations.IntegrationChannels import IntegrationChannelForm
from apps.inventory.models.ThirdPartyIntegrations._choices import (
    CHANNEL_KIND_CHOICES,
    CHANNEL_PLATFORM_CHOICES,
    CHANNEL_STATUS_CHOICES,
)
from apps.inventory.models.ThirdPartyIntegrations.IntegrationChannels import IntegrationChannel
from apps.inventory.models.ThirdPartyIntegrations.StockSyncRuns import StockSyncRun
from apps.inventory.views._common import *  # noqa: F401,F403


@login_required
def integrationchannel_list(request):
    """List integration channels with search, kind/platform/status filtering and a KPI strip."""
    qs = IntegrationChannel.objects.filter(tenant=request.tenant).select_related("default_location")

    # Search & filters — junk GET values (status=zzz) fall back to "" instead of echoing back
    # into context and rendering a silently empty register. All applied PRE-pagination.
    valid_kinds = dict(CHANNEL_KIND_CHOICES)
    valid_platforms = dict(CHANNEL_PLATFORM_CHOICES)
    valid_statuses = dict(CHANNEL_STATUS_CHOICES)

    kind = request.GET.get("kind", "").strip()
    if kind and kind not in valid_kinds:
        kind = ""
    if kind:
        qs = qs.filter(kind=kind)

    platform = request.GET.get("platform", "").strip()
    if platform and platform not in valid_platforms:
        platform = ""
    if platform:
        qs = qs.filter(platform=platform)

    status = request.GET.get("status", "").strip()
    if status and status not in valid_statuses:
        status = ""
    if status:
        qs = qs.filter(status=status)

    # KPIs across the tenant's full channel register — one grouped query, not four COUNTs.
    status_counts = {
        row["status"]: row["n"]
        for row in IntegrationChannel.objects.filter(tenant=request.tenant)
        .values("status")
        .annotate(n=Count("id"))
    }
    stats = {
        "total": sum(status_counts.values()),
        "connected": status_counts.get("connected", 0),
        "error": status_counts.get("error", 0),
        "disabled": status_counts.get("disabled", 0),
    }

    return crud_list(
        request,
        qs,
        "inventory/integration/channel/list.html",
        search_fields=["name", "external_account_ref", "platform", "default_location__code"],
        filters=(),
        extra_context={
            "stats": stats,
            "kind_choices": CHANNEL_KIND_CHOICES,
            "kind": kind,
            "platform_choices": CHANNEL_PLATFORM_CHOICES,
            "platform": platform,
            "status_choices": CHANNEL_STATUS_CHOICES,
            "status": status,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def integrationchannel_detail(request, pk):
    """View a connection: config, masked credential chip, listing map and recent sync runs.

    Hand-rolled render rather than crud_detail (the scm ``webhookdelivery_detail`` shape): the
    panels hang off the PINNED ``obj.listings`` / ``obj.runs`` related managers, so they can only
    be built AFTER the object is fetched — evaluating them as ``extra_context`` ahead of a
    possible 404 spent queries on every miss. Same tenant-scoped fetch, same context keys.
    """
    obj = get_object_or_404(
        IntegrationChannel.objects.filter(tenant=request.tenant).select_related("default_location"),
        pk=pk,
    )
    # Rows are high-volume BY DESIGN: the panel renders a capped slice and the header chip reads a
    # cheap count() instead of materializing the whole queryset through |length.
    listings = obj.listings.select_related("item", "location").order_by("external_sku", "id")
    return render(
        request,
        "inventory/integration/channel/detail.html",
        {
            "obj": obj,
            "listings": listings[:25],
            "listings_total": listings.count(),
            "runs": obj.runs.order_by("-started_at", "-id")[:10],
            "run_stats": _run_stats(obj),
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
def integrationchannel_create(request):
    """Register a new external connection."""
    return crud_create(
        request,
        form_class=IntegrationChannelForm,
        template="inventory/integration/channel/form.html",
        success_url="inventory:integrationchannel_list",
    )


@tenant_admin_required
def integrationchannel_edit(request, pk):
    """Edit an existing connection registration."""
    return crud_edit(
        request,
        model=IntegrationChannel,
        pk=pk,
        form_class=IntegrationChannelForm,
        template="inventory/integration/channel/form.html",
        success_url="inventory:integrationchannel_list",
    )


@tenant_admin_required
@require_POST
def integrationchannel_delete(request, pk):
    """Delete a connection registration."""
    return crud_delete(
        request,
        model=IntegrationChannel,
        pk=pk,
        success_url="inventory:integrationchannel_list",
    )


@tenant_admin_required
@require_POST
def integrationchannel_rotate_key(request, pk):
    """Issue a fresh API key: plaintext shown exactly ONCE, only prefix+hash persisted."""
    obj = get_object_or_404(IntegrationChannel, pk=pk, tenant=request.tenant)
    plaintext = obj.generate_api_key()
    obj.set_api_key(plaintext)
    obj.save(update_fields=["api_key_prefix", "api_key_hash", "updated_at"])
    # Audit WITHOUT the plaintext (the immutable trail must never hold a credential).
    write_audit_log(request.user, obj, "update", {"action": "rotate_api_key"})
    messages.success(
        request,
        f"New API key for {obj.number} (copy it now — it will not be shown again): {plaintext}",
    )
    return redirect("inventory:integrationchannel_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def integrationchannel_sync(request, pk):
    """Record a SIMULATED outbound push run — nothing is sent anywhere.

    Honesty rules (contract §3): status="simulated" (never plain "success"), only
    ``last_run_status`` is stamped (NEVER ``last_sync_at`` — nothing synced), zero
    StockMoves, zero HTTP.
    """
    obj = get_object_or_404(IntegrationChannel, pk=pk, tenant=request.tenant)
    records_total = obj.listings.filter(sync_enabled=True).count()
    run = StockSyncRun.record(
        tenant=request.tenant,
        channel=obj,
        direction="outbound_push",
        trigger_mode="manual",
        status="simulated",
        records_total=records_total,
        records_ok=0,
        records_failed=0,
        finished_at=timezone.now(),
    )
    obj.last_run_status = "simulated"
    obj.save(update_fields=["last_run_status", "updated_at"])
    write_audit_log(
        request.user, obj, "update", {"action": "sync_simulated", "records_total": records_total}
    )
    messages.success(request, f"{run.number} recorded: simulated — nothing was sent.")
    return redirect("inventory:stocksyncrun_detail", pk=run.pk)


def _run_stats(channel):
    """{total, failed} over one channel's runs — powers the failed-runs deep-link chip.

    ONE grouped aggregate on the channel's own related manager (house style), never two COUNT
    round-trips.
    """
    row = channel.runs.aggregate(
        total=Count("id"),
        failed=Count("id", filter=Q(status="failed")),
    )
    return {key: value or 0 for key, value in row.items()}
