"""HRM 3.27 Communication Hub — TravelPolicys forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    JobGrade,
    TravelPolicy,
)


class TravelPolicyForm(TenantModelForm):
    class Meta:
        model = TravelPolicy
        fields = ["name", "job_grade", "trip_type", "travel_class", "daily_allowance_limit",
                  "hotel_limit_per_night", "advance_percent_limit", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "job_grade" in self.fields:
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True).order_by("level_order", "name"))

    def clean(self):
        cleaned = super().clean()
        for f in ("daily_allowance_limit", "hotel_limit_per_night"):
            v = cleaned.get(f)
            if v is not None and v < 0:
                self.add_error(f, "Must be zero or greater.")
        pct = cleaned.get("advance_percent_limit")
        if pct is not None and not (0 <= pct <= 100):
            self.add_error("advance_percent_limit", "Must be between 0 and 100.")
        return cleaned
