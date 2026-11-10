from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetTradeIn(TenantNumbered):
    """
    Asset Trade-in & Exchange Record [ATRD-].
    Governs vendor equipment trade-ins, replacement asset cost offsets,
    dealer appraisal negotiations, like-kind exchange tracking, and handover logistics.
    """

    NUMBER_PREFIX = "ATRD"

    STATUS_CHOICES = [
        ("draft", "Draft Proposal"),
        ("proposed", "Submitted to Vendor"),
        ("negotiated", "Valuation Negotiated"),
        ("accepted", "Trade-in Approved & Bound"),
        ("equipment_surrendered", "Equipment Handed Over to Vendor"),
        ("credit_settled", "Allowance Settled on Invoice"),
        ("rejected", "Trade-in Rejected"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "proposed": "badge-amber",
        "negotiated": "badge-info",
        "accepted": "badge-info",
        "equipment_surrendered": "badge-amber",
        "credit_settled": "badge-green",
        "rejected": "badge-red",
        "cancelled": "badge-muted",
    }

    disposal_request = models.ForeignKey(
        "assets.AssetDisposalRequest",
        on_delete=models.CASCADE,
        related_name="trade_ins",
        help_text="Parent disposal authorization request",
    )
    retired_fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.CASCADE,
        related_name="trade_ins_retired",
        help_text="Retiring fixed asset being traded in",
    )
    vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="asset_trade_in_vendors",
        help_text="OEM dealer or machinery supplier offering trade credit",
    )
    replacement_requisition = models.ForeignKey(
        "assets.AssetRequisition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trade_ins",
        help_text="Linked purchase requisition for replacement machine",
    )
    replacement_fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trade_ins_replacement",
        help_text="New replacement asset acquired in exchange",
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authorized_asset_trade_ins",
        help_text="Procurement or finance manager authorizing trade",
    )
    agreement_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trade_in_agreements",
        help_text="Executed dealer exchange contract or credit memo",
    )

    agreement_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Vendor exchange agreement reference number",
    )
    agreement_date = models.DateField(
        default=timezone.now,
        help_text="Date of trade-in agreement signing",
    )
    handover_due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Target deadline for releasing physical asset to dealer",
    )

    dealer_appraised_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Dealer wholesale appraised value",
    )
    trade_in_allowance = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Contractual trade allowance credited against new purchase",
    )
    over_allowance_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Dealer marketing incentive / over-allowance discount",
    )
    net_credit_applied = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total net credit offset against replacement cost (allowance + over-allowance)",
    )

    replacement_asset_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross purchase cost of new replacement asset",
    )
    net_cash_outflow = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net remaining cash payment due (replacement cost - net credit)",
    )

    like_kind_exchange = models.BooleanField(
        default=False,
        help_text="Flags transaction as IRC Sec 1031 / like-kind exchange for deferred tax gain/loss",
    )
    gain_loss_deferred = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Taxable gain/loss deferred into replacement basis",
    )

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="draft",
    )
    surrendered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp physical equipment was transferred",
    )
    settled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp trade credit was cleared on dealer invoice",
    )
    notes = models.TextField(
        blank=True,
        help_text="Exchange stipulations, freight terms, or warranty offset notes",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_atrd_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_atrd_ten_stat"),
            models.Index(fields=["tenant", "agreement_date"], name="idx_atrd_ten_adate"),
            models.Index(fields=["tenant", "vendor"], name="idx_atrd_ten_vend"),
        ]

    def __str__(self):
        return f"{self.number} — {self.retired_fixed_asset.name} trade to {self.vendor.name}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def calculate_trade_credit(self):
        """Computes net credit applied and net cash outflow."""
        self.net_credit_applied = (self.trade_in_allowance or Decimal("0.00")) + (
            self.over_allowance_amount or Decimal("0.00")
        )
        if self.replacement_asset_cost:
            outflow = self.replacement_asset_cost - self.net_credit_applied
            self.net_cash_outflow = max(Decimal("0.00"), outflow)
        else:
            self.net_cash_outflow = Decimal("0.00")
        return self.net_credit_applied
