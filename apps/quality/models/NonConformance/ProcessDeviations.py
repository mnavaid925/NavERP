from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ProcessDeviation(TenantNumbered):
    NUMBER_PREFIX = "QDEV"

    DEVIATION_TYPE_CHOICES = (
        ("planned", "Planned (Temporary Concession)"),
        ("unplanned", "Unplanned (Process Excursion)"),
    )

    CATEGORY_CHOICES = (
        ("process_parameter", "Process Parameter Out-of-Spec"),
        ("equipment_substitution", "Equipment / Machine Substitution"),
        ("material_substitution", "Raw Material / Component Substitution"),
        ("procedural_exemption", "Procedural / SOP Exemption"),
        ("environmental", "Cleanroom / Environmental Excursion"),
    )

    RISK_IMPACT_CHOICES = (
        ("negligible", "Negligible Impact"),
        ("minor", "Minor Risk"),
        ("moderate", "Moderate Risk"),
        ("critical", "Critical Product Risk"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("under_assessment", "Under Impact Assessment"),
        ("approved", "Approved"),
        ("active", "Active Production Run"),
        ("expired", "Expired"),
        ("closed", "Closed / Completed"),
        ("cancelled", "Cancelled"),
    )

    DEVIATION_TYPE_CSS = {
        "planned": "badge-info",
        "unplanned": "badge-amber",
    }

    CATEGORY_CSS = {
        "process_parameter": "badge-amber",
        "equipment_substitution": "badge-info",
        "material_substitution": "badge-amber",
        "procedural_exemption": "badge-slate",
        "environmental": "badge-red",
    }

    RISK_IMPACT_CSS = {
        "negligible": "badge-slate",
        "minor": "badge-info",
        "moderate": "badge-amber",
        "critical": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "under_assessment": "badge-info",
        "approved": "badge-green",
        "active": "badge-amber",
        "expired": "badge-red",
        "closed": "badge-green",
        "cancelled": "badge-muted",
    }

    title = models.CharField(max_length=255)
    deviation_type = models.CharField(
        max_length=16,
        choices=DEVIATION_TYPE_CHOICES,
        default="unplanned",
        db_index=True,
    )
    category = models.CharField(
        max_length=32,
        choices=CATEGORY_CHOICES,
        default="process_parameter",
        db_index=True,
    )
    ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="process_deviations",
        help_text="Originating NCR if unplanned",
    )
    controlled_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="process_deviations",
        help_text="Operating procedure or work instruction being deviated from",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="process_deviations",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_deviations",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_deviations",
    )
    risk_impact_level = models.CharField(
        max_length=16,
        choices=RISK_IMPACT_CHOICES,
        default="minor",
        db_index=True,
    )
    quality_impact_assessment = models.TextField(
        help_text="Detailed assessment of impact on product safety, efficacy, validation, and stability",
    )
    affected_lots_summary = models.TextField(
        blank=True,
        help_text="List of batches, lots, or serial runs produced under this deviation",
    )
    customer_notification_required = models.BooleanField(
        default=False,
        help_text="Customer notification or concession approval required",
    )
    customer_concession_obtained = models.BooleanField(default=False)
    regulatory_reporting_required = models.BooleanField(
        default=False,
        help_text="Regulatory health authority notification required",
    )
    regulatory_authority_notified = models.BooleanField(default=False)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(
        null=True,
        blank=True,
        help_text="Mandatory expiration date for temporary deviation",
    )
    max_batches_permitted = models.PositiveIntegerField(
        default=1,
        help_text="Maximum number of batches/lots permitted under this deviation",
    )
    batches_produced_count = models.PositiveIntegerField(
        default=0,
        help_text="Actual number of batches produced to date",
    )
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Process Deviation"
        verbose_name_plural = "Process Deviations"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qdev_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qdev_ten_status"),
            models.Index(fields=["tenant", "deviation_type"], name="idx_qdev_ten_dev_type"),
            models.Index(fields=["tenant", "valid_until"], name="idx_qdev_ten_valid_until"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qdev_ten_created"),
        ]

    def __str__(self):
        return f"{self.number or 'Draft'} - {self.title}"

    @property
    def deviation_type_badge(self):
        return self.DEVIATION_TYPE_CSS.get(self.deviation_type, "badge-slate")

    @property
    def category_badge(self):
        return self.CATEGORY_CSS.get(self.category, "badge-slate")

    @property
    def risk_impact_badge(self):
        return self.RISK_IMPACT_CSS.get(self.risk_impact_level, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def is_expired(self):
        if self.valid_until and self.status in ("active", "approved"):
            return self.valid_until < timezone.now().date()
        return self.status == "expired"
