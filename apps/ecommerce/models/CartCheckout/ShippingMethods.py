from decimal import Decimal

from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class ShippingMethodConfig(TenantNumbered):
    """Configuration for shipping methods, carriers, and calculation rules."""

    CARRIER_CUSTOM = "custom"
    CARRIER_FEDEX = "fedex"
    CARRIER_UPS = "ups"
    CARRIER_USPS = "usps"
    CARRIER_DHL = "dhl"

    CARRIER_CHOICES = [
        (CARRIER_CUSTOM, "Custom / Internal Fleet"),
        (CARRIER_FEDEX, "FedEx"),
        (CARRIER_UPS, "UPS"),
        (CARRIER_USPS, "USPS"),
        (CARRIER_DHL, "DHL"),
    ]

    CALC_FLAT = "flat_rate"
    CALC_WEIGHT = "weight_tiered"
    CALC_FREE_THRESHOLD = "free_threshold"
    CALC_PICKUP = "local_pickup"

    CALC_TYPE_CHOICES = [
        (CALC_FLAT, "Flat Rate"),
        (CALC_WEIGHT, "Weight-Based Tier"),
        (CALC_FREE_THRESHOLD, "Free Above Subtotal Threshold"),
        (CALC_PICKUP, "Local Store Pickup / Free"),
    ]

    NUMBER_PREFIX = "ESHP"

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    carrier = models.CharField(max_length=20, choices=CARRIER_CHOICES, default=CARRIER_CUSTOM)
    calculation_type = models.CharField(max_length=20, choices=CALC_TYPE_CHOICES, default=CALC_FLAT)
    base_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    cost_per_kg = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_days_min = models.PositiveSmallIntegerField(default=3)
    estimated_days_max = models.PositiveSmallIntegerField(default=5)
    destination_countries = models.CharField(max_length=255, default="US,CA", help_text="Comma-separated country ISOs or ALL")
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["sort_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_shp_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "code"], name="ecom_shp_tenant_code_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "sort_order"], name="ecom_shp_tnt_act_sort_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_carrier_display()}) — ${self.base_rate}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def calculate_rate(self, subtotal, total_weight_kg=0):
        """Compute the applicable shipping cost for a given cart subtotal and weight."""
        if self.calculation_type == self.CALC_PICKUP:
            return Decimal("0.00")
        if self.calculation_type == self.CALC_FREE_THRESHOLD and self.free_shipping_threshold:
            if subtotal >= self.free_shipping_threshold:
                return Decimal("0.00")
        if self.calculation_type == self.CALC_WEIGHT:
            weight = Decimal(str(total_weight_kg or 0))
            return (self.base_rate + (self.cost_per_kg * weight)).quantize(Decimal("0.01"))
        return self.base_rate
