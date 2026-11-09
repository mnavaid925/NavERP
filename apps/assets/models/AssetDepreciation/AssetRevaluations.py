from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetRevaluation(TenantNumbered):
    """Asset valuation, impairment test (ASC 360 / IAS 36), and fair value revaluation [AREV-]."""

    NUMBER_PREFIX = "AREV"

    EVENT_TYPE_CHOICES = [
        ("impairment", "Impairment Loss (ASC 360 / IAS 36)"),
        ("revaluation_up", "Upward Fair Value Revaluation (IFRS 13)"),
        ("reversal_impairment", "Reversal of Prior Impairment"),
        ("salvage_revision", "Revision of Useful Life / Salvage Value"),
    ]

    VALUATION_METHOD_CHOICES = [
        ("market_approach", "Market Comparable Sales Approach"),
        ("cost_approach", "Depreciated Replacement Cost (DRC)"),
        ("income_approach", "Discounted Cash Flow (DCF) / Value-in-Use"),
        ("independent_appraisal", "Certified Third-Party Appraisal"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Assessment"),
        ("submitted", "Submitted for Financial Approval"),
        ("approved", "Approved / Ledger Updated"),
        ("rejected", "Rejected"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "submitted": "badge-info",
        "approved": "badge-green",
        "rejected": "badge-red",
    }

    EVENT_TYPE_CSS = {
        "impairment": "badge-red",
        "revaluation_up": "badge-green",
        "reversal_impairment": "badge-blue",
        "salvage_revision": "badge-amber",
    }

    # Core Asset Reference
    title = models.CharField(max_length=200, help_text="Revaluation event title / reference")
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.CASCADE,
        related_name="revaluation_events",
        help_text="Financial Fixed Asset being revalued",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revaluation_events",
        help_text="Operational physical asset register entry",
    )

    # Revaluation Metadata
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES, default="impairment")
    valuation_method = models.CharField(max_length=30, choices=VALUATION_METHOD_CHOICES, default="independent_appraisal")
    valuation_date = models.DateField(default=timezone.now, help_text="Effective date of appraisal / impairment assessment")
    appraiser = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_revaluations",
        help_text="Valuation firm, certified appraiser, or internal auditor",
    )
    appraiser_name_fallback = models.CharField(
        max_length=120,
        blank=True,
        help_text="Fallback appraiser name / credentials if not in Party",
    )

    # Balance Comparison
    historical_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Asset original historical acquisition cost",
    )
    accumulated_depreciation_before = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Acc. depreciation immediately prior to revaluation",
    )
    carrying_value_before = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net book value immediately prior to event",
    )
    new_fair_market_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Appraised fair value / recoverable amount",
    )
    revaluation_adjustment = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net adjustment amount (new_fair_value - carrying_value_before)",
    )

    # Prospective Life & Salvage Adjustments
    new_salvage_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Updated residual value for forward depreciation",
    )
    remaining_useful_life_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Revised remaining useful life in months for future runs",
    )

    # General Ledger Accounts
    impairment_loss_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_impairment_losses",
        help_text="P&L Impairment Loss Account",
    )
    revaluation_surplus_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_revaluation_surpluses",
        help_text="Equity: Revaluation Surplus (OCI) Account",
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_revaluations",
    )

    # Documentation & Governance
    reason_and_methodology = models.TextField(
        blank=True,
        help_text="Documented reason, market benchmarks, cash flow discount rates, or damage findings",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_revaluations",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "assets_revaluation"
        ordering = ["-valuation_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_arev_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "fixed_asset"], name="idx_arev_ten_fa"),
            models.Index(fields=["tenant", "event_type"], name="idx_arev_ten_type"),
            models.Index(fields=["tenant", "status"], name="idx_arev_ten_stat"),
            models.Index(fields=["tenant", "valuation_date"], name="idx_arev_ten_date"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_event_type_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def event_type_css(self):
        return self.EVENT_TYPE_CSS.get(self.event_type, "badge-slate")

    def calculate_adjustment(self):
        fa = self.fixed_asset
        self.historical_cost = fa.acquisition_cost or Decimal("0.00")
        self.accumulated_depreciation_before = fa.accumulated_depreciation or Decimal("0.00")
        self.carrying_value_before = max(self.historical_cost - self.accumulated_depreciation_before, Decimal("0.00"))
        self.revaluation_adjustment = (self.new_fair_market_value or Decimal("0.00")) - self.carrying_value_before
        return self.revaluation_adjustment

    def execute_revaluation(self, user=None):
        from apps.accounting.models import JournalEntry, JournalLine

        if self.status == "approved":
            raise ValidationError("This revaluation has already been approved and executed.")

        self.calculate_adjustment()
        adj = self.revaluation_adjustment
        fa = self.fixed_asset

        if adj < Decimal("0.00"):
            if not (self.impairment_loss_account and fa.accumulated_account):
                raise ValidationError(
                    "Both Impairment Loss GL account and Fixed Asset accumulated depreciation account are required to post impairment adjustment."
                )
        elif adj > Decimal("0.00"):
            if not (self.revaluation_surplus_account and fa.asset_account):
                raise ValidationError(
                    "Both Revaluation Surplus GL account and Fixed Asset cost account are required to post revaluation surplus."
                )

        with transaction.atomic():
            je = None
            if adj < Decimal("0.00"):
                loss_amount = abs(adj)
                je = JournalEntry.objects.create(
                    tenant=self.tenant,
                    entry_type="manual",
                    status="posted",
                    entry_date=self.valuation_date,
                    description=f"Impairment Loss for {fa.number} - {fa.name} ({self.number})",
                    reference=f"{self.number}",
                    created_by=user,
                    approved_by=user,
                    posted_at=timezone.now(),
                )
                # Debit Impairment Loss (Expense)
                JournalLine.objects.create(
                    entry=je,
                    gl_account=self.impairment_loss_account,
                    debit=loss_amount,
                    credit=Decimal("0.00"),
                    description=f"Impairment Loss - {fa.name}",
                )
                # Credit Accumulated Depreciation / Asset carrying account
                JournalLine.objects.create(
                    entry=je,
                    gl_account=fa.accumulated_account,
                    debit=Decimal("0.00"),
                    credit=loss_amount,
                    description=f"Impairment Allowance - {fa.name}",
                )
            elif adj > Decimal("0.00"):
                surplus_amount = adj
                je = JournalEntry.objects.create(
                    tenant=self.tenant,
                    entry_type="manual",
                    status="posted",
                    entry_date=self.valuation_date,
                    description=f"Upward Revaluation Surplus for {fa.number} - {fa.name} ({self.number})",
                    reference=f"{self.number}",
                    created_by=user,
                    approved_by=user,
                    posted_at=timezone.now(),
                )
                # Debit Asset Cost Account
                JournalLine.objects.create(
                    entry=je,
                    gl_account=fa.asset_account,
                    debit=surplus_amount,
                    credit=Decimal("0.00"),
                    description=f"Revaluation Step-up - {fa.name}",
                )
                # Credit Revaluation Surplus (OCI / Equity)
                JournalLine.objects.create(
                    entry=je,
                    gl_account=self.revaluation_surplus_account,
                    debit=Decimal("0.00"),
                    credit=surplus_amount,
                    description=f"Revaluation Surplus (OCI) - {fa.name}",
                )

            self.journal_entry = je
            self.status = "approved"
            self.approved_by = user
            self.approved_at = timezone.now()
            self.save()

            # Update FixedAsset ledger prospective parameters
            update_fields = []
            if self.new_salvage_value is not None:
                fa.salvage_value = self.new_salvage_value
                update_fields.append("salvage_value")
            if self.remaining_useful_life_months is not None:
                fa.useful_life_months = self.remaining_useful_life_months
                update_fields.append("useful_life_months")
            if adj < Decimal("0.00"):
                fa.accumulated_depreciation = (fa.accumulated_depreciation or Decimal("0.00")) + abs(adj)
                update_fields.append("accumulated_depreciation")
            elif adj > Decimal("0.00"):
                fa.acquisition_cost = (fa.acquisition_cost or Decimal("0.00")) + adj
                update_fields.append("acquisition_cost")

            if update_fields:
                fa.save(update_fields=update_fields)

        return je
