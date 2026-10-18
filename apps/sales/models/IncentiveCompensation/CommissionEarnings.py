"""Sales 8.10 — `CommissionEarning` (`CER-`), deal- and order-level commission crediting.

Calculates deal volume, split allocation %, quota attainment at deal close,
accelerator tier rate application, SPIF tactical bonuses, and spot FX rate translation.
"""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

CREDIT_TYPE_CHOICES = [
    ("direct", "Direct Rep Credit"),
    ("split", "Team Deal Split"),
    ("overlay", "Overlay / Specialist Credit"),
    ("manager_override", "Manager Rollup / Override"),
    ("spif_bonus", "SPIF Campaign Bonus"),
]

STATUS_CHOICES = [
    ("pending", "Pending Calculation"),
    ("calculated", "Calculated / Verified"),
    ("approved", "Approved for Payout"),
    ("paid", "Paid out"),
    ("clawed_back", "Clawed Back"),
]


class CommissionEarning(TenantNumbered):
    NUMBER_PREFIX = "CER"

    plan = models.ForeignKey(
        "sales.CommissionPlan",
        on_delete=models.CASCADE,
        related_name="earnings",
    )
    payee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sales_commission_earnings",
        db_index=True,
    )
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_earnings",
    )
    sales_order = models.ForeignKey(
        "scm.SalesOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_earnings",
    )
    credit_type = models.CharField(
        max_length=30,
        choices=CREDIT_TYPE_CHOICES,
        default="direct",
    )
    split_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of the deal attributed to this payee (0 to 100%)",
    )
    deal_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Total value of the transaction in deal currency",
    )
    credited_volume = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Credited volume = deal_amount * split_percentage / 100",
    )
    attainment_pct_at_close = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Rep cumulative quota attainment percentage at deal close time",
    )
    applied_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Effective commission rate applied (base + accelerator bracket)",
    )
    base_commission_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Credited volume * applied_rate_pct / 100",
    )
    spif_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Additional tactical SPIF bonus earned",
    )
    gross_commission = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Total gross commission = base_commission_amount + spif_amount",
    )
    deal_currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="sales_deal_earnings",
    )
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1.000000,
        validators=[MinValueValidator(0)],
        help_text="Daily spot rate to convert deal currency to tenant functional currency",
    )
    functional_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Gross commission converted to functional currency (gross * exchange_rate)",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="calculated",
        db_index=True,
    )
    earned_date = models.DateField(db_index=True)
    clawback_parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clawback_children",
        help_text="If this record is a clawback, points to the original earning",
    )
    statement = models.ForeignKey(
        "sales.CommissionStatement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="earnings",
    )

    class Meta:
        ordering = ["-earned_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_cer_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "payee", "status"],
                name="sales_cer_payee_stat_idx",
            ),
            models.Index(
                fields=["tenant", "earned_date"],
                name="sales_cer_date_idx",
            ),
            models.Index(
                fields=["tenant", "opportunity"],
                name="sales_cer_opp_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} — {self.payee} ({self.deal_currency.code} {self.gross_commission})"

    def clean(self):
        super().clean()

        # G5: Tenant isolation
        if self.plan_id and self.tenant_id:
            if self.plan.tenant_id != self.tenant_id:
                raise ValidationError({"plan": "Commission plan belongs to another workspace."})

        if self.payee_id and self.tenant_id:
            if getattr(self.payee, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"payee": "Credited payee must belong to the same workspace."})

        # G6: Opportunity tenant isolation
        if self.opportunity_id and self.tenant_id:
            if self.opportunity.tenant_id != self.tenant_id:
                raise ValidationError({"opportunity": "Opportunity belongs to another workspace."})

        # G7: Sales order tenant isolation
        if self.sales_order_id and self.tenant_id:
            if self.sales_order.tenant_id != self.tenant_id:
                raise ValidationError({"sales_order": "Sales order belongs to another workspace."})

        # Statement tenant isolation
        if self.statement_id and self.tenant_id:
            if self.statement.tenant_id != self.tenant_id:
                raise ValidationError({"statement": "Statement belongs to another workspace."})

        # G8: Math verification: credited_volume
        if self.deal_amount is not None and self.split_percentage is not None:
            expected_vol = round(Decimal(str(self.deal_amount)) * Decimal(str(self.split_percentage)) / Decimal("100"), 2)
            self.credited_volume = expected_vol

        # Base commission calculation
        if self.credited_volume is not None and self.applied_rate_pct is not None:
            self.base_commission_amount = round(Decimal(str(self.credited_volume)) * Decimal(str(self.applied_rate_pct)) / Decimal("100"), 2)

        # G9: Gross commission calculation
        base_amt = self.base_commission_amount or Decimal("0.00")
        spif_amt = self.spif_amount or Decimal("0.00")
        self.gross_commission = round(base_amt + spif_amt, 2)

        # Functional amount calculation
        xr = self.exchange_rate or Decimal("1.000000")
        self.functional_amount = round(self.gross_commission * Decimal(str(xr)), 2)
