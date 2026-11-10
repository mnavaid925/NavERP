from decimal import Decimal

from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetLeaseSchedule(TenantNumbered):
    """
    Asset Lease Amortization & Payment Schedule [ALSP-].
    Tracks period-by-period lease payment installments, actuarial interest expense,
    principal lease liability reduction, and ROU asset depreciation.
    """

    NUMBER_PREFIX = "ALSP"

    STATUS_CHOICES = [
        ("scheduled", "Scheduled (Pending Due Date)"),
        ("accrued", "Accrued (Interest/Amortization Booked)"),
        ("paid", "Paid & Settled"),
        ("cancelled", "Cancelled / Derecognized"),
    ]

    STATUS_CSS = {
        "scheduled": "badge-slate",
        "accrued": "badge-info",
        "paid": "badge-green",
        "cancelled": "badge-muted",
    }

    lease_contract = models.ForeignKey(
        "assets.AssetLeaseContract",
        on_delete=models.CASCADE,
        related_name="payment_schedules",
        help_text="Parent lease agreement",
    )
    period_number = models.PositiveIntegerField(
        help_text="Sequential period index (1 to N)",
    )
    due_date = models.DateField(
        help_text="Payment due date for this installment",
    )
    payment_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross installment cash payment due",
    )

    # Financial Amortization Breakdown
    beginning_liability = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Liability balance at start of period",
    )
    interest_expense = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Accreted interest expense component",
    )
    principal_reduction = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Reduction in lease liability principal",
    )
    ending_liability = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Remaining liability balance at period end",
    )
    rou_depreciation = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Straight-line or asset-specific ROU depreciation",
    )
    ending_rou_asset_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Carrying value of ROU asset at period end",
    )

    # Settlement
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Disbursement voucher, check, or wire transaction reference",
    )
    paid_date = models.DateField(
        null=True,
        blank=True,
        help_text="Actual date payment was settled",
    )
    notes = models.TextField(
        blank=True,
        help_text="Accrual or settlement remarks",
    )

    class Meta:
        ordering = ["due_date", "period_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_alsp_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "lease_contract", "period_number"], name="idx_alsp_ten_ctr_prd"),
            models.Index(fields=["tenant", "status"], name="idx_alsp_ten_stat"),
            models.Index(fields=["tenant", "due_date"], name="idx_alsp_ten_due"),
        ]

    def __str__(self):
        contract_num = self.lease_contract.number if self.lease_contract_id else ""
        if contract_num:
            return f"{self.number} — {contract_num} (Period {self.period_number})"
        return f"{self.number} (Period {self.period_number})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
