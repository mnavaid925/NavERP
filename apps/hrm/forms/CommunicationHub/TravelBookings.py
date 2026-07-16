"""HRM 3.27 Communication Hub — TravelBookings forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TravelBooking,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload


class TravelBookingForm(TenantModelForm):
    # travel_request/tenant are set by the view; multipart for the document.
    class Meta:
        model = TravelBooking
        fields = ["booking_type", "vendor", "reference", "depart_date", "return_date", "travel_class",
                  "cost", "document", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        depart, ret = cleaned.get("depart_date"), cleaned.get("return_date")
        if depart and ret and ret < depart:
            self.add_error("return_date", "Return/check-out date cannot be before the depart/check-in date.")
        cost = cleaned.get("cost")
        if cost is not None and cost < 0:
            self.add_error("cost", "Must be zero or greater.")
        return cleaned

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Booking Document")
