"""Sales 8.16 — FieldCheckIn model."""
from decimal import Decimal
import math

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

VERIFICATION_STATUS_CHOICES = [
    ("verified", "Verified On-Site"),
    ("out_of_range", "Out of Range (>150m)"),
    ("gps_unavailable", "GPS Unavailable"),
    ("manual_override", "Manual Override"),
]

VISIT_PURPOSE_CHOICES = [
    ("prospecting", "Prospecting / Cold Call"),
    ("presentation", "Product Demo / Presentation"),
    ("quote_review", "Quote Review & Negotiation"),
    ("order_collection", "Order Taking / Restock"),
    ("relationship", "Account Review / Check-In"),
    ("audit", "Merchandising / Stock Audit"),
    ("service_check", "Service / Support Follow-Up"),
]

VISIT_OUTCOME_CHOICES = [
    ("successful", "Successful Visit"),
    ("follow_up_needed", "Follow-Up Required"),
    ("quote_requested", "Quote Requested"),
    ("order_placed", "Order Placed"),
    ("decision_maker_unavailable", "Decision Maker Unavailable"),
    ("rescheduled", "Rescheduled"),
    ("cancelled", "Cancelled"),
]


class FieldCheckIn(TenantNumbered):
    NUMBER_PREFIX = "CHK"

    route = models.ForeignKey(
        "sales.FieldSalesRoute",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="check_ins",
    )
    stop_number = models.PositiveIntegerField(default=1)
    party = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="field_check_ins",
    )
    contact = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_check_ins",
    )
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="field_check_ins",
    )
    sales_rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="field_check_ins",
    )

    # GPS & Geofence
    check_in_at = models.DateTimeField(default=timezone.now)
    check_in_lat = models.DecimalField(max_digits=9, decimal_places=6)
    check_in_lng = models.DecimalField(max_digits=9, decimal_places=6)
    target_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    target_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geofence_radius_m = models.PositiveIntegerField(default=150)
    distance_from_target_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_geofence_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default="verified",
    )

    # Check-out & Duration
    check_out_at = models.DateTimeField(null=True, blank=True)
    check_out_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_force_checkout = models.BooleanField(default=False)

    # Visit Outcome
    visit_purpose = models.CharField(
        max_length=30,
        choices=VISIT_PURPOSE_CHOICES,
        default="presentation",
    )
    outcome = models.CharField(
        max_length=30,
        choices=VISIT_OUTCOME_CHOICES,
        default="successful",
    )
    notes = models.TextField(blank=True)
    next_step = models.CharField(max_length=255, blank=True)
    next_step_due = models.DateField(null=True, blank=True)

    # Spine integrations
    photo_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="check_in_photos",
    )
    resulting_quote = models.ForeignKey(
        "sales.CPQQuote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="originating_check_ins",
    )
    communication_log = models.ForeignKey(
        "crm.CommunicationLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="field_check_ins",
    )

    class Meta:
        ordering = ["-check_in_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_chk_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "party"], name="sales_chk_ten_party_idx"),
            models.Index(fields=["tenant", "sales_rep"], name="sales_chk_ten_rep_idx"),
            models.Index(fields=["tenant", "check_in_at"], name="sales_chk_ten_time_idx"),
            models.Index(fields=["tenant", "route"], name="sales_chk_ten_route_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.party.name} ({self.check_in_at.strftime('%Y-%m-%d %H:%M')})"

    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate the Haversine distance between two coordinates in metres."""
        if None in (lat1, lon1, lat2, lon2):
            return None
        r = 6371000.0  # Earth radius in metres
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        delta_phi = math.radians(float(lat2) - float(lat1))
        delta_lambda = math.radians(float(lon2) - float(lon1))

        a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return Decimal(str(round(r * c, 2)))

    def calculate_duration(self):
        if self.check_in_at and self.check_out_at:
            delta = self.check_out_at - self.check_in_at
            return max(0, int(delta.total_seconds() // 60))
        return None

    def clean(self):
        super().clean()
        if self.check_in_lat is not None and not (-90 <= float(self.check_in_lat) <= 90):
            raise ValidationError({"check_in_lat": "Latitude must be between -90 and 90 degrees."})
        if self.check_in_lng is not None and not (-180 <= float(self.check_in_lng) <= 180):
            raise ValidationError({"check_in_lng": "Longitude must be between -180 and 180 degrees."})

        if self.check_out_at and self.check_in_at and self.check_out_at < self.check_in_at:
            raise ValidationError({"check_out_at": "Check-out time cannot precede check-in time."})

        # Calculate distance if target is supplied
        if self.target_lat is not None and self.target_lng is not None:
            dist = self.calculate_distance(self.check_in_lat, self.check_in_lng, self.target_lat, self.target_lng)
            if dist is not None:
                self.distance_from_target_m = dist
                if dist <= Decimal(str(self.geofence_radius_m)):
                    self.is_geofence_verified = True
                    if self.verification_status != "manual_override":
                        self.verification_status = "verified"
                else:
                    self.is_geofence_verified = False
                    if self.verification_status not in ("manual_override", "gps_unavailable"):
                        self.verification_status = "out_of_range"

        if self.check_out_at and not self.duration_minutes:
            self.duration_minutes = self.calculate_duration()

        # Multi-tenant isolation verification
        if self.tenant_id:
            for fk_field, rel_name in [
                ("party", "Party"),
                ("contact", "Contact"),
                ("opportunity", "Opportunity"),
                ("sales_rep", "Sales Rep"),
                ("route", "Field Route"),
                ("photo_document", "Document"),
                ("resulting_quote", "CPQ Quote"),
                ("communication_log", "Communication Log"),
            ]:
                obj = getattr(self, fk_field, None)
                if obj and getattr(obj, "tenant_id", None) and obj.tenant_id != self.tenant_id:
                    raise ValidationError({fk_field: f"{rel_name} belongs to another workspace."})
