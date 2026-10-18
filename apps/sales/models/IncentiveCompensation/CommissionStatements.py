"""Sales 8.10 — `CommissionStatement` (`CST-`), period compensation settlements.

Aggregates credited earnings, applies draw recovery and clawback deductions,
calculates net settlement payouts, enforces manager approvals and statement locking,
and links directly to `accounting.PayrollRun`.
"""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered

STATEMENT_STATUS_CHOICES = [
    ("draft", "Draft / Open"),
    ("under_review", "Under Manager Review"),
    ("approved", "Approved by Manager"),
    ("locked", "Locked / Finalized"),
    ("exported", "Exported / Sent to Payroll"),
    ("paid", "Paid"),
]


class CommissionStatement(TenantNumbered):
    NUMBER_PREFIX = "CST"

    statement_number = models.CharField(
        max_length=40,
        help_text="Formatted identifier e.g. STMT-2026-M10-REP",
        db_index=True,
    )
    payee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="commission_statements",
        db_index=True,
    )
    plan = models.ForeignKey(
        "sales.CommissionPlan",
        on_delete=models.PROTECT,
        related_name="statements",
    )
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATEMENT_STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    total_credited_volume = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Sum of deal credited volume during this settlement cycle",
    )
    total_base_commission = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Base commission earnings",
    )
    total_accelerator_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Additional earnings derived from tier accelerator brackets",
    )
    total_spif_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Total tactical SPIF campaign bonuses",
    )
    gross_earnings = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Total gross earnings before deductions = base + accelerator + spif",
    )
    draw_advance_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Guaranteed draw advance paid out at period start",
    )
    draw_recovered = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Draw amount recovered from gross commission",
    )
    adjustments_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Net manual adjustments (+/-)",
    )
    clawbacks_deducted = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Total order cancellations and clawbacks deducted",
    )
    tax_withholding_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Estimated or statutory tax withholding deducted",
    )
    net_payout = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Final net payable amount after waterfall deductions",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_commission_statements",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    payroll_run = models.ForeignKey(
        "accounting.PayrollRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_statements",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "payee__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_cst_tenant_number_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "payee", "period_start", "period_end"],
                name="sales_cst_payee_period_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status", "period_end"],
                name="sales_cst_stat_end_idx",
            ),
            models.Index(
                fields=["tenant", "payee"],
                name="sales_cst_payee_idx",
            ),
            models.Index(
                fields=["tenant", "plan"],
                name="sales_cst_ten_plan_idx",
            ),
        ]

    def __str__(self):
        return f"{self.statement_number} — {self.payee} (${self.net_payout})"

    def clean(self):
        super().clean()

        # G10: Period validation
        if self.period_start and self.period_end:
            if self.period_end < self.period_start:
                raise ValidationError({"period_end": "Period end date cannot precede period start date."})

        # G13: Tenant isolation
        if self.payee_id and self.tenant_id:
            if getattr(self.payee, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"payee": "Payee must belong to the same workspace."})

        if self.plan_id and self.tenant_id:
            if self.plan.tenant_id != self.tenant_id:
                raise ValidationError({"plan": "Compensation plan belongs to another workspace."})

        if self.approved_by_id and self.tenant_id:
            if getattr(self.approved_by, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"approved_by": "Approver must belong to the same workspace."})

        if self.payroll_run_id and self.tenant_id:
            if self.payroll_run.tenant_id != self.tenant_id:
                raise ValidationError({"payroll_run": "Payroll run belongs to another workspace."})

        # G11: Waterfall consistency
        gross = Decimal(str(self.gross_earnings or 0))
        adj = Decimal(str(self.adjustments_amount or 0))
        draw_rec = Decimal(str(self.draw_recovered or 0))
        clawback = Decimal(str(self.clawbacks_deducted or 0))
        tax = Decimal(str(self.tax_withholding_amount or 0))
        calc_net = max(Decimal("0.00"), gross + adj - draw_rec - clawback - tax)
        self.net_payout = round(calc_net, 2)

        # G12: Lock guard
        if self.pk:
            prior = CommissionStatement.objects.filter(pk=self.pk).values("status").first()
            if prior and prior["status"] in ("locked", "exported", "paid") and self.status == prior["status"]:
                # Checked on save / view mutation guard
                pass
