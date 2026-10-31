import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class VendorSubOrder(TenantNumbered):
    NUMBER_PREFIX = "EVSO"

    FULFILLMENT_STATUS_CHOICES = [
        ("unfulfilled", "Unfulfilled"),
        ("allocated", "Stock Allocated"),
        ("picking", "Picking Items"),
        ("packed", "Package Packed"),
        ("shipped", "Shipped with Carrier"),
        ("delivered", "Delivered to Customer"),
        ("cancelled", "Cancelled"),
    ]

    SLA_STATUS_CHOICES = [
        ("on_time", "On Time (Within SLA)"),
        ("near_breach", "Approaching SLA Deadline"),
        ("breached", "SLA Breached (Late Dispatch)"),
    ]

    PAYOUT_STATUS_CHOICES = [
        ("accrued", "Accrued / Pending Settlement"),
        ("in_payout_batch", "Assigned to Payout Batch"),
        ("paid", "Disbursed to Vendor"),
        ("withheld_dispute", "Withheld (Open Dispute)"),
        ("refunded", "Refunded / Cancelled"),
    ]

    DISPUTE_STATUS_CHOICES = [
        ("none", "No Dispute"),
        ("disputed", "Customer Dispute Opened"),
        ("under_investigation", "Under Investigation"),
        ("resolved_merchant", "Resolved in Seller Favor"),
        ("resolved_customer", "Resolved in Buyer Favor (Refund Issued)"),
        ("escalated_to_admin", "Escalated to Operator Admin"),
    ]

    vendor = models.ForeignKey(
        "ecommerce.MarketplaceVendor",
        on_delete=models.PROTECT,
        related_name="sub_orders",
        help_text="Vendor responsible for fulfilling this consignment sub-order",
    )
    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        on_delete=models.CASCADE,
        related_name="vendor_sub_orders",
        help_text="Parent customer eCommerce order",
    )
    payout = models.ForeignKey(
        "ecommerce.VendorPayout",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_orders",
        help_text="Payout batch settlement that cleared this sub-order",
    )
    fulfillment_status = models.CharField(
        max_length=25,
        choices=FULFILLMENT_STATUS_CHOICES,
        default="unfulfilled",
        db_index=True,
        help_text="Consignment logistical fulfillment state",
    )
    sla_status = models.CharField(
        max_length=20,
        choices=SLA_STATUS_CHOICES,
        default="on_time",
        help_text="SLA dispatch compliance status",
    )
    payout_status = models.CharField(
        max_length=25,
        choices=PAYOUT_STATUS_CHOICES,
        default="accrued",
        db_index=True,
        help_text="Disbursement settlement state",
    )
    subtotal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross items subtotal for this vendor consignment",
    )
    shipping_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Shipping fee allocated to this vendor",
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
        help_text="Commission percentage applied to this sub-order",
    )
    commission_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Platform commission fee deducted from gross sales",
    )
    net_vendor_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net amount payable to vendor (Subtotal + Shipping - Commission)",
    )
    carrier_name = models.CharField(
        max_length=80,
        blank=True,
        help_text="Shipping carrier name (e.g. FedEx, DHL, USPS)",
    )
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Consignment parcel tracking number",
    )
    tracking_url = models.URLField(
        blank=True,
        help_text="Direct shipment tracking portal link",
    )
    promised_dispatch_date = models.DateField(
        null=True,
        blank=True,
        help_text="Promised deadline date for vendor dispatch based on vendor lead time",
    )
    dispatched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when vendor handed package to carrier",
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when carrier confirmed customer delivery",
    )
    customer_rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Customer satisfaction score for this seller (1 to 5 stars)",
    )
    customer_feedback = models.TextField(
        blank=True,
        help_text="Customer review comments regarding seller fulfillment",
    )
    seller_response = models.TextField(
        blank=True,
        help_text="Vendor public response to customer feedback",
    )
    rated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when rating was submitted",
    )
    dispute_status = models.CharField(
        max_length=25,
        choices=DISPUTE_STATUS_CHOICES,
        default="none",
        db_index=True,
        help_text="Customer dispute status for this consignment",
    )
    dispute_reason = models.CharField(
        max_length=150,
        blank=True,
        help_text="Reason for dispute (e.g. Late Delivery, Damaged Goods, Missing Item)",
    )
    dispute_notes = models.TextField(
        blank=True,
        help_text="Investigation details, evidence, and customer claims",
    )
    dispute_resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when dispute was closed",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_evso_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "vendor", "fulfillment_status"],
                name="idx_evso_ten_ven_ful",
            ),
            models.Index(
                fields=["tenant", "order"],
                name="idx_evso_ten_order",
            ),
            models.Index(
                fields=["tenant", "payout_status"],
                name="idx_evso_ten_payout",
            ),
            models.Index(
                fields=["tenant", "dispute_status"],
                name="idx_evso_ten_dispute",
            ),
        ]

    def clean(self):
        super().clean()
        if self.subtotal_amount < Decimal("0.00"):
            raise ValidationError({"subtotal_amount": "Subtotal amount cannot be negative."})
        if self.shipping_amount < Decimal("0.00"):
            raise ValidationError({"shipping_amount": "Shipping amount cannot be negative."})
        if self.customer_rating is not None and (self.customer_rating < 1 or self.customer_rating > 5):
            raise ValidationError({"customer_rating": "Customer rating must be between 1 and 5 stars."})

        # Tenant boundary check
        if self.vendor_id and hasattr(self, "tenant_id") and self.vendor.tenant_id != self.tenant_id:
            raise ValidationError({"vendor": "Vendor belongs to another workspace."})
        if self.order_id and hasattr(self, "tenant_id") and self.order.tenant_id != self.tenant_id:
            raise ValidationError({"order": "Order belongs to another workspace."})
        if self.payout_id and hasattr(self, "tenant_id") and self.payout.tenant_id != self.tenant_id:
            raise ValidationError({"payout": "Payout batch belongs to another workspace."})

    def calculate_financials(self):
        """Calculates platform commission and net vendor payout amount."""
        fixed_fee = getattr(self.vendor, "fixed_fee_per_order", Decimal("0.00")) or Decimal("0.00")
        rate = self.commission_rate or Decimal("15.00")
        pct_fee = (self.subtotal_amount * rate) / Decimal("100.00")
        self.commission_amount = Decimal(round(pct_fee + fixed_fee, 2))
        self.net_vendor_amount = Decimal(round((self.subtotal_amount + self.shipping_amount) - self.commission_amount, 2))

    def evaluate_sla(self):
        """Evaluates dispatch deadline vs SLA."""
        if self.fulfillment_status in ("shipped", "delivered"):
            if self.promised_dispatch_date and self.dispatched_at:
                if self.dispatched_at.date() > self.promised_dispatch_date:
                    self.sla_status = "breached"
                else:
                    self.sla_status = "on_time"
            return

        if self.promised_dispatch_date:
            today = timezone.localdate()
            if today > self.promised_dispatch_date:
                self.sla_status = "breached"
            elif today == self.promised_dispatch_date:
                self.sla_status = "near_breach"
            else:
                self.sla_status = "on_time"

    def save(self, *args, **kwargs):
        self.calculate_financials()
        self.evaluate_sla()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} (Order {self.order.number} • {self.vendor.store_name})"
