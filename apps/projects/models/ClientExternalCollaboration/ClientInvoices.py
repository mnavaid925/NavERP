"""Projects 7.14 Client & External Collaboration — ProjectClientInvoice [PCI-].

Project delivery billing schedule and client invoice generation (T&M, fixed-fee,
milestone-based) linked directly to the canonical accounting.Invoice ledger.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.projects.models._base import TenantNumbered, q2


class ProjectClientInvoice(TenantNumbered):
    NUMBER_PREFIX = "PCI"

    BILLING_TYPE_CHOICES = [
        ("fixed_fee", "Fixed Fee"),
        ("time_and_materials", "Time & Materials"),
        ("milestone", "Milestone-Based"),
        ("retainer", "Retainer"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("ready_to_bill", "Ready to Bill"),
        ("invoiced", "Invoiced"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="client_invoices",
    )
    sow = models.ForeignKey(
        "projects.StatementOfWork",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_records",
    )
    milestone = models.ForeignKey(
        "projects.ProjectMilestone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_records",
    )
    billing_type = models.CharField(
        max_length=25, choices=BILLING_TYPE_CHOICES, default="milestone"
    )
    billing_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
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
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    accounting_invoice = models.ForeignKey(
        "accounting.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_billing_records",
    )
    invoiced_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="pci_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="pci_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.project.name} ({self.total_amount})"

    def save(self, *args, **kwargs):
        self.amount = q2(self.amount)
        self.tax_amount = q2(self.tax_amount)
        self.total_amount = q2(self.amount + self.tax_amount)
        super().save(*args, **kwargs)
