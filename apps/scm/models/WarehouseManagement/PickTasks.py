"""SCM 4.4 Warehouse Management — PickTask + PickTaskLine.

The outbound half: pick stock from bins, then pack it. Picking posts an ``issue`` move per line
through the 4.3 service, so on-hand falls exactly as the ledger says and never via a stored field.

Scope boundary: this pass has no outbound demand document to hang picks off — ``SalesOrder`` belongs
to Module 8 and is not built. A pick task therefore stands alone and records what was picked; when
Sales lands, `PickTask` gains a nullable FK to the order rather than being rebuilt.

Packing captures label DATA (package count, weight, a carrier tracking reference typed in by the
packer). Actual label rendering and carrier integration are 4.6 TMS — this stops at the hand-off.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class PickTask(TenantNumbered):
    """A pick (and pack) instruction covering one or more lines [PIK-]."""

    NUMBER_PREFIX = "PIK"

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("released", "Released"),
        ("picking", "Picking"),
        ("picked", "Picked"),
        ("packed", "Packed"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("pending", "released")
    # Statuses from which the stock-moving "confirm pick" step may run.
    PICKABLE_STATUSES = ("released", "picking")

    STRATEGY_CHOICES = [
        ("single", "Single Order"),
        ("wave", "Wave"),
        ("batch", "Batch"),
        ("zone", "Zone"),
    ]

    strategy = models.CharField(max_length=8, choices=STRATEGY_CHOICES, default="single")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    zone = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="pick_tasks",
                             help_text="Zone this pick is confined to (zone picking)")
    wave_ref = models.CharField(max_length=40, blank=True,
                                help_text="Groups tasks released together as one wave")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="scm_pick_tasks")
    ship_to = models.CharField(max_length=255, blank=True, help_text="Free-text destination for now")

    # --- packing / label data (4.6 TMS renders the actual label) ---------------------------
    package_count = models.PositiveIntegerField(null=True, blank=True)
    package_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True,
                                         validators=[MinValueValidator(ZERO)])
    tracking_ref = models.CharField(max_length=64, blank=True,
                                    help_text="Carrier tracking reference (recorded, not generated)")
    picked_at = models.DateTimeField(null=True, blank=True, editable=False)
    packed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_pik_tnt_status_idx"),
            models.Index(fields=["tenant", "wave_ref"], name="scm_pik_tnt_wave_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    def line_count(self):
        return self.lines.count()

    def is_short(self):
        """True when any line picked less than it asked for — a short pick worth surfacing."""
        return any(l.quantity_picked < l.quantity_requested for l in self.lines.all())

    def __str__(self):
        return f"{self.number or 'PIK'} · {self.get_strategy_display()}"


class PickTaskLine(models.Model):
    """One item to pick from one bin. ``quantity_picked`` may fall short of requested."""

    pick_task = models.ForeignKey("scm.PickTask", on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="pick_lines")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="pick_lines")
    from_location = models.ForeignKey("scm.Location", on_delete=models.PROTECT,
                                      related_name="pick_lines", help_text="Bin to pick from")
    quantity_requested = models.DecimalField(max_digits=16, decimal_places=4,
                                             validators=[MinValueValidator(Decimal("0.0001"))])
    quantity_picked = models.DecimalField(max_digits=16, decimal_places=4, default=0,
                                          validators=[MinValueValidator(ZERO)])
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        # Walk order: honour the bin's pick_sequence so a picker isn't sent back and forth.
        ordering = ["from_location__pick_sequence", "from_location__code", "id"]

    @property
    def shortfall(self):
        return (self.quantity_requested or ZERO) - (self.quantity_picked or ZERO)

    def __str__(self):
        return f"{self.item_id and self.item.sku} ×{self.quantity_requested}"
