"""SCM 4.4 Warehouse Management — YardVisit.

Tracks a truck/trailer through the yard: scheduled → arrived → at a dock door → departed. Purely a
movement-of-vehicles record — it posts NO StockMove (the goods themselves move via the receipt and
putaway path).

``carrier_name`` is free text on purpose: a real `Carrier` master belongs to 4.6 TMS, which isn't
built. When it lands this gains a nullable FK rather than being rebuilt (the same stand-in pattern
4.1's line items used before the item master existed, lesson L28).
"""
from apps.scm.models._base import *  # noqa: F401,F403


class YardVisit(TenantNumbered):
    """One vehicle's visit to the yard [YRD-]."""

    NUMBER_PREFIX = "YRD"

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("arrived", "Arrived"),
        ("at_dock", "At Dock"),
        ("departed", "Departed"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("scheduled", "arrived", "at_dock")
    OPEN_STATUSES = ("scheduled", "arrived", "at_dock")

    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]

    carrier_name = models.CharField(max_length=255, help_text="Haulier (free text until 4.6 TMS)")
    vehicle_ref = models.CharField(max_length=64, blank=True, help_text="Truck / tractor registration")
    trailer_ref = models.CharField(max_length=64, blank=True)
    driver_name = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=8, choices=DIRECTION_CHOICES, default="inbound")
    dock_door = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="yard_visits", help_text="Dock door assigned")
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="yard_visits",
                                       help_text="Inbound load this vehicle is delivering")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="scheduled")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True, editable=False)
    docked_at = models.DateTimeField(null=True, blank=True, editable=False)
    departed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_yrd_tnt_status_idx"),
            models.Index(fields=["tenant", "direction"], name="scm_yrd_tnt_dir_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    def dwell_minutes(self):
        """Minutes on site (arrival → departure, or → now while still here). None before arrival."""
        if not self.arrived_at:
            return None
        end = self.departed_at or timezone.now()
        return int((end - self.arrived_at).total_seconds() // 60)

    def __str__(self):
        return f"{self.number or 'YRD'} · {self.carrier_name}"
