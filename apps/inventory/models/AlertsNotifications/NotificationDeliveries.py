"""Inventory 5.16 Alerts & Notifications — NotificationDelivery [NDL-].

The append-only DISPATCH LOG: one row per (raised alert × channel × recipient), written
only by the detection engine when an alert is raised. No edit and no delete views —
the same posture as ``scm.TrackingEvent`` / the ``StockMove`` ledger: a delivery record
is a fact about what the engine queued, and rewriting history would defeat the audit.

# WARNING: no SMTP/SMS/push gateway is integrated yet, so rows are created with status
# "queued" and stay there — that is the honest state of an unconfigured transport. The
# in-app inbox IS live (the alert list/detail pages); everything else waits on a gateway.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class NotificationDelivery(TenantOwned):
    """One queued notification [NDL-] for one channel/recipient of one alert."""

    CHANNEL_CHOICES = [
        ("in_app", "In-App"),
        ("email", "Email"),
        ("sms", "SMS"),
        ("push", "Push"),
    ]
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    #: Placeholder recipient for broadcast channels that have no per-person address yet.
    BROADCAST = "(broadcast)"

    alert = models.ForeignKey(
        "inventory.InventoryAlert", on_delete=models.CASCADE, related_name="deliveries",
        help_text="The alert this dispatch belongs to")
    channel = models.CharField(max_length=8, choices=CHANNEL_CHOICES)
    recipient = models.CharField(
        max_length=255,
        help_text="Email address, number or token; '(broadcast)' for inbox-wide channels")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="queued")
    detail = models.CharField(max_length=255, blank=True,
                              help_text="Gateway note — e.g. why a delivery is still queued")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "channel", "status"], name="inv_ndl_tnt_chan_idx"),
        ]

    def __str__(self):
        return f"{self.alert_id} · {self.channel} → {self.recipient}"
