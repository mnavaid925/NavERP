from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class ReturnMerchandiseAuthorization(TenantNumbered):
    """
    Reverse logistics, returns, and exchange management (RMA).
    Orchestrates customer return authorization, return shipping labels,
    inspection disposition, restocking logic, and financial settlement.
    """

    NUMBER_PREFIX = "ERMA"

    RETURN_TYPE_CHOICES = [
        ("refund", "Refund to Original Payment"),
        ("exchange", "Exchange for Alternate Variant"),
        ("store_credit", "Store Credit / Voucher"),
    ]

    RMA_STATUS_CHOICES = [
        ("requested", "Return Requested"),
        ("authorized", "Authorized & Label Issued"),
        ("label_generated", "Return Label Generated"),
        ("in_transit", "In Transit back to Center"),
        ("received", "Received at Center"),
        ("inspected", "Inspected & Evaluated"),
        ("approved", "Approved for Settlement"),
        ("rejected", "Rejected / Denied"),
        ("completed", "Completed & Settled"),
    ]

    RETURN_REASON_CHOICES = [
        ("damaged_defective", "Damaged or Defective"),
        ("wrong_item_sent", "Wrong Item Sent"),
        ("size_fit_issue", "Size or Fit Issue"),
        ("not_as_described", "Item Not as Described"),
        ("changed_mind", "Customer Changed Mind"),
        ("late_delivery", "Late Delivery Arrival"),
        ("other", "Other Reason"),
    ]

    REFUND_STATUS_CHOICES = [
        ("pending", "Pending Approval"),
        ("processed", "Refund Processed"),
        ("failed", "Refund Failed"),
        ("waived", "Fee Waived / No Refund"),
    ]

    RESTOCK_STATUS_CHOICES = [
        ("pending", "Pending Restock Inspection"),
        ("restocked", "Restocked to Active Inventory"),
        ("scrapped", "Damaged / Scrapped"),
        ("quarantined", "Quarantined for Review"),
    ]

    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        on_delete=models.CASCADE,
        related_name="returns",
        help_text="Original customer eCommerce order",
    )
    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="ecommerce_returns",
        help_text="Customer initiating return request",
    )
    return_type = models.CharField(
        max_length=20,
        choices=RETURN_TYPE_CHOICES,
        default="refund",
        help_text="Settlement channel requested by customer",
    )
    status = models.CharField(
        max_length=25,
        choices=RMA_STATUS_CHOICES,
        default="requested",
        help_text="RMA inspection and reverse logistics state",
    )
    reason = models.CharField(
        max_length=30,
        choices=RETURN_REASON_CHOICES,
        default="changed_mind",
        help_text="Customer stated return justification",
    )
    return_shipping_label_url = models.URLField(
        blank=True,
        help_text="Inbound reverse courier shipping label PDF link",
    )
    return_tracking_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Carrier tracking number for return consignment",
    )
    restocking_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Deduction charged for return processing and repackaging",
    )
    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated net reimbursement amount",
    )
    refund_status = models.CharField(
        max_length=20,
        choices=REFUND_STATUS_CHOICES,
        default="pending",
        help_text="Gateway refund transmission state",
    )
    restocking_status = models.CharField(
        max_length=20,
        choices=RESTOCK_STATUS_CHOICES,
        default="pending",
        help_text="Physical inventory disposition assessment",
    )
    restocking_center = models.ForeignKey(
        "ecommerce.FulfillmentCenter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rma_restocks",
        help_text="Target warehouse location accepting returned consignment",
    )
    customer_notes = models.TextField(
        blank=True,
        help_text="Remarks provided by customer upon initiating return",
    )
    inspection_notes = models.TextField(
        blank=True,
        help_text="Staff warehouse inspection findings and condition notes",
    )
    authorized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when RMA was authorized by staff",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when settlement and refund were finalized",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_rma_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "order"], name="ecom_rma_tnt_order_idx"),
            models.Index(fields=["tenant", "status"], name="ecom_rma_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} ({self.get_return_type_display()} - {self.order.number})"

    def authorize(self):
        """Authorize return and issue label authorization timestamp."""
        self.status = "authorized"
        self.authorized_at = timezone.now()
        self.save(update_fields=["status", "authorized_at"])

    def complete_settlement(self):
        """Finalize return settlement and update completion timestamp."""
        self.status = "completed"
        self.completed_at = timezone.now()
        self.refund_status = "processed"
        self.save(update_fields=["status", "completed_at", "refund_status"])
