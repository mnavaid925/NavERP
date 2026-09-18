"""Projects 7.15 Financial & Billing Management — ProjectBillingRun [PBR-].

Governs batch billing run sessions that aggregate unbilled approved timesheets
and direct project expenses, calculate taxes, multi-currency conversion,
and generate canonical accounting.Invoice records for client delivery.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.projects.models._base import TenantNumbered, q2


class ProjectBillingRun(TenantNumbered):
    NUMBER_PREFIX = "PBR"

    BILLING_TYPE_CHOICES = [
        ("time_and_materials", "Time & Materials"),
        ("fixed_fee", "Fixed Fee"),
        ("milestone", "Milestone-Based"),
        ("progress_percent", "Progress Percentage"),
        ("retainer", "Retainer"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("invoiced", "Invoiced"),
        ("cancelled", "Cancelled"),
    ]

    DELIVERY_CHANNEL_CHOICES = [
        ("email", "Email Dispatch"),
        ("portal", "Client Portal"),
        ("download", "Manual Download"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="billing_runs",
    )
    client = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="project_billing_runs",
    )
    sow = models.ForeignKey(
        "projects.StatementOfWork",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_runs",
    )
    milestone = models.ForeignKey(
        "projects.ProjectMilestone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_runs",
    )
    billing_type = models.CharField(
        max_length=24,
        choices=BILLING_TYPE_CHOICES,
        default="time_and_materials",
    )
    run_date = models.DateField(default=timezone.localdate)
    cutoff_date = models.DateField(
        help_text="Unbilled hours and expenses up to this cutoff date are captured in this run."
    )
    total_time_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    labor_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    expense_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    fee_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    tax_code = models.ForeignKey(
        "accounting.TaxCode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    tax_rate_pct = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal("0.000"),
    )
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="+",
    )
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        default=Decimal("1.00000000"),
        help_text="Spot exchange rate to tenant functional currency at run date.",
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="draft",
    )
    accounting_invoice = models.ForeignKey(
        "accounting.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_billing_runs",
        help_text="Canonical invoice record in accounting AR ledger.",
    )
    delivery_channel = models.CharField(
        max_length=12,
        choices=DELIVERY_CHANNEL_CHOICES,
        default="email",
    )
    recipient_email = models.CharField(max_length=255, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True, editable=False)
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="pbr_tnt_prj_idx"),
            models.Index(fields=["tenant", "status"], name="pbr_tnt_status_idx"),
            models.Index(fields=["tenant", "run_date"], name="pbr_tnt_date_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.project.name} ({self.get_billing_type_display()}): {self.total_amount} {self.currency.code}"

    def save(self, *args, **kwargs):
        self.labor_amount = q2(self.labor_amount)
        self.expense_amount = q2(self.expense_amount)
        self.fee_amount = q2(self.fee_amount)
        self.subtotal = q2(self.labor_amount + self.expense_amount + self.fee_amount)
        if self.tax_code and not self.tax_rate_pct:
            self.tax_rate_pct = self.tax_code.rate
        if self.tax_rate_pct:
            self.tax_amount = q2(self.subtotal * (self.tax_rate_pct / Decimal("100.0")))
        else:
            self.tax_amount = q2(self.tax_amount)
        self.total_amount = q2(self.subtotal + self.tax_amount)
        super().save(*args, **kwargs)
