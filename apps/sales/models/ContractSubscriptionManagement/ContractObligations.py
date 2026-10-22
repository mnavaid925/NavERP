"""Sales 8.15 — ContractObligation model."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

OBLIGATION_TYPE_CHOICES = [
    ("sla_uptime", "SLA Uptime Benchmark"),
    ("sla_response", "SLA Support Response Time"),
    ("delivery_milestone", "Project Delivery Milestone"),
    ("reporting_compliance", "Regulatory & Reporting Compliance"),
    ("warranty_support", "Warranty & Support Obligation"),
    ("security_review", "Security Assessment / Audit"),
]

OBLIGATION_STATUS_CHOICES = [
    ("pending", "Pending Fulfillment"),
    ("fulfilled", "Fulfilled"),
    ("at_risk", "At Risk"),
    ("breached", "Breached / Default"),
    ("waived", "Waived by Mutual Agreement"),
]

PENALTY_STATUS_CHOICES = [
    ("none", "No Penalty"),
    ("assessed", "Penalty Assessed"),
    ("credited", "Service Credit Issued"),
    ("waived", "Penalty Waived"),
]


class ContractObligation(TenantNumbered):
    NUMBER_PREFIX = "OBL"

    contract = models.ForeignKey(
        "sales.CustomerContract",
        on_delete=models.CASCADE,
        related_name="obligations",
    )
    subscription = models.ForeignKey(
        "sales.CustomerSubscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="obligations",
    )
    title = models.CharField(max_length=255)
    obligation_type = models.CharField(
        max_length=40,
        choices=OBLIGATION_TYPE_CHOICES,
        default="sla_uptime",
    )
    target_metric = models.CharField(
        max_length=150,
        help_text="Benchmark metric (e.g. >= 99.9% Uptime, < 1hr P1 Response)",
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=OBLIGATION_STATUS_CHOICES,
        default="pending",
    )
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    fulfillment_evidence = models.TextField(
        blank=True,
        help_text="Proof of satisfaction, audit report, or incident reference",
    )
    penalty_terms = models.TextField(
        blank=True,
        help_text="Contractual service credit terms or damages formula",
    )
    penalty_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    penalty_status = models.CharField(
        max_length=20,
        choices=PENALTY_STATUS_CHOICES,
        default="none",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_contract_obligations",
    )

    class Meta:
        ordering = ["due_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_obl_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_obl_ten_status_idx"),
            models.Index(fields=["tenant", "obligation_type"], name="sales_obl_ten_type_idx"),
            models.Index(fields=["tenant", "contract"], name="sales_obl_ten_contract_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.contract.number})"

    def clean(self):
        super().clean()
        if self.contract_id and self.tenant_id and self.contract.tenant_id != self.tenant_id:
            raise ValidationError({"contract": "Contract must belong to this workspace."})

        if self.subscription_id and self.tenant_id and self.subscription.tenant_id != self.tenant_id:
            raise ValidationError({"subscription": "Subscription must belong to this workspace."})

        if self.assigned_to_id and self.tenant_id and getattr(self.assigned_to, "tenant_id", None) != self.tenant_id:
            raise ValidationError({"assigned_to": "Assignee must belong to this workspace."})

        if self.status == "fulfilled" and not self.fulfillment_evidence.strip():
            raise ValidationError({"fulfillment_evidence": "Fulfillment evidence is required when marking obligation fulfilled."})

        if self.penalty_status in ("assessed", "credited") and self.penalty_amount <= Decimal("0.00"):
            raise ValidationError({"penalty_amount": "Penalty amount must be greater than zero when assessing or crediting penalties."})
