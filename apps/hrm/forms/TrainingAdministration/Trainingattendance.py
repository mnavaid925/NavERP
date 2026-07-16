"""HRM 3.24 Training Administration — Trainingattendance forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TrainingAttendance,
    TrainingNomination,
)


class TrainingAttendanceForm(TenantModelForm):
    class Meta:
        model = TrainingAttendance
        fields = ["session", "employee", "nomination", "attendance_status", "completion_status",
                  "check_in_at", "check_out_at", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "nomination" in self.fields and self.tenant is not None:
            self.fields["nomination"].queryset = (
                TrainingNomination.objects.filter(tenant=self.tenant, status__in=("approved", "waitlisted"))
                .select_related("employee__party", "session").order_by("-created_at"))

    def clean(self):
        # (tenant, session, employee) unique_together — same form-excluded-tenant gotcha.
        cleaned = super().clean()
        session, employee = cleaned.get("session"), cleaned.get("employee")
        if self.tenant is not None and session and employee:
            dupes = TrainingAttendance.objects.filter(tenant=self.tenant, session=session, employee=employee)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError({"employee": "This employee already has an attendance record for this session."})
        return cleaned
