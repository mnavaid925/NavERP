"""HRM 3.11 Time Tracking — FloatingHolidayElections forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    FloatingHolidayElection,
    HolidayPolicy,
    PublicHoliday,
)


class FloatingHolidayElectionForm(TenantModelForm):
    # SECURITY: `status`, `approved_by`, `approved_at` are deliberately NOT form fields — a new
    # election starts "pending" and all three are set only by the privileged approve/reject workflow
    # actions (mirrors LeaveRequestForm). Exposing them would let a user self-approve via a crafted POST.
    class Meta:
        model = FloatingHolidayElection
        fields = ["employee", "holiday", "policy", "note"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only optional (floating) holidays are electable; policy auto-resolves in the model's save()
        # if left blank, so it's optional on the form.
        if self.tenant is not None and "holiday" in self.fields:
            self.fields["holiday"].queryset = (
                PublicHoliday.objects.filter(tenant=self.tenant, is_optional=True).order_by("date"))
        if self.tenant is not None and "policy" in self.fields:
            self.fields["policy"].queryset = (
                HolidayPolicy.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
        if "policy" in self.fields:
            self.fields["policy"].required = False
