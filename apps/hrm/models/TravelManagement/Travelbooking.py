"""HRM 3.35 Travel Management — Travelbooking models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.TravelManagement.Travelpolicy import TravelPolicy
from apps.hrm.models.TravelManagement._helpers import _TRAVEL_CLASS_RANK
from apps.hrm.models.TravelManagement.Travelpolicy import TravelPolicy
from apps.hrm.models.TravelManagement._helpers import _TRAVEL_CLASS_RANK


class TravelBooking(TenantOwned):
    """One recorded booking (flight/hotel/cab/rail/other) against a TravelRequest — record-keeping only
    (entered after the fact, no live GDS/OTA search this pass). out_of_policy/out_of_policy_reason are
    COMPUTED (never stored). Editable only while the parent trip is draft/pending (enforced in the views)."""

    BOOKING_TYPE_CHOICES = [
        ("flight", "Flight"),
        ("hotel", "Hotel"),
        ("cab", "Cab"),
        ("rail", "Rail"),
        ("other", "Other"),
    ]

    travel_request = models.ForeignKey("hrm.TravelRequest", on_delete=models.CASCADE, related_name="bookings")
    booking_type = models.CharField(max_length=10, choices=BOOKING_TYPE_CHOICES, default="flight")
    vendor = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, blank=True, help_text="PNR / confirmation number.")
    depart_date = models.DateField(null=True, blank=True)
    return_date = models.DateField(null=True, blank=True, help_text="Check-out / drop-off date.")
    travel_class = models.CharField(max_length=20, choices=TravelPolicy.TRAVEL_CLASS_CHOICES, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # WARNING: extension allowlist + size cap enforced in TravelBookingForm.clean_document (shared
    # _validate_upload). Keep MEDIA_ROOT outside the web root and serve with Content-Disposition:
    # attachment + X-Content-Type-Options: nosniff in production (mirrors ExpenseClaimLine.receipt).
    document = models.FileField(upload_to="hrm/travel_docs/%Y/%m/", null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["depart_date", "id"]
        indexes = [models.Index(fields=["tenant", "travel_request"], name="hrm_travelbk_tnt_req_idx")]

    def __str__(self):
        trip = self.travel_request.number if self.travel_request_id else "?"
        return f"{trip} - {self.get_booking_type_display()} - {self.vendor}"

    def _policy_check(self):
        """(violation, reason) — both branches None-guarded. Flight: booked class rank > policy class rank.
        Hotel: cost/nights > policy.hotel_limit_per_night (nights=1 fallback when dates missing/invalid)."""
        if not self.travel_request_id or not self.travel_request.policy_id:
            return False, ""
        policy = self.travel_request.policy
        reasons = []
        if self.booking_type == "flight" and self.travel_class and policy.travel_class:
            if _TRAVEL_CLASS_RANK.get(self.travel_class, 0) > _TRAVEL_CLASS_RANK.get(policy.travel_class, 0):
                reasons.append(f"Class {self.get_travel_class_display()} exceeds the policy limit of "
                               f"{policy.get_travel_class_display()}")
        if self.booking_type == "hotel" and self.cost is not None and policy.hotel_limit_per_night is not None:
            nights = 1
            if self.depart_date and self.return_date and self.return_date > self.depart_date:
                nights = (self.return_date - self.depart_date).days
            per_night = self.cost / nights
            if per_night > policy.hotel_limit_per_night:
                reasons.append(f"Hotel cost {per_night}/night exceeds the policy limit of "
                               f"{policy.hotel_limit_per_night}/night")
        return bool(reasons), "; ".join(reasons)

    @property
    def out_of_policy(self):
        return self._policy_check()[0]

    @property
    def out_of_policy_reason(self):
        return self._policy_check()[1]
