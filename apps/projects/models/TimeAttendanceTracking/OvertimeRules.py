"""Projects 7.11 Time & Attendance Tracking — OvertimeRule [OTR-].

Overtime calculation policies defining standard daily and weekly hours thresholds
and multiplier rates for overtime, weekend, and holiday project work.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class OvertimeRule(TenantNumbered):
    """Configures overtime thresholds, multipliers, and approval requirements per project or tenant-wide."""

    NUMBER_PREFIX = "OTR"

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overtime_rules",
        help_text="Optional project scope. When blank, applies as tenant-wide default policy.")
    name = models.CharField(max_length=100)
    standard_daily_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("8.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("24.00"))],
        help_text="Standard daily hours threshold before daily overtime begins.")
    standard_weekly_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("40.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("168.00"))],
        help_text="Standard weekly hours threshold before weekly overtime begins.")
    daily_overtime_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.50"),
        validators=[MinValueValidator(Decimal("1.00")), MaxValueValidator(Decimal("5.00"))],
        help_text="Pay multiplier for standard daily overtime.")
    weekly_overtime_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.50"),
        validators=[MinValueValidator(Decimal("1.00")), MaxValueValidator(Decimal("5.00"))],
        help_text="Pay multiplier for hours exceeding the weekly threshold.")
    weekend_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.50"),
        validators=[MinValueValidator(Decimal("1.00")), MaxValueValidator(Decimal("5.00"))],
        help_text="Pay multiplier for work performed on non-working weekend days.")
    holiday_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("2.00"),
        validators=[MinValueValidator(Decimal("1.00")), MaxValueValidator(Decimal("5.00"))],
        help_text="Pay multiplier for work performed on public/company holidays.")
    requires_pre_approval = models.BooleanField(
        default=False,
        help_text="Whether overtime must be pre-approved before logging.")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_active", "name", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="otr_tnt_active_idx"),
            models.Index(fields=["tenant", "project"], name="otr_tnt_prj_idx"),
        ]

    def __str__(self):
        scope = self.project.name if self.project else "Tenant Default"
        return f"{self.number} · {self.name} ({scope})"
