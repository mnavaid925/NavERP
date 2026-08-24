"""Inventory 5.19 Third-Party Integrations & API — ChannelListingMap views.

Listing maps are staff-level plumbing: every signed-in member reads AND writes them
(deliberate contract ruling — NOT admin-gated, unlike the channel register). The list is a
filtering surface over high-volume rows: search across both sides of the mapping, lens by
channel (deep-linked from the channel detail page) and by sync Enabled/Paused.
"""
from django.db.models import Count

from apps.core.crud import as_db_int
from apps.inventory.forms.ThirdPartyIntegrations.ChannelListingMaps import ChannelListingMapForm
from apps.inventory.models.ThirdPartyIntegrations.ChannelListingMaps import ChannelListingMap
from apps.inventory.models.ThirdPartyIntegrations.IntegrationChannels import IntegrationChannel
from apps.inventory.views._common import *  # noqa: F401,F403


def _is_admin(user):
    """The one admin flag every 5.19 template receives — same test as the decorator."""
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


@login_required
def listingmap_list(request):
    """List listing maps with search, channel/sync lenses and a KPI strip."""
    qs = ChannelListingMap.objects.filter(tenant=request.tenant).select_related(
        "channel", "item", "location"
    )

    # KPIs across the tenant's full register — one grouped query, not three COUNTs.
    sync_counts = {
        row["sync_enabled"]: row["n"]
        for row in ChannelListingMap.objects.filter(tenant=request.tenant)
        .values("sync_enabled")
        .annotate(n=Count("id"))
    }
    stats = {
        "total": sum(sync_counts.values()),
        "enabled": sync_counts.get(True, 0),
        "paused": sync_counts.get(False, 0),
    }

    # FK filter parsed via as_db_int and validated against THIS tenant's channels, so a junk or
    # foreign pk falls back to unfiltered with no echoed selection instead of a silently empty list.
    channel_choices = [
        (c.pk, str(c))
        for c in IntegrationChannel.objects.filter(tenant=request.tenant).order_by("name")
    ]
    channel = ""
    channel_id = as_db_int(request.GET.get("channel"))
    if channel_id is not None:
        if any(pk == channel_id for pk, _label in channel_choices):
            qs = qs.filter(channel_id=channel_id)
            channel = str(channel_id)

    # Boolean lens BEFORE pagination; junk values fall back to "" rather than filtering.
    enabled = request.GET.get("sync_enabled", "").strip()
    if enabled == "true":
        qs = qs.filter(sync_enabled=True)
    elif enabled == "false":
        qs = qs.filter(sync_enabled=False)
    else:
        enabled = ""

    return crud_list(
        request,
        qs,
        "inventory/integration/listingmap/list.html",
        search_fields=["external_sku", "external_variant_id", "item__sku", "channel__name"],
        filters=(),
        extra_context={
            "stats": stats,
            "channel_choices": channel_choices,
            "channel": channel,
            "enabled_choices": [("true", "Enabled"), ("false", "Paused")],
            "enabled": enabled,
            "is_admin": _is_admin(request.user),
        },
    )


@login_required
def listingmap_detail(request, pk):
    """View one mapping with its channel/item/location resolved."""
    obj = get_object_or_404(
        ChannelListingMap.objects.filter(tenant=request.tenant).select_related(
            "channel", "item", "location"
        ),
        pk=pk,
    )
    return render(
        request,
        "inventory/integration/listingmap/detail.html",
        {
            "obj": obj,
            "is_admin": _is_admin(request.user),
        },
    )


@login_required
def listingmap_create(request):
    """Create a listing map (staff-level — deliberately NOT admin-gated)."""
    return crud_create(
        request,
        form_class=ChannelListingMapForm,
        template="inventory/integration/listingmap/form.html",
        success_url="inventory:listingmap_list",
    )


@login_required
def listingmap_edit(request, pk):
    """Edit a listing map (staff-level — deliberately NOT admin-gated)."""
    return crud_edit(
        request,
        model=ChannelListingMap,
        pk=pk,
        form_class=ChannelListingMapForm,
        template="inventory/integration/listingmap/form.html",
        success_url="inventory:listingmap_list",
    )


@login_required
@require_POST
def listingmap_delete(request, pk):
    """Delete a listing map record."""
    return crud_delete(
        request,
        model=ChannelListingMap,
        pk=pk,
        success_url="inventory:listingmap_list",
    )
