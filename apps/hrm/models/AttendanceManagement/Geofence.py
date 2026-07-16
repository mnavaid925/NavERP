"""HRM 3.9 Attendance Management — Geofence models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.9 Attendance Management — Geofencing (GeoFence) + Attendance Regularization
# ---------------------------------------------------------------------------
class GeoFence(TenantOwned):
    """A GPS geofence zone for field/site attendance (3.9). A punch's coordinates are checked
    against the zone centre + ``radius_m`` via the haversine ``distance_to`` — real proximity
    maths, not a stub. Small per-tenant catalog identified by name (not auto-numbered)."""

    EARTH_RADIUS_M = 6_371_000  # mean Earth radius, metres

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6,
                                   validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))])
    longitude = models.DecimalField(max_digits=9, decimal_places=6,
                                    validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))])
    radius_m = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1)],
                                           help_text="Allowed radius from the centre point, in metres.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_geo_tenant_active_idx"),
        ]

    def distance_to(self, lat, lng):
        """Great-circle distance in metres from this zone's centre to (lat, lng) via the
        haversine formula. Accepts Decimal or float; returns a float (metres)."""
        lat1, lng1 = math.radians(float(self.latitude)), math.radians(float(self.longitude))
        lat2, lng2 = math.radians(float(lat)), math.radians(float(lng))
        dlat, dlng = lat2 - lat1, lng2 - lng1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        return self.EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))

    def contains(self, lat, lng):
        """True when (lat, lng) is within ``radius_m`` of the zone centre."""
        if lat is None or lng is None:
            return False
        return self.distance_to(lat, lng) <= self.radius_m

    def __str__(self):
        return f"{self.name} (r={self.radius_m}m)"
