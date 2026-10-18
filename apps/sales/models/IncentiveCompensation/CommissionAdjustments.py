"""Sales 8.10 — `CommissionAdjustment` (`CADJ-`), clawbacks, true-ups & dispute workflows.

Auditable adjustment engine for order cancellation chargebacks, churn clawbacks,
draw advances and retroactive tier true-ups, manager discretionary overrides,
and sales rep dispute claims.
"""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered

ADJUSTMENT_TYPE_CHOICES = [
    ("cancellation_clawback", "Order Cancellation / Churn Clawback"),
    ("draw_true_up", "Draw True-Up / Reconciliation"),
    ("tier_true_up", "Retroactive Tier Rate True-Up"),
    ("manual_override", "Manager Discretionary Override"),
    ("dispute_resolution", "Rep Dispute Claim Settlement"),
    ("tax_adjustment", "Local Tax / FX Adjustment"),
]

STATUS_CHOICES = [
    ("draft", "Draft / Proposed"),
    ("disputed", "Under Rep Dispute"),
    ("approved", "Approved by Manager"),
    ("applied", "Applied to Statement"),
    ("rejected", "Rejected / Dismissed"),
]


class CommissionAdjustment(TenantNumbered):
    NUMBER_PREFIX = "CADJ"

    statement = models.ForeignKey(
        "sales.CommissionStatement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjustments",
    )
    earning = models.ForeignKey(
        "sales.CommissionEarning",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjustments",
    )
    payee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sales_commission_adjustments",
        db_index=True,
    )
    adjustment_type = models.CharField(
        max_length=30,
        choices=ADJUSTMENT_TYPE_CHOICES,
        db_index=True,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Adjustment amount in functional currency (+ for credits, - for clawbacks/deductions)",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    reason = models.TextField(
        help_text="Detailed justification, cancellation order link, or dispute claim explanation",
    )
    dispute_comments = models.TextField(
        blank=True,
        help_text="Exchange between payee and sales management regarding disputed amount",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_commission_adjustments",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_commission_adjustments",
    )
    effective_date = models.DateField(db_index=True)

    class Meta:
        ordering = ["-effective_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_cadj_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "payee", "status"],
                name="sales_cadj_payee_stat_idx",
            ),
            models.Index(
                fields=["tenant", "adjustment_type"],
                name="sales_cadj_type_idx",
            ),
            models.Index(
                fields=["tenant", "status"],
                name="sales_cadj_ten_stat_idx",
            ),
            models.Index(
                fields=["tenant", "statement"],
                name="sales_cadj_ten_stmt_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} — {self.payee} (${self.amount})"

    def clean(self):
        super().clean()

        # G14: Tenant isolation
        if self.payee_id and self.tenant_id:
            if getattr(self.payee, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"payee": "Payee must belong to the same workspace."})

        if self.requested_by_id and self.tenant_id:
            if getattr(self.requested_by, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"requested_by": "Requester must belong to the same workspace."})

        if self.approved_by_id and self.tenant_id:
            if getattr(self.approved_by, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"approved_by": "Approver must belong to the same workspace."})

        if self.earning_id and self.tenant_id:
            if self.earning.tenant_id != self.tenant_id:
                raise ValidationError({"earning": "Commission earning belongs to another workspace."})

        if self.statement_id and self.tenant_id:
            if self.statement.tenant_id != self.tenant_id:
                raise ValidationError({"statement": "Statement belongs to another workspace."})

        # G15: Cancellation clawbacks must have negative amounts
        if self.adjustment_type == "cancellation_clawback" and self.amount is not None:
            if Decimal(str(self.amount)) > Decimal("0.00"):
                raise ValidationError({"amount": "Cancellation clawbacks must be recorded with a negative amount (e.g. -500.00)."})

        # G16: If statement is locked/paid, adjustments cannot be added to it directly
        if self.statement_id:
            if self.statement.status in ("locked", "exported", "paid"):
                raise ValidationError({"statement": "Cannot attach adjustments to a locked or exported statement. Adjustments must roll into the next draft statement."})

        # G17: Cross-payee relational isolation
        if self.earning_id and self.payee_id:
            if self.earning.payee_id != self.payee_id:
                raise ValidationError({"earning": "Linked commission earning must belong to the same payee."})

        if self.statement_id and self.payee_id:
            if self.statement.payee_id != self.payee_id:
                raise ValidationError({"statement": "Linked statement must belong to the same payee."})
