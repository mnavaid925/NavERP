from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetDisposalRequest(TenantNumbered):
    """
    Asset Disposal & Retirement Request [ADSP-].
    Central multi-tier authorization and governance spine for fixed asset retirement,
    capturing justification, book value analysis, residual appraisal, and realization metrics.
    """

    NUMBER_PREFIX = "ADSP"

    DISPOSAL_METHOD_CHOICES = [
        ("resale", "Commercial Resale / Auction"),
        ("trade_in", "Vendor Trade-in / Exchange"),
        ("scrap_salvage", "Scrap / Salvage & Recycling"),
        ("donation", "Charitable Donation"),
        ("write_off_loss", "Casualty Loss / Write-off"),
    ]

    RETIREMENT_REASON_CHOICES = [
        ("end_of_life", "End of Useful Life"),
        ("uneconomical_repair", "Uneconomical to Repair / Beyond Salvage"),
        ("technological_obsolescence", "Technological Obsolescence"),
        ("damaged_accident", "Accidental Damage / Total Loss"),
        ("lease_expired", "Lease Term Expired"),
        ("redundant_surplus", "Surplus / Facility Closure"),
        ("regulatory_compliance", "Environmental / Safety Regulatory Mandate"),
        ("other", "Other Business Justification"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Initiated)"),
        ("submitted", "Submitted for Review"),
        ("appraised", "Appraised & Assessed"),
        ("approved", "Approved for Disposal"),
        ("in_progress", "Disposal in Progress"),
        ("completed", "Disposal Completed & Closed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "submitted": "badge-amber",
        "appraised": "badge-info",
        "approved": "badge-green",
        "in_progress": "badge-info",
        "completed": "badge-green",
        "rejected": "badge-red",
        "cancelled": "badge-muted",
    }

    DISPOSAL_METHOD_CSS = {
        "resale": "badge-info",
        "trade_in": "badge-green",
        "scrap_salvage": "badge-amber",
        "donation": "badge-slate",
        "write_off_loss": "badge-red",
    }

    RETIREMENT_REASON_CSS = {
        "end_of_life": "badge-slate",
        "uneconomical_repair": "badge-amber",
        "technological_obsolescence": "badge-info",
        "damaged_accident": "badge-red",
        "lease_expired": "badge-slate",
        "redundant_surplus": "badge-muted",
        "regulatory_compliance": "badge-amber",
        "other": "badge-slate",
    }

    title = models.CharField(
        max_length=255,
        help_text="Retirement initiative title or disposal summary",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.CASCADE,
        related_name="disposal_requests",
        help_text="Financial Fixed Asset being retired",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disposal_requests",
        help_text="Operational plant machinery or equipment record",
    )
    category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disposal_requests",
        help_text="Asset category classification",
    )
    cost_center = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_disposal_requests",
        help_text="Owning department or facility cost center",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_asset_disposals",
        help_text="Initiating custodian or equipment engineer",
    )
    appraised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appraised_asset_disposals",
        help_text="Asset valuation specialist or technical appraiser",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_asset_disposals",
        help_text="Authorizing corporate executive or finance manager",
    )
    accounting_disposal = models.ForeignKey(
        "accounting.AssetDisposal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_disposal_requests",
        help_text="Linked general ledger disposal transaction",
    )

    disposal_method = models.CharField(
        max_length=24,
        choices=DISPOSAL_METHOD_CHOICES,
        default="resale",
    )
    retirement_reason = models.CharField(
        max_length=32,
        choices=RETIREMENT_REASON_CHOICES,
        default="end_of_life",
    )
    justification_notes = models.TextField(
        help_text="Detailed justification for asset decommissioning",
    )

    acquisition_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Original capitalized cost basis",
    )
    accumulated_depreciation = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total depreciation booked to date",
    )
    net_book_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Current carrying value",
    )
    estimated_residual_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Appraised salvage or resale recovery value",
    )
    estimated_removal_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Estimated decommissioning, teardown, or freight expense",
    )

    actual_gross_proceeds = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross realization from sale, trade-in, or scrap",
    )
    actual_removal_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Incurred disposal, abatement, or dismantling fees",
    )
    realized_gain_loss = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net financial gain (+) or loss (-) recognized upon disposal",
    )

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="draft",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection if authorization was declined",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_adsp_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_adsp_ten_stat"),
            models.Index(fields=["tenant", "disposal_method"], name="idx_adsp_ten_meth"),
            models.Index(fields=["tenant", "submitted_at"], name="idx_adsp_ten_subm"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_adsp_ten_fa"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def disposal_method_css(self):
        return self.DISPOSAL_METHOD_CSS.get(self.disposal_method, "badge-slate")

    @property
    def retirement_reason_css(self):
        return self.RETIREMENT_REASON_CSS.get(self.retirement_reason, "badge-slate")

    def calculate_gain_loss(self):
        """Calculates realized gain or loss: Proceeds - Removal Cost - Net Book Value."""
        gain_loss = (self.actual_gross_proceeds or Decimal("0.00")) - (
            self.actual_removal_cost or Decimal("0.00")
        ) - (self.net_book_value or Decimal("0.00"))
        self.realized_gain_loss = gain_loss
        return gain_loss

    def complete_disposal(self):
        """
        Marks request completed, recalculates gain/loss, sets completion timestamp,
        and synchronizes FixedAsset and scm.Asset statuses to 'disposed'.
        """
        self.calculate_gain_loss()
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "realized_gain_loss", "updated_at"])

        if self.fixed_asset:
            fa = self.fixed_asset
            if hasattr(fa, "status"):
                fa.status = "disposed"
                fa.save(update_fields=["status", "updated_at"] if hasattr(fa, "updated_at") else ["status"])

        if self.operational_asset:
            oa = self.operational_asset
            if hasattr(oa, "status"):
                oa.status = "disposed"
                oa.save(update_fields=["status", "updated_at"] if hasattr(oa, "updated_at") else ["status"])

        return self

