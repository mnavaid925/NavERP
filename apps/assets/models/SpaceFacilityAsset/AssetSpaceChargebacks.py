"""Space Chargeback, Utility Recovery & Leasehold TI Coordination model (11.17)."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.assets.models._base import TenantNumbered
from apps.assets.models.SpaceFacilityAsset._validators import (
    add_field_error,
    validate_non_negative,
    validate_pct_range,
    validate_tenant_fks,
)


class AssetSpaceChargeback(TenantNumbered):
    """Departmental space chargebacks, CAM/utility recoveries, shared asset allocations, & TI coordination [AFCB]."""

    NUMBER_PREFIX = "AFCB"

    COORDINATION_TYPE_CHOICES = [
        ("space_chargeback", "Departmental Space Chargeback"),
        ("shared_asset_allocation", "Shared System / Asset Allocation"),
        ("cam_utility_recovery", "CAM & Utility Recovery"),
        ("leasehold_improvement", "Leasehold Improvement (TI)"),
        ("ti_allowance_amortization", "TI Allowance Amortization"),
    ]

    ALLOCATION_BASIS_CHOICES = [
        ("usable_sqft", "Usable SqFt"),
        ("rentable_sqft", "Rentable SqFt"),
        ("headcount", "Headcount / Seats"),
        ("submeter_usage", "Submeter Usage"),
        ("fixed_split_pct", "Fixed Percentage Split"),
        ("direct_ti_cost", "Direct TI Cost"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("posted_to_gl", "Posted to GL"),
        ("invoiced", "Invoiced"),
        ("disputed", "Disputed"),
        ("closed", "Closed"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "pending_approval": "badge-amber",
        "approved": "badge-info",
        "posted_to_gl": "badge-green",
        "invoiced": "badge-green",
        "disputed": "badge-red",
        "closed": "badge-muted",
    }

    EDITABLE_STATUSES = {"draft", "disputed"}
    LOCKED_STATUSES = {"approved", "posted_to_gl", "invoiced", "closed"}

    # NOTE: currency is GLOBAL (no tenant FK) and intentionally excluded here.
    _TENANT_FK_FIELDS = (
        "facility_space",
        "shared_building_system",
        "lease_contract",
        "fixed_asset",
        "charged_org_unit",
        "occupant_party",
        "fiscal_period",
        "expense_gl_account",
        "recovery_gl_account",
        "journal_entry",
        "ar_invoice",
    )

    title = models.CharField(max_length=200)
    coordination_type = models.CharField(
        max_length=36,
        choices=COORDINATION_TYPE_CHOICES,
        default="space_chargeback",
    )
    allocation_basis = models.CharField(
        max_length=24,
        choices=ALLOCATION_BASIS_CHOICES,
        default="usable_sqft",
    )

    facility_space = models.ForeignKey(
        "assets.AssetFacilitySpace",
        on_delete=models.PROTECT,
        related_name="space_chargebacks",
    )
    shared_building_system = models.ForeignKey(
        "assets.AssetBuildingSystem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_chargebacks",
    )
    lease_contract = models.ForeignKey(
        "assets.AssetLeaseContract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_chargebacks",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_chargebacks",
    )
    charged_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_chargebacks",
    )
    occupant_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_chargebacks",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_chargebacks",
    )
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_chargebacks",
    )
    expense_gl_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_space_chargebacks",
    )
    recovery_gl_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_space_chargebacks",
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name="space_chargebacks",
    )
    ar_invoice = models.ForeignKey(
        "accounting.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_chargebacks",
    )

    period_start = models.DateField()
    period_end = models.DateField()
    amortization_end_date = models.DateField(null=True, blank=True)

    allocated_area_sqft = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    allocation_share_pct = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("100.00"),
    )
    base_cost_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    shared_cam_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    utility_recovery_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    ti_improvement_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    ti_allowance_offset = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    net_chargeback_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="draft",
        editable=False,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="approved_space_chargebacks",
    )
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_start", "-number"]
        verbose_name = "Space Chargeback & Occupancy Coordination"
        verbose_name_plural = "Space Chargebacks & Occupancy Coordination"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_afcb_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_afcb_ten_stat"),
            models.Index(fields=["tenant", "coordination_type"], name="idx_afcb_ten_type"),
            models.Index(fields=["tenant", "allocation_basis"], name="idx_afcb_ten_basis"),
            models.Index(fields=["tenant", "facility_space"], name="idx_afcb_ten_spc"),
            models.Index(fields=["tenant", "charged_org_unit"], name="idx_afcb_ten_org"),
            models.Index(fields=["tenant", "period_start", "period_end"], name="idx_afcb_ten_per"),
        ]

    def compute_net_chargeback(self):
        base = self.base_cost_amount or Decimal("0.00")
        cam = self.shared_cam_amount or Decimal("0.00")
        utility = self.utility_recovery_amount or Decimal("0.00")
        ti_cost = self.ti_improvement_cost or Decimal("0.00")
        ti_offset = self.ti_allowance_offset or Decimal("0.00")
        net_ti = max(Decimal("0.00"), ti_cost - ti_offset)
        return (base + cam + utility + net_ti).quantize(Decimal("0.01"))

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def can_edit(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def clean(self):
        super().clean()
        errors = {}
        if self.tenant_id:
            validate_tenant_fks(self, errors, self._TENANT_FK_FIELDS)

        if self.period_start and self.period_end and self.period_end < self.period_start:
            add_field_error(errors, "period_end", "Period end date cannot precede period start date.")

        if (
            self.period_start
            and self.amortization_end_date
            and self.amortization_end_date < self.period_start
        ):
            add_field_error(
                errors,
                "amortization_end_date",
                "TI amortization end date cannot precede period start date.",
            )

        if (
            self.expense_gl_account_id
            and self.recovery_gl_account_id
            and self.expense_gl_account_id == self.recovery_gl_account_id
        ):
            add_field_error(
                errors,
                "recovery_gl_account",
                "Recovery GL account must differ from expense GL account.",
            )

        validate_pct_range(
            self.allocation_share_pct,
            errors,
            "allocation_share_pct",
            "Allocation share %",
        )
        for fld, label in (
            ("allocated_area_sqft", "Allocated area"),
            ("base_cost_amount", "Base cost amount"),
            ("shared_cam_amount", "Shared CAM amount"),
            ("utility_recovery_amount", "Utility recovery amount"),
            ("ti_improvement_cost", "TI improvement cost"),
            ("ti_allowance_offset", "TI allowance offset"),
        ):
            validate_non_negative(getattr(self, fld), errors, fld, label)

        base = self.base_cost_amount or Decimal("0.00")
        cam = self.shared_cam_amount or Decimal("0.00")
        utility = self.utility_recovery_amount or Decimal("0.00")
        ti_cost = self.ti_improvement_cost or Decimal("0.00")
        ti_offset = self.ti_allowance_offset or Decimal("0.00")
        raw_total = base + cam + utility + max(Decimal("0.00"), ti_cost - ti_offset)
        if raw_total > Decimal("99999999999999.99"):
            add_field_error(
                errors,
                "base_cost_amount",
                "Combined net chargeback exceeds the maximum supported value of 99,999,999,999,999.99.",
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.net_chargeback_amount = self.compute_net_chargeback()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} — {self.title}"
