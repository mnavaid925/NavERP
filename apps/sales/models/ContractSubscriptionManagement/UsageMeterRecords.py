"""Sales 8.15 — UsageMeterRecord model."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

USAGE_STATUS_CHOICES = [
    ("metering", "Metering in Progress"),
    ("calculated", "Charges Calculated"),
    ("invoiced", "Invoiced"),
    ("disputed", "Disputed / Adjusted"),
]


class UsageMeterRecord(TenantNumbered):
    NUMBER_PREFIX = "UMR"

    subscription = models.ForeignKey(
        "sales.CustomerSubscription",
        on_delete=models.CASCADE,
        related_name="usage_records",
    )
    meter_name = models.CharField(max_length=120)
    unit_of_measure = models.CharField(max_length=40, default="units")
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    included_allowance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    reported_usage = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    billable_overage_units = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    overage_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(0)],
    )
    overage_total_charge = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        max_length=20,
        choices=USAGE_STATUS_CHOICES,
        default="metering",
    )
    invoiced_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-billing_period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_umr_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_umr_ten_status_idx"),
            models.Index(fields=["tenant", "subscription"], name="sales_umr_ten_sub_idx"),
            models.Index(fields=["tenant", "billing_period_end"], name="sales_umr_ten_period_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.meter_name} ({self.subscription.subscription_name})"

    def calculate_charges(self):
        if self.reported_usage > self.included_allowance:
            self.billable_overage_units = (self.reported_usage - self.included_allowance).quantize(Decimal("0.01"))
        else:
            self.billable_overage_units = Decimal("0.00")
        self.overage_total_charge = (self.billable_overage_units * self.overage_unit_price).quantize(Decimal("0.01"))

    def clean(self):
        super().clean()
        if self.billing_period_end and self.billing_period_start and self.billing_period_end < self.billing_period_start:
            raise ValidationError({"billing_period_end": "Period end date cannot precede start date."})

        if self.subscription_id and self.tenant_id and self.subscription.tenant_id != self.tenant_id:
            raise ValidationError({"subscription": "Subscription must belong to this workspace."})

        self.calculate_charges()
