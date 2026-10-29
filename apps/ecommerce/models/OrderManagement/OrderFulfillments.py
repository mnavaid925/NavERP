from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class OrderFulfillment(TenantNumbered):
    """
    Decoupled shipment package and fulfillment tracking record.
    Represents an independent consignment of items dispatched from a fulfillment center,
    carrying multi-carrier tracking numbers, delivery dates, and package lifecycles.
    """

    NUMBER_PREFIX = "EFUL"

    PACKAGE_STATUS_CHOICES = [
        ("draft", "Draft / Sourced"),
        ("allocated", "Stock Allocated"),
        ("picking", "Picking Items"),
        ("packing", "Packing Package"),
        ("shipped", "Shipped with Carrier"),
        ("in_transit", "In Transit"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered", "Delivered to Customer"),
        ("failed_delivery", "Delivery Attempt Failed"),
    ]

    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        on_delete=models.CASCADE,
        related_name="fulfillments",
        help_text="Parent order being fulfilled",
    )
    fulfillment_center = models.ForeignKey(
        "ecommerce.FulfillmentCenter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fulfillments",
        help_text="Origin fulfillment warehouse or 3PL center",
    )
    carrier_name = models.CharField(
        max_length=80,
        help_text="Shipping carrier (e.g. FedEx, UPS, DHL, USPS, Local Courier)",
    )
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Carrier shipment consignment tracking number",
    )
    tracking_url = models.URLField(
        blank=True,
        help_text="Direct link to online carrier tracking portal",
    )
    status = models.CharField(
        max_length=25,
        choices=PACKAGE_STATUS_CHOICES,
        default="allocated",
        help_text="Current package transit state",
    )
    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Actual freight postage cost paid to carrier",
    )
    shipped_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when carrier physically collected consignment",
    )
    estimated_delivery_date = models.DateField(
        null=True,
        blank=True,
        help_text="Carrier SLA expected arrival date",
    )
    actual_delivery_date = models.DateField(
        null=True,
        blank=True,
        help_text="Verified proof of delivery date",
    )
    shipping_label_url = models.URLField(
        blank=True,
        help_text="Stored PDF or barcode shipping label document link",
    )
    notification_sent = models.BooleanField(
        default=False,
        help_text="Indicates whether customer delivery notification dispatch has occurred",
    )
    notes = models.TextField(
        blank=True,
        help_text="Operational dispatch remarks and packaging specifications",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_ful_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "order"], name="ecom_ful_tnt_order_idx"),
            models.Index(fields=["tenant", "status"], name="ecom_ful_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} ({self.carrier_name}: {self.tracking_number or 'No Tracking'})"

    def mark_shipped(self):
        """Transition status to shipped, stamp shipped_at, and sync order status."""
        self.status = "shipped"
        self.shipped_at = timezone.now()
        self.save(update_fields=["status", "shipped_at"])
        # Check order fulfillment state
        order = self.order
        if order.status in ("pending_validation", "validated", "processing"):
            order.status = "partially_fulfilled"
            order.fulfillment_status = "partially_fulfilled"
            order.save(update_fields=["status", "fulfillment_status"])

    def mark_delivered(self):
        """Transition status to delivered and stamp actual_delivery_date."""
        self.status = "delivered"
        self.actual_delivery_date = timezone.localdate()
        self.save(update_fields=["status", "actual_delivery_date"])
