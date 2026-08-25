"""Inventory 5.16 Alerts & Notifications — NotificationDelivery views (append-only).

No edit/delete/create routes on purpose: a delivery row is what the engine queued at
raise time. Rewriting it would forge the dispatch history (see the model docstring).
"""
from apps.inventory.models.AlertsNotifications.NotificationDeliveries import (
    NotificationDelivery,
)
from apps.inventory.views._common import *  # noqa: F401,F403


@login_required
def delivery_list(request):
    """The dispatch log across all alerts of this workspace."""
    qs = (NotificationDelivery.objects.filter(tenant=request.tenant)
          .select_related("alert"))

    valid_channels = dict(NotificationDelivery.CHANNEL_CHOICES)
    valid_statuses = dict(NotificationDelivery.STATUS_CHOICES)

    channel = request.GET.get("channel", "").strip()
    if channel and channel not in valid_channels:
        channel = ""
    if channel:
        qs = qs.filter(channel=channel)

    status = request.GET.get("status", "").strip()
    if status and status not in valid_statuses:
        status = ""
    if status:
        qs = qs.filter(status=status)

    return crud_list(
        request,
        qs,
        "inventory/alerts/notificationdelivery/list.html",
        search_fields=["recipient", "detail", "alert__number", "alert__title"],
        filters=(),
        extra_context={
            "channel_choices": NotificationDelivery.CHANNEL_CHOICES,
            "status_choices": NotificationDelivery.STATUS_CHOICES,
            "channel": channel,
            "status": status,
        },
    )


@login_required
def delivery_detail(request, pk):
    """One queued dispatch."""
    return crud_detail(
        request,
        model=NotificationDelivery,
        pk=pk,
        template="inventory/alerts/notificationdelivery/detail.html",
        select_related=("alert",),
        extra_context={},
    )
