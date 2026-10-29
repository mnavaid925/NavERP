from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class BackorderPolicy(TenantNumbered):
    NUMBER_PREFIX = "EBK"

    POLICY_TYPE_CHOICES = [
        ("deny_when_empty", "Deny When Out of Stock (Standard)"),
        ("allow_backorder_with_notice", "Allow Backorders with Warning Notice"),
        ("pre_order_only", "Pre-Order Mode (Advance Campaign)"),
    ]

    variant = models.OneToOneField(
        "ecommerce.ProductVariant",
        on_delete=models.CASCADE,
        related_name="backorder_policy",
    )
    policy_type = models.CharField(max_length=35, choices=POLICY_TYPE_CHOICES, default="deny_when_empty")
    storefront_message = models.CharField(
        max_length=255,
        blank=True,
        help_text="Customer-facing availability message (e.g. 'Backordered. Expected to ship Dec 15th.')",
    )
    expected_availability_date = models.DateField(
        null=True,
        blank=True,
        help_text="Target restock or product release date",
    )
    max_backorder_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Cap on allowed backorders (0 = unlimited backorders permitted)",
    )
    current_backorder_count = models.PositiveIntegerField(
        default=0,
        help_text="Total customer orders committed under backorder / pre-order status",
    )
    auto_notify_waitlist = models.BooleanField(
        default=True,
        help_text="Automatically send email/SMS notifications to customers when restocked",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["variant__sku"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_bk_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "variant"], name="ecom_bk_tenant_var_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "policy_type"], name="ecom_bk_tnt_policy_idx"),
            models.Index(fields=["tenant", "is_active"], name="ecom_bk_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.variant.sku} — {self.get_policy_type_display()}"

    @property
    def is_backorder_allowed(self):
        """
        Whether storefront should permit checkout when ATP is zero:
        1. Policy must be active
        2. Policy cannot be 'deny_when_empty'
        3. If max_backorder_quantity > 0, current_backorder_count must be below cap
        """
        if not self.is_active or self.policy_type == "deny_when_empty":
            return False
        if self.max_backorder_quantity > 0:
            return self.current_backorder_count < self.max_backorder_quantity
        return True

    @property
    def remaining_capacity(self):
        if self.max_backorder_quantity == 0:
            return None  # unlimited
        return max(0, self.max_backorder_quantity - self.current_backorder_count)
