from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class LabTestWorksheet(TenantNumbered):
    NUMBER_PREFIX = "QWKS"

    STATUS_CHOICES = [
        ("assigned", "Assigned / Pending"),
        ("in_progress", "Execution in Progress"),
        ("review_pending", "Pending QA Review"),
        ("approved", "Approved / Closed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    DISPOSITION_CHOICES = [
        ("pending", "Pending Results"),
        ("conforms", "Conforms to Specification"),
        ("oos_flagged", "Out of Specification (OOS)"),
        ("inconclusive", "Inconclusive Run"),
        ("invalid_run", "Invalid Run (Lab Error)"),
    ]

    STATUS_CSS = {
        "assigned": "badge-slate",
        "in_progress": "badge-amber",
        "review_pending": "badge-info",
        "approved": "badge-green",
        "rejected": "badge-red",
        "cancelled": "badge-muted",
    }

    DISPOSITION_CSS = {
        "pending": "badge-slate",
        "conforms": "badge-green",
        "oos_flagged": "badge-red",
        "inconclusive": "badge-amber",
        "invalid_run": "badge-amber",
    }

    title = models.CharField(max_length=255)
    sample = models.ForeignKey(
        "quality.LabSample",
        on_delete=models.CASCADE,
        related_name="test_worksheets",
    )
    specification = models.ForeignKey(
        "quality.LabSpecification",
        on_delete=models.PROTECT,
        related_name="test_worksheets",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="assigned",
        db_index=True,
    )
    disposition = models.CharField(
        max_length=25,
        choices=DISPOSITION_CHOICES,
        default="pending",
        db_index=True,
    )
    assigned_analyst = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_worksheets",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_worksheets",
    )
    scheduled_date = models.DateField(null=True, blank=True)
    execution_date = models.DateField(null=True, blank=True)
    completion_timestamp = models.DateTimeField(null=True, blank=True)
    instrument = models.ForeignKey(
        "quality.CalibrationGage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="test_worksheets",
    )
    instrument_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="e.g. HPLC-03, UV-Vis-01",
    )
    reagent_lot_number = models.CharField(max_length=100, blank=True)
    reagent_expiry_date = models.DateField(null=True, blank=True)
    standards_lot_number = models.CharField(max_length=100, blank=True)
    standards_expiry_date = models.DateField(null=True, blank=True)
    raw_data_summary = models.TextField(
        blank=True,
        help_text="Instrument readings, replicates, peak areas",
    )
    numeric_result = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    qualitative_result = models.CharField(max_length=255, blank=True)
    is_within_specification = models.BooleanField(default=True)
    relative_standard_deviation = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="% RSD of analytical replicates",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_date", "-created_at"]
        verbose_name = "Lab Test Worksheet"
        verbose_name_plural = "Lab Test Worksheets"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qwks_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "sample"], name="idx_qwks_ten_sample"),
            models.Index(fields=["tenant", "specification"], name="idx_qwks_ten_spec"),
            models.Index(fields=["tenant", "status"], name="idx_qwks_ten_status"),
            models.Index(fields=["tenant", "disposition"], name="idx_qwks_ten_disp"),
            models.Index(fields=["tenant", "-scheduled_date"], name="idx_qwks_ten_date"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_status_display()})"

    @property
    def is_overdue(self):
        return (
            self.scheduled_date is not None
            and self.scheduled_date < timezone.now().date()
            and self.status in ["assigned", "in_progress"]
        )

    @property
    def reagent_expired(self):
        return self.reagent_expiry_date is not None and self.reagent_expiry_date < timezone.now().date()

    @property
    def standards_expired(self):
        return self.standards_expiry_date is not None and self.standards_expiry_date < timezone.now().date()

    def get_status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def get_disposition_badge(self):
        return self.DISPOSITION_CSS.get(self.disposition, "badge-slate")
