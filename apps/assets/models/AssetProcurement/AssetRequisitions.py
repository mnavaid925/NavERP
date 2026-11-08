from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetRequisition(TenantNumbered):
    """Capital expenditure (CapEx) requisition for equipment, machinery, and physical assets [AREQ-]."""

    NUMBER_PREFIX = "AREQ"

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("ordered", "PO Issued / Ordered"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]

    CATEGORY_CHOICES = [
        ("machinery", "Plant & Heavy Machinery"),
        ("vehicle", "Fleet & Commercial Vehicle"),
        ("it_hardware", "IT & Computer Equipment"),
        ("tooling", "Tooling & Test Equipment"),
        ("facility", "Building & Facility Equipment"),
        ("office_furniture", "Furniture & Fixtures"),
        ("other", "Other Capital Asset"),
    ]

    # Design system badge colours (theme.css: badge-green, badge-red, badge-amber, badge-info, badge-muted, badge-slate ONLY)
    STATUS_CSS = {
        "draft": "badge-slate",
        "pending_approval": "badge-amber",
        "approved": "badge-green",
        "rejected": "badge-red",
        "ordered": "badge-info",
        "received": "badge-green",
        "cancelled": "badge-muted",
    }

    PRIORITY_CSS = {
        "low": "badge-muted",
        "medium": "badge-info",
        "high": "badge-amber",
        "urgent": "badge-red",
    }

    # Core identification & justification
    title = models.CharField(max_length=200, help_text="Short summary of capital request")
    description = models.TextField(blank=True, help_text="Detailed operational specifications and requirements")
    business_justification = models.TextField(help_text="CapEx justification, expected ROI, or replacement driver")

    # Classification & financial estimation
    asset_category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default="machinery")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    estimated_cost = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_requisitions",
    )
    budget_code = models.CharField(max_length=64, blank=True, help_text="Capital budget line item or project code")

    # Sourcing preferences
    proposed_vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposed_asset_requisitions",
    )
    proposed_manufacturer = models.CharField(max_length=120, blank=True)
    proposed_model = models.CharField(max_length=100, blank=True)
    required_delivery_date = models.DateField(null=True, blank=True)

    # Destination in plant / organization
    target_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_asset_requisitions",
        help_text="Target department or operational cost center",
    )
    target_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_asset_requisitions",
        help_text="Intended physical facility or plant room",
    )

    # Lifecycle & workflow
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_asset_requisitions",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_asset_requisitions",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Procurement link
    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_requisitions",
        help_text="SCM Purchase Order issued for this capital equipment",
    )

    class Meta:
        db_table = "assets_requisition"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_areq_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_areq_ten_stat"),
            models.Index(fields=["tenant", "priority"], name="idx_areq_ten_prio"),
            models.Index(fields=["tenant", "asset_category"], name="idx_areq_ten_cat"),
            models.Index(fields=["tenant", "created_at"], name="idx_areq_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def priority_css(self):
        return self.PRIORITY_CSS.get(self.priority, "badge-info")

    def can_submit(self):
        return self.status in ("draft", "rejected")

    def can_approve(self):
        return self.status == "pending_approval"

    def can_reject(self):
        return self.status == "pending_approval"
