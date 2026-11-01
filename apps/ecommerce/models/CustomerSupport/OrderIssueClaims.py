from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class OrderIssueClaim(TenantNumbered):
    NUMBER_PREFIX = "ECLM"

    CLAIM_TYPE_CHOICES = [
        ("damaged_item", "Damaged Item in Transit"),
        ("lost_in_transit", "Lost in Transit / Package Not Received"),
        ("wrong_item", "Wrong Item Received"),
        ("missing_parts", "Missing Item / Partial Shipment"),
        ("defective_product", "Defective / Malfunctioning Product"),
        ("late_delivery", "Late Delivery SLA Breach"),
    ]

    STATUS_CHOICES = [
        ("submitted", "Submitted by Customer"),
        ("under_review", "Under Staff Review"),
        ("carrier_investigation", "Carrier Investigation Pending"),
        ("approved", "Claim Approved"),
        ("rejected", "Claim Rejected"),
        ("completed", "Resolution Completed"),
    ]

    RESOLUTION_CHOICES = [
        ("pending", "Pending Review"),
        ("replacement_reship", "Reship Replacement Item"),
        ("full_refund", "Full Refund to Original Payment"),
        ("partial_refund", "Partial Refund Adjustment"),
        ("store_credit", "Store Credit / Gift Voucher"),
        ("repair", "Product Repair / Service"),
        ("rejected", "No Action / Claim Denied"),
    ]

    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        on_delete=models.CASCADE,
        related_name="issue_claims",
        help_text="Order against which claim is filed",
    )
    customer = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_claims",
        help_text="Shopper account profile",
    )
    ticket = models.ForeignKey(
        "ecommerce.CustomerSupportTicket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_claims",
        help_text="Associated customer support ticket",
    )
    claim_type = models.CharField(max_length=30, choices=CLAIM_TYPE_CHOICES, default="damaged_item")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="submitted")
    claimed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Amount requested by customer",
    )
    approved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Authorized refund or credit amount",
    )
    resolution_action = models.CharField(max_length=30, choices=RESOLUTION_CHOICES, default="pending")
    carrier_tracking_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Carrier shipment tracking number",
    )
    photo_evidence_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL of customer photo upload showing damaged box or merchandise",
    )
    customer_notes = models.TextField(help_text="Customer explanation of damage or loss")
    decision_notes = models.TextField(blank=True, help_text="Staff review rationale")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_order_claims",
        help_text="Staff supervisor reviewing this claim",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_eclm_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "order", "status"], name="idx_eclm_ten_ord_stat"),
            models.Index(fields=["tenant", "status", "claim_type"], name="idx_eclm_ten_stat_type"),
            models.Index(fields=["tenant", "claim_type"], name="idx_eclm_ten_claim_type"),
        ]

    def __str__(self):
        return f"{self.number} - Order {self.order.number} ({self.get_claim_type_display()})"

    def save(self, *args, **kwargs):
        if self.status in ["approved", "rejected", "completed"] and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)
