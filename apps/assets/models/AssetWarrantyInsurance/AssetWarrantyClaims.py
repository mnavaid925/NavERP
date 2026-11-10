from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetWarrantyClaim(TenantNumbered):
    """
    Asset warranty defect claim submission and settlement tracking [AWCL-].
    Tracks OEM warranty claims, defect symptoms, repair orders, RMA and defective
    component return logistics, claimed vs authorized recovery amounts, and final settlement.
    """

    NUMBER_PREFIX = "AWCL"

    CLAIM_STATUS_CHOICES = [
        ("draft", "Draft (Claim Preparation)"),
        ("submitted", "Submitted to Warrantor / OEM"),
        ("under_review", "Under Technical Review"),
        ("approved", "Approved in Full"),
        ("partially_approved", "Partially Approved (Adjusted)"),
        ("rejected", "Rejected / Denied"),
        ("settled_closed", "Settled & Closed"),
    ]

    RESOLUTION_TYPE_CHOICES = [
        ("pending_evaluation", "Pending OEM Evaluation"),
        ("parts_replacement", "OEM Direct Parts Replacement"),
        ("on_site_repair", "On-Site Factory Authorized Repair"),
        ("depot_repair", "Factory Depot Repair / Overhaul"),
        ("cash_reimbursement", "Direct Cash Reimbursement"),
        ("credit_memo", "Vendor Credit Memo on Account"),
        ("rejected_uncovered", "Rejected / Excluded from Coverage"),
    ]

    PART_RETURN_STATUS_CHOICES = [
        ("not_required", "Defective Part Scrap on Site (Return Not Required)"),
        ("return_required_pending", "Defective Part Return Required (Pending Shipment)"),
        ("shipped_in_transit", "Defective Part Shipped to OEM (In Transit)"),
        ("received_inspected_by_oem", "Received & Authenticated by OEM Depot"),
    ]

    CLAIM_STATUS_CSS = {
        "draft": "badge-slate",
        "submitted": "badge-info",
        "under_review": "badge-amber",
        "approved": "badge-green",
        "partially_approved": "badge-amber",
        "rejected": "badge-red",
        "settled_closed": "badge-muted",
    }

    RESOLUTION_TYPE_CSS = {
        "pending_evaluation": "badge-slate",
        "parts_replacement": "badge-info",
        "on_site_repair": "badge-green",
        "depot_repair": "badge-amber",
        "cash_reimbursement": "badge-green",
        "credit_memo": "badge-info",
        "rejected_uncovered": "badge-red",
    }

    PART_RETURN_STATUS_CSS = {
        "not_required": "badge-slate",
        "return_required_pending": "badge-amber",
        "shipped_in_transit": "badge-info",
        "received_inspected_by_oem": "badge-green",
    }

    title = models.CharField(
        max_length=255,
        help_text="Warranty claim headline or defect summary",
    )
    warranty = models.ForeignKey(
        "assets.AssetWarranty",
        on_delete=models.CASCADE,
        related_name="claims",
        help_text="Covering warranty policy",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warranty_claims",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warranty_claims",
        help_text="Operational equipment record",
    )
    maintenance_request = models.ForeignKey(
        "assets.AssetMaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warranty_claims",
        help_text="Originating corrective maintenance work order or ticket",
    )
    incident_date = models.DateField(
        help_text="Date defect or component failure occurred",
    )
    operating_meter_at_failure = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Meter reading at time of failure (hours/km)",
    )
    defect_description = models.TextField(
        help_text="Detailed physical failure symptom, root cause analysis, or diagnostic code",
    )
    warrantor_claim_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="OEM / vendor RMA or ticket tracking number",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_warranty_claims",
        help_text="Currency of claim valuation",
    )
    claimed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total cost claimed (parts + labor + dispatch)",
    )
    approved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Amount accepted/authorized by warrantor",
    )
    deductible_applied = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Tenant warranty deductible deducted from settlement",
    )
    net_recovery_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net payout/credit recovered (Approved - Deductible)",
    )
    resolution_type = models.CharField(
        max_length=28,
        choices=RESOLUTION_TYPE_CHOICES,
        default="pending_evaluation",
    )
    claim_status = models.CharField(
        max_length=24,
        choices=CLAIM_STATUS_CHOICES,
        default="draft",
    )
    part_return_status = models.CharField(
        max_length=32,
        choices=PART_RETURN_STATUS_CHOICES,
        default="not_required",
    )
    rma_tracking_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Courier shipping tracking for return of core/failed assembly",
    )
    submission_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date formal claim submitted to warrantor",
    )
    settlement_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date claim settled or credit/payment received",
    )
    settlement_notes = models.TextField(
        blank=True,
        help_text="Settlement reconciliation or rejection justification notes",
    )
    filed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filed_asset_warranty_claims",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authorized_asset_warranty_claims",
    )
    supporting_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_warranty_claims",
        help_text="Diagnostic report, photos, or OEM settlement letter",
    )

    class Meta:
        ordering = ["-incident_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_awcl_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "claim_status"], name="idx_awcl_ten_stat"),
            models.Index(fields=["tenant", "incident_date"], name="idx_awcl_ten_date"),
            models.Index(fields=["tenant", "warranty"], name="idx_awcl_ten_war"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_awcl_ten_fa"),
            models.Index(fields=["tenant", "resolution_type"], name="idx_awcl_ten_res"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def claim_status_css(self):
        return self.CLAIM_STATUS_CSS.get(self.claim_status, "badge-slate")

    @property
    def resolution_type_css(self):
        return self.RESOLUTION_TYPE_CSS.get(self.resolution_type, "badge-slate")

    @property
    def part_return_status_css(self):
        return self.PART_RETURN_STATUS_CSS.get(self.part_return_status, "badge-slate")
