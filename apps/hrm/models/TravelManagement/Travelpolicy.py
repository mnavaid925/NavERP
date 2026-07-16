"""HRM 3.35 Travel Management — Travelpolicy models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class TravelPolicy(TenantOwned):
    """3.35 travel-policy catalog: class-of-travel + daily/hotel/advance caps, optionally scoped to a
    job grade and a domestic/international/both trip scope. These limits DRIVE TravelBooking.out_of_policy
    (class + hotel-per-night) and cap TravelRequest advance approval (advance_percent_limit). A blank
    job_grade means 'applies to all grades'."""

    SCOPE_CHOICES = [
        ("domestic", "Domestic"),
        ("international", "International"),
        ("both", "Both"),
    ]
    TRAVEL_CLASS_CHOICES = [
        ("economy", "Economy"),
        ("premium_economy", "Premium Economy"),
        ("business", "Business"),
        ("first", "First"),
    ]

    name = models.CharField(max_length=100)
    job_grade = models.ForeignKey("hrm.JobGrade", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="travel_policies", help_text="Blank = applies to all grades.")
    trip_type = models.CharField(max_length=15, choices=SCOPE_CHOICES, default="both")
    travel_class = models.CharField(max_length=20, choices=TRAVEL_CLASS_CHOICES, default="economy")
    daily_allowance_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Per-diem cap. A static number this pass — not an auto-calc engine.")
    hotel_limit_per_night = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    advance_percent_limit = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Max advance as a percent of estimated cost, e.g. 80.00 = max 80%.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "is_active"], name="hrm_travelpol_tnt_active_idx")]

    def __str__(self):
        return f"{self.name} ({self.get_travel_class_display()})"
