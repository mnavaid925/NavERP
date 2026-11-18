from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class QuarantineContainment(TenantNumbered):
    NUMBER_PREFIX = "QCNT"

    HOLD_TYPE_CHOICES = (
        ("physical_quarantine", "Physical Quarantine Cage / Bin"),
        ("digital_hold", "Digital System / ERP Hold"),
        ("stop_shipment", "Stop Shipment Notice"),
        ("stop_production", "Stop Production Order"),
    )

    STATUS_CHOICES = (
        ("active", "Active Hold"),
        ("partially_released", "Partially Released"),
        ("released", "Fully Released"),
        ("disposed", "Disposed / Scrapped"),
    )

    HOLD_TYPE_CSS = {
        "physical_quarantine": "badge-amber",
        "digital_hold": "badge-info",
        "stop_shipment": "badge-red",
        "stop_production": "badge-red",
    }

    STATUS_CSS = {
        "active": "badge-red",
        "partially_released": "badge-amber",
        "released": "badge-green",
        "disposed": "badge-slate",
    }

    ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.CASCADE,
        related_name="containment_records",
    )
    title = models.CharField(max_length=255)
    hold_type = models.CharField(
        max_length=24,
        choices=HOLD_TYPE_CHOICES,
        default="physical_quarantine",
        db_index=True,
    )
    quarantine_location = models.CharField(
        max_length=150,
        help_text="Quarantine storage location or holding bin",
    )
    red_tag_number = models.CharField(
        max_length=64,
        blank=True,
        help_text="Physical red tag identifier attached to items",
    )
    quantity_on_hold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    unit_of_measure = models.CharField(max_length=32, default="EA", blank=True)
    hold_date = models.DateField(default=timezone.now)
    hold_applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="applied_quarantines",
    )
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )
    release_criteria = models.TextField(
        blank=True,
        help_text="Conditions required before lifting quarantine",
    )
    released_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    release_date = models.DateField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="released_quarantines",
    )
    disposition_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Quarantine & Containment Record"
        verbose_name_plural = "Quarantine & Containment Records"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qcnt_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qcnt_ten_status"),
            models.Index(fields=["tenant", "hold_type"], name="idx_qcnt_ten_hold_type"),
            models.Index(fields=["tenant", "ncr"], name="idx_qcnt_ten_ncr"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qcnt_ten_created"),
        ]

    def __str__(self):
        return f"{self.number or 'Draft'} - {self.title}"

    @property
    def hold_type_badge(self):
        return self.HOLD_TYPE_CSS.get(self.hold_type, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def remaining_on_hold(self):
        return max(Decimal("0.00"), self.quantity_on_hold - self.released_quantity)
