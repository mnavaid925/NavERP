from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class ProductRecall(TenantNumbered):
    NUMBER_PREFIX = "QRCL"

    RECALL_CLASS_CHOICES = [
        ("class_i", "Class I — Serious Threat / Death Risk"),
        ("class_ii", "Class II — Temporary / Reversible Risk"),
        ("class_iii", "Class III — Violation without Adverse Effect"),
        ("market_withdrawal", "Market Withdrawal (Minor)"),
        ("safety_alert", "Safety Alert / Field Notice"),
    ]

    RECALL_STATUS_CHOICES = [
        ("initiated", "Recall Initiated"),
        ("containment_hold", "Containment Hold Active"),
        ("notification_sent", "Consignee Notifications Sent"),
        ("recovery_in_progress", "Product Recovery In Progress"),
        ("effectiveness_check", "Effectiveness Check Review"),
        ("completed", "Recall Execution Completed"),
        ("terminated", "Formally Terminated / Closed"),
    ]

    RECALL_CLASS_CSS = {
        "class_i": "badge-red",
        "class_ii": "badge-amber",
        "class_iii": "badge-info",
        "market_withdrawal": "badge-slate",
        "safety_alert": "badge-amber",
    }

    RECALL_STATUS_CSS = {
        "initiated": "badge-amber",
        "containment_hold": "badge-red",
        "notification_sent": "badge-info",
        "recovery_in_progress": "badge-amber",
        "effectiveness_check": "badge-info",
        "completed": "badge-green",
        "terminated": "badge-slate",
    }

    title = models.CharField(max_length=255)
    recall_class = models.CharField(max_length=25, choices=RECALL_CLASS_CHOICES, default="class_ii", db_index=True)
    status = models.CharField(max_length=25, choices=RECALL_STATUS_CHOICES, default="initiated", db_index=True)
    is_mock_recall = models.BooleanField(default=False, help_text="Mock recall drill for audit readiness")
    mock_drill_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Elapsed time in hours to complete trace (target < 4.0h)",
    )
    item_code = models.CharField(max_length=100, db_index=True)
    item_name = models.CharField(max_length=255)
    affected_lot_numbers = models.TextField(help_text="Affected batch and lot numbers")
    affected_serial_range = models.CharField(max_length=255, blank=True)
    hazard_summary = models.TextField()
    root_cause = models.TextField(blank=True)
    customer_complaint = models.ForeignKey(
        "quality.CustomerComplaint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_recalls",
    )
    capa_investigation = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_recalls",
    )
    total_distributed_qty = models.PositiveIntegerField(default=0)
    total_quarantined_qty = models.PositiveIntegerField(default=0)
    total_recovered_qty = models.PositiveIntegerField(default=0)
    total_destroyed_qty = models.PositiveIntegerField(default=0)
    recovery_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    regulatory_agency_notified = models.CharField(max_length=100, blank=True)
    regulatory_notification_date = models.DateField(null=True, blank=True)
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coordinated_recalls",
    )
    closure_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_recalls",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Product Recall"
        verbose_name_plural = "Product Recalls"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qrcl_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "recall_class"], name="idx_qrcl_ten_class"),
            models.Index(fields=["tenant", "status"], name="idx_qrcl_ten_status"),
            models.Index(fields=["tenant", "is_mock_recall"], name="idx_qrcl_ten_mock"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_recall_class_display()})"

    def save(self, *args, **kwargs):
        if self.total_distributed_qty and self.total_distributed_qty > 0:
            self.recovery_rate_pct = (
                (Decimal(str(self.total_recovered_qty)) / Decimal(str(self.total_distributed_qty))) * Decimal("100.00")
            ).quantize(Decimal("0.01"))
        else:
            self.recovery_rate_pct = Decimal("0.00")
        super().save(*args, **kwargs)
