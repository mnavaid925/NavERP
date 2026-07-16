"""HRM 3.27 Communication Hub — TravelRequests forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TravelPolicy,
    TravelRequest,
)


class TravelRequestForm(TenantModelForm):
    # status/approver/approved_at/decision_note/advance_approved/advance_paid_at/advance_reference/
    # settlement_claim are workflow-set; employee is resolved server-side by _ss_child_create.
    class Meta:
        model = TravelRequest
        fields = ["title", "trip_type", "origin", "destination", "purpose", "start_date", "end_date",
                  "policy", "estimated_cost", "currency", "advance_requested"]
        widgets = {"purpose": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "policy" in self.fields:
            self.fields["policy"].queryset = (
                TravelPolicy.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
        if self.tenant is not None and "currency" in self.fields:
            from apps.accounting.models import Currency
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before start date.")
        cost = cleaned.get("estimated_cost")
        if cost is not None and cost < 0:
            self.add_error("estimated_cost", "Must be zero or greater.")
        advance = cleaned.get("advance_requested")
        if advance is not None:
            if advance < 0:
                self.add_error("advance_requested", "Must be zero or greater.")
            elif cost is not None and advance > cost:
                self.add_error("advance_requested", "Cannot request an advance larger than the estimated cost.")
        policy, trip_type = cleaned.get("policy"), cleaned.get("trip_type")
        if policy and trip_type and policy.trip_type != "both" and policy.trip_type != trip_type:
            self.add_error("policy", f"This policy applies to {policy.get_trip_type_display()} trips, "
                                     f"not this {dict(TravelRequest.TRIP_TYPE_CHOICES).get(trip_type, trip_type)} one.")
        return cleaned
