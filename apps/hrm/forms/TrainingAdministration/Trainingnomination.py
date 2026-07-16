"""HRM 3.24 Training Administration — Trainingnomination forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TrainingNomination,
    TrainingSession,
)


# ----------------------------------------------------------------------- 3.24 Training Administration
class TrainingNominationForm(TenantModelForm):
    # status/approver/approved_at/rejected_reason/cancelled_reason are workflow-owned (set by the
    # approve/reject/waitlist/cancel/withdraw actions, never on this form); number auto.
    class Meta:
        model = TrainingNomination
        fields = ["session", "employee", "nominated_by", "nomination_type", "justification", "priority"]
        widgets = {"justification": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "session" in self.fields and self.tenant is not None:
            self.fields["session"].queryset = (
                TrainingSession.objects.filter(tenant=self.tenant)
                .exclude(status__in=("cancelled", "postponed")).order_by("-start_datetime"))

    def clean(self):
        # (tenant, session, employee) unique_together — tenant is form-excluded so validate_unique()
        # skips it; check explicitly (the 3.22/3.23 gotcha).
        cleaned = super().clean()
        session, employee = cleaned.get("session"), cleaned.get("employee")
        if self.tenant is not None and session and employee:
            dupes = TrainingNomination.objects.filter(tenant=self.tenant, session=session, employee=employee)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError({"employee": "This employee is already nominated for this session."})
        return cleaned
