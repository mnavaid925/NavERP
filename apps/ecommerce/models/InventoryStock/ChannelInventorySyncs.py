from decimal import Decimal

from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class ChannelInventorySync(TenantNumbered):
    NUMBER_PREFIX = "ESYN"

    CHANNEL_TYPE_CHOICES = [
        ("web_storefront", "Direct Web Storefront"),
        ("amazon_marketplace", "Amazon Marketplace"),
        ("walmart_marketplace", "Walmart Marketplace"),
        ("pos_retail", "Retail POS Register"),
        ("wholesale_b2b", "B2B Wholesale Portal"),
    ]

    SYNC_MODE_CHOICES = [
        ("real_time", "Real-Time Event Sync"),
        ("scheduled_batch", "Scheduled Batch"),
        ("manual", "Manual Push Only"),
    ]

    SYNC_STATUS_CHOICES = [
        ("synced", "In Sync"),
        ("pending", "Sync Pending"),
        ("sync_error", "Sync Error"),
        ("disabled", "Disabled"),
    ]

    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.CASCADE,
        related_name="channel_syncs",
    )
    channel_type = models.CharField(max_length=30, choices=CHANNEL_TYPE_CHOICES, default="web_storefront")
    channel_name = models.CharField(max_length=100, help_text="e.g. US Amazon Prime, Downtown Retail POS")
    fulfillment_center = models.ForeignKey(
        "ecommerce.FulfillmentCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="channel_syncs",
        help_text="Optional specific warehouse dedicated to this channel (leave blank for aggregated stock pool)",
    )
    sync_mode = models.CharField(max_length=25, choices=SYNC_MODE_CHOICES, default="real_time")
    allocation_buffer_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Percentage buffer withheld to prevent marketplace overselling (e.g. 5.00%)",
    )
    last_synced_quantity = models.IntegerField(default=0, help_text="Quantity last broadcasted to external feed")
    sync_status = models.CharField(max_length=25, choices=SYNC_STATUS_CHOICES, default="synced")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["variant__sku", "channel_type"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_sync_tenant_num_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "variant", "channel_type", "channel_name"],
                name="ecom_sync_tnt_var_chn_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "sync_status"], name="ecom_sync_tnt_stat_idx"),
            models.Index(fields=["tenant", "channel_type"], name="ecom_sync_tnt_chntyp_idx"),
        ]

    def __str__(self):
        return f"{self.channel_name} ({self.variant.sku}) — {self.get_sync_status_display()}"

    def calculate_sync_quantity(self):
        """
        Calculate available quantity to broadcast to this digital channel,
        factoring in channel-specific warehouse constraints and safety buffer percentages.
        """
        allocations = self.variant.inventory_allocations.all()
        if self.fulfillment_center_id:
            allocations = allocations.filter(fulfillment_center_id=self.fulfillment_center_id)

        total_atp = sum(alloc.available_to_promise for alloc in allocations)

        if self.allocation_buffer_pct > 0:
            buffer_multiplier = Decimal("1.0") - (self.allocation_buffer_pct / Decimal("100.0"))
            calculated = int(Decimal(str(total_atp)) * buffer_multiplier)
            return max(0, calculated)

        return max(0, total_atp)
