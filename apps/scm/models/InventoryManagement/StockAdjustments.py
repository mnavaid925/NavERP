"""SCM 4.3 Inventory Management — StockAdjustment + StockAdjustmentLine.

A reason-coded correction to stock at one location: write-offs, damage, cycle-count corrections,
found stock, or a revaluation. Posting an adjustment writes one StockMove per line (signed
``quantity_delta``) inside an atomic block. Never edited once posted — a further correction is a new
adjustment, keeping the StockMove ledger append-only.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class StockAdjustment(TenantNumbered):
    """A stock adjustment at a location [ADJ-]."""

    NUMBER_PREFIX = "ADJ"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("draft",)

    REASON_CHOICES = [
        ("cycle_count", "Cycle Count Correction"),
        ("write_off", "Write-Off"),
        ("damage", "Damage"),
        ("found", "Found Stock"),
        ("revaluation", "Revaluation"),
        ("other", "Other"),
    ]

    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, related_name="adjustments")
    reason = models.CharField(max_length=16, choices=REASON_CHOICES, default="cycle_count")
    adjustment_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    posted_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-adjustment_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="scm_adj_tnt_status_idx")]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    def value_impact(self):
        """Net value change if posted (Σ quantity_delta × unit_cost across lines)."""
        total = ZERO
        for line in self.lines.all():
            total += (line.quantity_delta or ZERO) * (line.unit_cost or ZERO)
        return total.quantize(Decimal("0.01"))

    def clean(self):
        super().clean()
        # A cycle-count/write-off/other adjustment should say WHY beyond the reason code.
        if self.reason == "other" and not (self.notes or "").strip():
            raise ValidationError({"notes": "Give a note explaining an 'Other' adjustment."})

    def __str__(self):
        return f"{self.number or 'ADJ'} · {self.get_reason_display()}"


class StockAdjustmentLine(models.Model):
    """One item's signed correction. ``quantity_delta`` +adds / −removes; ``unit_cost`` values it."""

    adjustment = models.ForeignKey("scm.StockAdjustment", on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="adjustment_lines")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="adjustment_lines")
    quantity_delta = models.DecimalField(max_digits=16, decimal_places=4,
                                         help_text="Signed: positive adds stock, negative removes it")
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                    validators=[MinValueValidator(ZERO)])

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.item_id and self.item.sku} Δ{self.quantity_delta}"
