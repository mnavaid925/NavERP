import math
from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class MobileLocationRule(TenantNumbered):
    NUMBER_PREFIX = "EMLR"

    RULE_TYPE_CHOICES = [
        ("store_locator", "Store Locator Directory Pin"),
        ("geofence_entry", "Geofence Entry Trigger (Welcome)"),
        ("geofence_exit", "Geofence Exit Trigger (Departure)"),
        ("geofence_dwell", "Geofence Dwell Trigger (Browsing In-Store)"),
        ("curbside_pickup", "Curbside Pickup Arrival Radar"),
    ]

    TRIGGER_ACTION_CHOICES = [
        ("display_store_mode", "Switch App to In-Store Shopping Mode"),
        ("send_push_notification", "Send Proximity Push Notification"),
        ("apply_coupon", "Unlock Proximity Coupon Promotion"),
        ("notify_store_associates", "Alert In-Store Staff for Curbside Hand-Off"),
    ]

    name = models.CharField(
        max_length=120,
        help_text="Friendly rule name (e.g. Downtown Flagship Welcome Geofence)",
    )
    rule_type = models.CharField(
        max_length=30,
        choices=RULE_TYPE_CHOICES,
        default="store_locator",
    )
    fulfillment_center = models.ForeignKey(
        "ecommerce.FulfillmentCenter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="location_rules",
        help_text="Linked physical retail store fulfillment center",
    )
    store_name = models.CharField(
        max_length=120,
        help_text="Retail store name displayed in mobile store locator",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text="Store or geofence center GPS latitude (e.g. 40.712776)",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text="Store or geofence center GPS longitude (e.g. -74.005974)",
    )
    radius_meters = models.PositiveIntegerField(
        default=500,
        help_text="Circular geofence radius in meters (50m to 10,000m)",
    )
    trigger_action = models.CharField(
        max_length=30,
        choices=TRIGGER_ACTION_CHOICES,
        default="display_store_mode",
    )
    linked_promotion = models.ForeignKey(
        "ecommerce.CouponPromotion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="location_rules",
        help_text="Optional proximity discount unlocked upon arrival",
    )
    push_message = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Custom push alert sent to shopper on geofence trigger",
    )
    enable_bopis_checkin = models.BooleanField(
        default=True,
        help_text="Allow customer 1-tap arrival check-in for online orders",
    )
    enable_instore_mode = models.BooleanField(
        default=True,
        help_text="Expose local aisle map and barcode scanner in app",
    )
    dwell_time_seconds = models.PositiveIntegerField(
        default=120,
        help_text="Seconds shopper must remain in radius before dwell trigger",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Rule active for mobile telemetry evaluation",
    )

    class Meta:
        db_table = "ecommerce_mobile_location_rule"
        ordering = ["store_name", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_emlr_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "rule_type"], name="idx_emlr_ten_type"),
            models.Index(fields=["tenant", "is_active"], name="idx_emlr_ten_act"),
            models.Index(fields=["tenant", "fulfillment_center"], name="idx_emlr_ten_fc"),
        ]

    def __str__(self):
        return f"{self.name} - {self.store_name} ({self.number})"

    def distance_to(self, target_lat, target_lng):
        """Haversine formula calculating distance in meters between this location and target."""
        if target_lat is None or target_lng is None:
            return float("inf")
        try:
            lat1 = math.radians(float(self.latitude))
            lon1 = math.radians(float(self.longitude))
            lat2 = math.radians(float(target_lat))
            lon2 = math.radians(float(target_lng))
        except (ValueError, TypeError):
            return float("inf")

        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        earth_radius_m = 6371000
        return round(earth_radius_m * c, 1)

    def is_within_geofence(self, target_lat, target_lng):
        dist = self.distance_to(target_lat, target_lng)
        return dist <= self.radius_meters
