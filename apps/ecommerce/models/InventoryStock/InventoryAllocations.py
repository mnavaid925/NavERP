from django.core.exceptions import ValidationError
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class InventoryAllocation(TenantNumbered):
    NUMBER_PREFIX = "EAL"

    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="inventory_allocations",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.CASCADE,
        related_name="inventory_allocations",
    )
    fulfillment_center = models.ForeignKey(
        "ecommerce.FulfillmentCenter",
        on_delete=models.CASCADE,
        related_name="inventory_allocations",
    )

    zone_bin = models.CharField(max_length=50, blank=True, help_text="Warehouse bin, aisle, or shelf coordinate")
    quantity_on_hand = models.IntegerField(default=0, help_text="Total physical units located at this center")
    quantity_allocated = models.IntegerField(default=0, help_text="Units committed to pending customer orders")
    safety_stock_buffer = models.PositiveIntegerField(
        default=0,
        help_text="Safety reserve units withheld from storefronts to prevent overselling",
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Available stock level that automatically flags a low-stock alert",
    )
    is_low_stock_alert = models.BooleanField(
        default=False,
        help_text="System-flagged when Available to Promise <= low_stock_threshold",
    )
    restock_lead_time_days = models.PositiveSmallIntegerField(
        default=7,
        help_text="Supplier replenishment lead time in days",
    )
    last_counted_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of last physical audit")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["variant__sku", "fulfillment_center__priority"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_inv_tenant_num_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "variant", "fulfillment_center"],
                name="ecom_inv_tnt_var_fc_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_low_stock_alert"], name="ecom_inv_tnt_low_alert_idx"),
            models.Index(fields=["tenant", "fulfillment_center"], name="ecom_inv_tnt_fc_idx"),
            models.Index(fields=["tenant", "product"], name="ecom_inv_tnt_prod_idx"),
        ]

    def __str__(self):
        return f"{self.variant.sku} @ {self.fulfillment_center.code} (ATP: {self.available_to_promise})"

    @property
    def available_to_promise(self):
        """
        Net quantity available to digital storefronts:
        ATP = max(0, on_hand - allocated - safety_buffer)
        """
        raw_available = (self.quantity_on_hand or 0) - (self.quantity_allocated or 0) - (self.safety_stock_buffer or 0)
        return max(0, raw_available)

    @property
    def is_out_of_stock(self):
        return self.available_to_promise <= 0

    def clean(self):
        super().clean()
        if self.variant_id and not getattr(self, "product_id", None):
            self.product = self.variant.product
        elif self.variant_id and getattr(self, "product_id", None):
            if self.variant.product_id != self.product_id:
                raise ValidationError({"variant": "Variant does not belong to the selected catalog product."})

        # Update automated low stock alert flag
        self.is_low_stock_alert = bool(self.available_to_promise <= self.low_stock_threshold)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
