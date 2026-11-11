from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetGeofenceEvent(TenantNumbered):
    """
    Mobile GPS geolocation tracking, virtual perimeter geofencing, radius monitoring,
    unauthorized movement alerts, and incident resolution [AGEO-].
    """

    NUMBER_PREFIX = "AGEO"

    EVENT_TYPE_CHOICES = [
        ("inside_perimeter", "Verified Inside Perimeter"),
        ("boundary_warning", "Proximity Boundary Warning"),
        ("perimeter_exit", "Unauthorized Perimeter Exit (Breach)"),
        ("perimeter_entry", "Perimeter Entry Detected"),
        ("unauthorized_movement", "Motion Outside Operating Hours"),
    ]

    SEVERITY_CHOICES = [
        ("info", "Informational"),
        ("low", "Low Risk"),
        ("medium", "Medium Warning"),
        ("high", "High Security Alert"),
        ("critical", "Critical Theft / Emergency"),
    ]

    STATUS_CHOICES = [
        ("open_alert", "Open Security Alert"),
        ("under_investigation", "Under Field Investigation"),
        ("resolved", "Resolved & Cleared"),
        ("false_alarm", "False Alarm / Sensor Glitch"),
    ]

    EVENT_TYPE_CSS = {
        "inside_perimeter": "badge-green",
        "boundary_warning": "badge-amber",
        "perimeter_exit": "badge-red",
        "perimeter_entry": "badge-info",
        "unauthorized_movement": "badge-red",
    }

    SEVERITY_CSS = {
        "info": "badge-slate",
        "low": "badge-info",
        "medium": "badge-amber",
        "high": "badge-red",
        "critical": "badge-red",
    }

    STATUS_CSS = {
        "open_alert": "badge-red",
        "under_investigation": "badge-amber",
        "resolved": "badge-green",
        "false_alarm": "badge-muted",
    }

    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        related_name="geofence_events",
        help_text="Subject mobile or plant asset tracked",
    )
    fence_name = models.CharField(max_length=150, help_text="Name of designated yard or facility boundary")
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Yard center latitude")
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Yard center longitude")
    radius_meters = models.PositiveIntegerField(default=100, help_text="Authorized perimeter radius in meters")
    recorded_latitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Actual asset latitude fix")
    recorded_longitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="Actual asset longitude fix")
    recorded_accuracy_m = models.FloatField(null=True, blank=True)
    distance_from_center_m = models.FloatField(default=0.0, help_text="Calculated distance from center in meters")
    event_type = models.CharField(max_length=28, choices=EVENT_TYPE_CHOICES, default="inside_perimeter")
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="info")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="open_alert")
    detected_at = models.DateTimeField(default=timezone.now)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_geofence_events",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, help_text="Security investigation or clearing notes")

    class Meta:
        ordering = ["-detected_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_ageo_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "asset"], name="idx_ageo_ten_asset"),
            models.Index(fields=["tenant", "status"], name="idx_ageo_ten_stat"),
            models.Index(fields=["tenant", "event_type"], name="idx_ageo_ten_type"),
            models.Index(fields=["tenant", "severity"], name="idx_ageo_ten_sev"),
            models.Index(fields=["tenant", "detected_at"], name="idx_ageo_ten_date"),
        ]

    def __str__(self):
        return f"{self.number} - {self.fence_name} ({self.get_event_type_display()})"

    @property
    def event_type_badge_class(self):
        return self.EVENT_TYPE_CSS.get(self.event_type, "badge-slate")

    @property
    def severity_badge_class(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
