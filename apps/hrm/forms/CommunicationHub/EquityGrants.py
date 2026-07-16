"""HRM 3.27 Communication Hub — EquityGrants forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    EquityGrant,
)
from apps.hrm.forms.CommunicationHub._helpers import _scope_currency


class EquityGrantForm(TenantModelForm):
    # Admin-issued to a chosen employee; exercised_shares/last_exercised_at set by the record-exercise action.
    class Meta:
        model = EquityGrant
        fields = ["employee", "grant_type", "grant_date", "shares_granted", "exercise_price",
                  "fair_market_value_at_grant", "currency", "vesting_start_date", "cliff_months",
                  "vesting_duration_months", "vesting_frequency", "status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _scope_currency(self)
        if self.tenant is not None and "employee" in self.fields:
            self.fields["employee"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party").order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        shares = cleaned.get("shares_granted")
        if shares is not None and shares <= 0:
            self.add_error("shares_granted", "Must be greater than zero.")
        # Can't shrink a grant below shares already exercised (would corrupt exercisable/unvested math).
        if self.instance.pk and shares is not None and shares < self.instance.exercised_shares:
            self.add_error("shares_granted",
                           f"Cannot be less than the {self.instance.exercised_shares} share(s) already exercised.")
        cliff, dur = cleaned.get("cliff_months"), cleaned.get("vesting_duration_months")
        if cliff is not None and dur is not None and cliff > dur:
            self.add_error("cliff_months", "The cliff cannot be longer than the total vesting duration.")
        for f in ("exercise_price", "fair_market_value_at_grant"):
            v = cleaned.get(f)
            if v is not None and v < 0:
                self.add_error(f, "Must be zero or greater.")
        return cleaned
