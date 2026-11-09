from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetTransfer(TenantNumbered):
    """Asset relocation, inter-department movement, and cost center expense reallocation [AXFR-]."""

    NUMBER_PREFIX = "AXFR"

    TRANSFER_TYPE_CHOICES = [
        ("cost_center", "Cost Center Reallocation"),
        ("inter_department", "Inter-Department Transfer"),
        ("inter_facility", "Inter-Facility / Plant Relocation"),
        ("custodian_reassignment", "Custodian / Employee Handover"),
        ("inter_company", "Inter-Company Transfer (Affiliate)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Transfer Order"),
        ("in_transit", "In Transit / Dispatched"),
        ("completed", "Completed & Accepted"),
        ("rejected", "Rejected / Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_transit": "badge-amber",
        "completed": "badge-green",
        "rejected": "badge-red",
    }

    TRANSFER_TYPE_CSS = {
        "cost_center": "badge-info",
        "inter_department": "badge-blue",
        "inter_facility": "badge-purple",
        "custodian_reassignment": "badge-amber",
        "inter_company": "badge-slate",
    }

    # Core Asset Reference
    title = models.CharField(max_length=200, help_text="Transfer purpose or relocation order reference")
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.CASCADE,
        related_name="transfers",
        help_text="Financial Fixed Asset being reallocated",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers",
        help_text="Operational physical asset register entry",
    )

    transfer_type = models.CharField(max_length=30, choices=TRANSFER_TYPE_CHOICES, default="cost_center")
    transfer_date = models.DateField(default=timezone.now, help_text="Effective transfer date")

    # Source Allocation
    source_department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_from_dept",
    )
    source_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_from_loc",
    )
    source_custodian = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_from_cust",
    )
    source_expense_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_from_gl",
    )

    # Destination Allocation
    destination_department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_to_dept",
    )
    destination_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_to_loc",
    )
    destination_custodian = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_to_cust",
    )
    destination_expense_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers_to_gl",
    )

    # Financial & Cost Metrics
    carrying_value_at_transfer = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net book value at transfer date",
    )
    transportation_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Moving, freight, or decommissioning expenses",
    )
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_transfers",
    )

    # Workflow & Approvals
    reason = models.TextField(blank=True, help_text="Operational justification for asset transfer")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    transferred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_transfers",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_transfers",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "assets_transfer"
        ordering = ["-transfer_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_axfr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "fixed_asset"], name="idx_axfr_ten_fa"),
            models.Index(fields=["tenant", "status"], name="idx_axfr_ten_stat"),
            models.Index(fields=["tenant", "transfer_type"], name="idx_axfr_ten_type"),
            models.Index(fields=["tenant", "transfer_date"], name="idx_axfr_ten_date"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_transfer_type_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def transfer_type_css(self):
        return self.TRANSFER_TYPE_CSS.get(self.transfer_type, "badge-slate")

    def capture_carrying_value(self):
        fa = self.fixed_asset
        cost = fa.acquisition_cost or Decimal("0.00")
        accum = fa.accumulated_depreciation or Decimal("0.00")
        self.carrying_value_at_transfer = max(cost - accum, Decimal("0.00"))
        return self.carrying_value_at_transfer

    def dispatch_transfer(self):
        if self.status != "draft":
            raise ValidationError("Only draft transfer orders can be dispatched.")
        self.capture_carrying_value()
        self.status = "in_transit"
        self.save(update_fields=["status", "carrying_value_at_transfer", "updated_at"])

    def complete_transfer(self, user=None):
        if self.status == "completed":
            raise ValidationError("This transfer has already been completed.")

        self.capture_carrying_value()
        fa = self.fixed_asset
        oa = self.operational_asset

        with transaction.atomic():
            # Update FixedAsset ledger allocations
            update_fa_fields = []
            if self.destination_department:
                fa.location = self.destination_department
                update_fa_fields.append("location")
            if self.destination_custodian:
                fa.custodian = self.destination_custodian
                update_fa_fields.append("custodian")
            if self.destination_expense_account:
                fa.expense_account = self.destination_expense_account
                update_fa_fields.append("expense_account")

            if update_fa_fields:
                fa.save(update_fields=update_fa_fields)

            # Update SCM Operational Asset if present
            if oa:
                update_oa_fields = []
                if self.destination_location:
                    oa.location = self.destination_location
                    update_oa_fields.append("location")
                if self.destination_custodian:
                    oa.custodian = self.destination_custodian
                    update_oa_fields.append("custodian")
                if self.destination_department:
                    oa.org_unit = self.destination_department
                    update_oa_fields.append("org_unit")
                if update_oa_fields:
                    oa.save(update_fields=update_oa_fields)

            self.status = "completed"
            self.received_by = user
            self.completed_at = timezone.now()
            self.save()
