"""SCM 4.4 Warehouse Management — CycleCountTask + CycleCountTaskLine.

Scheduled counting of a warehouse section without halting operations. This is the SCHEDULING and
EXECUTION layer only: reconciling a completed count generates exactly one
``scm.StockAdjustment(reason="cycle_count")`` and posts it through the existing 4.3 adjustment path.
There is deliberately no second correction route — one way for stock to change, always the ledger.

``expected_quantity`` is snapshotted SERVER-SIDE when the count starts, not typed by the counter and
not read back at reconcile time. A blind count that let the counter see (or re-derive) the expected
figure is not a count; and re-deriving it at reconcile would silently absorb any movement that
happened mid-count, hiding the very discrepancy the count exists to find.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class CycleCountTask(TenantNumbered):
    """A scheduled count of one location's stock [CC-]."""

    NUMBER_PREFIX = "CC"

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("counted", "Counted"),
        ("reconciled", "Reconciled"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("scheduled", "in_progress")

    METHOD_CHOICES = [
        ("full", "Full Count"),
        ("abc", "ABC Class"),
        ("random", "Random Sample"),
        ("zone", "Zone"),
    ]

    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, related_name="cycle_counts",
                                 help_text="The section being counted")
    scheduled_date = models.DateField()
    count_method = models.CharField(max_length=8, choices=METHOD_CHOICES, default="full")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="scheduled")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="scm_cycle_counts")
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    counted_at = models.DateTimeField(null=True, blank=True, editable=False)
    reconciled_at = models.DateTimeField(null=True, blank=True, editable=False)
    # The single adjustment this count produced — the audit link from "we counted" to "stock changed".
    adjustment = models.ForeignKey("scm.StockAdjustment", on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="cycle_counts", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_cc_tnt_status_idx"),
            models.Index(fields=["tenant", "scheduled_date"], name="scm_cc_tnt_date_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    def variance_count(self):
        """How many counted lines disagree with what the ledger expected."""
        return sum(1 for line in self.lines.all() if line.has_variance)

    def has_variance(self):
        return self.variance_count() > 0

    def net_variance(self):
        """Σ (counted − expected) across counted lines — the net quantity the count would correct."""
        total = ZERO
        for line in self.lines.all():
            if line.counted_quantity is not None:
                total += line.variance
        return total

    def __str__(self):
        loc = self.location.code if self.location_id else "?"
        return f"{self.number or 'CC'} · {loc}"


class CycleCountTaskLine(models.Model):
    """One item on a count sheet: what the ledger expected vs what was physically counted."""

    cycle_count = models.ForeignKey("scm.CycleCountTask", on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="cycle_count_lines")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="cycle_count_lines")
    # Snapshotted from the derived on-hand when the count is started — never editable by the counter.
    expected_quantity = models.DecimalField(max_digits=16, decimal_places=4, default=0, editable=False)
    # Null until physically counted, so "not yet counted" is distinguishable from "counted zero".
    counted_quantity = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True,
                                           validators=[MinValueValidator(ZERO)])
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["item__sku", "id"]

    @property
    def variance(self):
        """counted − expected. Zero while uncounted (not a phantom shortfall)."""
        if self.counted_quantity is None:
            return ZERO
        return self.counted_quantity - (self.expected_quantity or ZERO)

    @property
    def has_variance(self):
        return self.counted_quantity is not None and self.variance != ZERO

    def __str__(self):
        return f"{self.item_id and self.item.sku}: expected {self.expected_quantity}"
