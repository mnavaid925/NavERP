from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetLeaseModification(TenantNumbered):
    """
    Asset Lease Modification & Remeasurement [ALMD-].
    Governs formal lease contract amendments, term extensions, payment adjustments,
    partial or full early terminations, and ROU asset impairments with automated
    remeasured liability calculations.
    """

    NUMBER_PREFIX = "ALMD"

    MODIFICATION_TYPE_CHOICES = [
        ("term_extension", "Lease Term Extension"),
        ("payment_change", "Payment Amount Adjustment"),
        ("partial_termination", "Partial Scope / Asset Reduction"),
        ("full_termination", "Full Early Termination"),
        ("impairment", "ROU Asset Impairment Write-down"),
        ("discount_rate_change", "Discount Rate / IBR Remeasurement"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Amendment"),
        ("submitted", "Submitted for Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("executed", "Executed & Remeasured"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "submitted": "badge-amber",
        "approved": "badge-info",
        "rejected": "badge-red",
        "executed": "badge-green",
    }

    MODIFICATION_TYPE_CSS = {
        "term_extension": "badge-info",
        "payment_change": "badge-slate",
        "partial_termination": "badge-amber",
        "full_termination": "badge-red",
        "impairment": "badge-red",
        "discount_rate_change": "badge-slate",
    }

    lease_contract = models.ForeignKey(
        "assets.AssetLeaseContract",
        on_delete=models.CASCADE,
        related_name="modifications",
        help_text="Lease agreement modified",
    )
    modification_type = models.CharField(
        max_length=30,
        choices=MODIFICATION_TYPE_CHOICES,
        default="term_extension",
    )
    request_date = models.DateField(
        default=timezone.now,
        help_text="Date modification was requested",
    )
    effective_date = models.DateField(
        default=timezone.now,
        help_text="Effective accounting date of modification",
    )

    # Balances Before & After
    prior_lease_liability = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Carrying lease liability before remeasurement",
    )
    revised_lease_liability = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Remeasured present value of remaining lease payments",
    )
    liability_adjustment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net change in lease liability (+/-)",
    )
    prior_rou_asset_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Carrying ROU asset value before remeasurement",
    )
    revised_rou_asset_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Remeasured ROU asset carrying value",
    )
    rou_asset_adjustment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net adjustment to ROU asset basis (+/-)",
    )

    # Accounting Gain/Loss
    gain_loss_on_modification = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gain (+) or loss (-) recognized on partial/full termination",
    )
    impairment_loss_recognized = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Impairment loss recognized against ROU asset",
    )

    # Revised Terms
    revised_term_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="New total lease duration if term is amended",
    )
    revised_payment_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="New periodic payment amount if rent is amended",
    )
    revised_discount_rate_pct = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Updated IBR discount rate at modification date",
    )

    # Governance
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_lease_modifications",
        help_text="Contract administrator requesting amendment",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_lease_modifications",
        help_text="Corporate controller approving remeasurement",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    justification = models.TextField(
        blank=True,
        help_text="Commercial and operational justification for lease modification",
    )
    notes = models.TextField(
        blank=True,
        help_text="Audit remarks and accounting documentation notes",
    )

    class Meta:
        ordering = ["-effective_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_almd_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "lease_contract"], name="idx_almd_ten_ctr"),
            models.Index(fields=["tenant", "status"], name="idx_almd_ten_stat"),
            models.Index(fields=["tenant", "effective_date"], name="idx_almd_ten_eff"),
            models.Index(fields=["tenant", "modification_type"], name="idx_almd_ten_type"),
        ]

    def __str__(self):
        contract_num = self.lease_contract.number if self.lease_contract_id else ""
        if contract_num:
            return f"{self.number} — {self.get_modification_type_display()} ({contract_num})"
        return f"{self.number} — {self.get_modification_type_display()}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def type_css(self):
        return self.MODIFICATION_TYPE_CSS.get(self.modification_type, "badge-slate")
