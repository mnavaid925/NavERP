"""Sales 8.16 — FieldSalesRoute model."""
from decimal import Decimal
import urllib.parse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

ROUTE_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("scheduled", "Scheduled"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

OPTIMIZATION_STATUS_CHOICES = [
    ("unoptimized", "Unoptimized Sequence"),
    ("optimized", "Route Optimized"),
    ("manual_order", "Manual Custom Order"),
]


class FieldSalesRoute(TenantNumbered):
    NUMBER_PREFIX = "FSR"

    name = models.CharField(max_length=200)
    sales_rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="field_sales_routes",
    )
    route_date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=ROUTE_STATUS_CHOICES,
        default="scheduled",
    )
    start_location = models.CharField(max_length=255, blank=True)
    end_location = models.CharField(max_length=255, blank=True)
    total_stops = models.PositiveIntegerField(default=0)
    completed_stops = models.PositiveIntegerField(default=0)
    planned_distance_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    actual_distance_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    estimated_duration_minutes = models.PositiveIntegerField(default=0)
    actual_duration_minutes = models.PositiveIntegerField(default=0)
    optimization_status = models.CharField(
        max_length=20,
        choices=OPTIMIZATION_STATUS_CHOICES,
        default="unoptimized",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-route_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_fsr_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_fsr_ten_stat_idx"),
            models.Index(fields=["tenant", "sales_rep"], name="sales_fsr_ten_rep_idx"),
            models.Index(fields=["tenant", "route_date"], name="sales_fsr_ten_date_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.route_date})"

    def clean(self):
        super().clean()
        if self.completed_stops > self.total_stops:
            raise ValidationError({"completed_stops": "Completed stops cannot exceed total stops."})

        if self.sales_rep_id and self.tenant_id:
            rep_tenant_id = getattr(self.sales_rep, "tenant_id", None)
            if rep_tenant_id and rep_tenant_id != self.tenant_id:
                raise ValidationError({"sales_rep": "Assigned sales rep belongs to another workspace."})

    @property
    def completion_rate_pct(self):
        if self.total_stops > 0:
            return int(round((self.completed_stops / self.total_stops) * 100))
        return 0

    @property
    def progress_display(self):
        return f"{self.completed_stops}/{self.total_stops} Stops"

    def generate_navigation_url(self):
        if self.start_location:
            dest = self.end_location or self.start_location
            query = urllib.parse.quote(f"{self.start_location} to {dest}")
            return f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(self.start_location)}&destination={urllib.parse.quote(dest)}"
        return "https://maps.google.com"
