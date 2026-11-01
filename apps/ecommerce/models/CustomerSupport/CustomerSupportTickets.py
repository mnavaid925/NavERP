from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class CustomerSupportTicket(TenantNumbered):
    NUMBER_PREFIX = "ESTK"

    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("chat", "Live Chat"),
        ("web_form", "Web Contact Form"),
        ("portal", "Customer Portal"),
        ("marketplace", "Marketplace Message"),
        ("phone", "Phone / Voice"),
    ]

    CATEGORY_CHOICES = [
        ("order_tracking_wismo", "Order Tracking (WISMO)"),
        ("return_refund", "Returns & Refunds"),
        ("damaged_defective", "Damaged or Defective Item"),
        ("shipping_delivery", "Shipping & Delivery Issue"),
        ("product_inquiry", "Pre-Purchase Product Inquiry"),
        ("payment_billing", "Payment & Billing"),
        ("account_access", "Customer Account Access"),
        ("general", "General Inquiries"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("new", "New / Unassigned"),
        ("open", "Open / In Progress"),
        ("pending_customer", "Pending Customer Reply"),
        ("waiting_carrier", "Waiting on Carrier / Warehouse"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]

    customer = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
        help_text="Customer profile anchor if registered",
    )
    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
        help_text="Related order context",
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_ecommerce_tickets",
        help_text="Support staff agent assigned to this ticket",
    )
    subject = models.CharField(max_length=255, help_text="Short summary of customer issue")
    customer_name = models.CharField(max_length=150, help_text="Name of shopper or guest")
    customer_email = models.EmailField(help_text="Shopper contact email")
    customer_phone = models.CharField(max_length=32, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="email")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="general")
    priority = models.CharField(max_length=15, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="new")
    initial_message = models.TextField(help_text="Customer inquiry body")
    resolution_summary = models.TextField(blank=True, help_text="Agent resolution notes provided to customer")
    internal_notes = models.TextField(blank=True, help_text="Private internal staff-only notes")
    sla_first_response_due_at = models.DateTimeField(null=True, blank=True)
    sla_resolution_due_at = models.DateTimeField(null=True, blank=True)
    first_responded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_sla_breached = models.BooleanField(default=False)
    is_bot_handled = models.BooleanField(default=False, help_text="Handled by conversational bot")
    bot_handoff_reason = models.CharField(max_length=100, blank=True, help_text="Why bot transferred to human")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_estk_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "priority"], name="idx_estk_ten_stat_prio"),
            models.Index(fields=["tenant", "assigned_agent", "status"], name="idx_estk_ten_agent_stat"),
            models.Index(fields=["tenant", "order"], name="idx_estk_ten_order"),
            models.Index(fields=["tenant", "customer_email"], name="idx_estk_ten_cust_email"),
            models.Index(fields=["tenant", "channel"], name="idx_estk_ten_channel"),
        ]

    def __str__(self):
        return f"{self.number} - {self.subject} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        now = timezone.now()
        if not self.sla_first_response_due_at:
            sla_response_hours = {"urgent": 1, "high": 2, "medium": 8, "low": 24}
            self.sla_first_response_due_at = now + timedelta(hours=sla_response_hours.get(self.priority, 8))
        if not self.sla_resolution_due_at:
            sla_resolution_hours = {"urgent": 4, "high": 12, "medium": 24, "low": 72}
            self.sla_resolution_due_at = now + timedelta(hours=sla_resolution_hours.get(self.priority, 24))

        if self.status in ["resolved", "closed"] and not self.resolved_at:
            self.resolved_at = now
        elif self.status not in ["resolved", "closed"]:
            self.resolved_at = None

        if self.sla_resolution_due_at and now > self.sla_resolution_due_at and self.status not in ["resolved", "closed", "cancelled"]:
            self.is_sla_breached = True

        super().save(*args, **kwargs)
