"""HRM 3.27 Communication Hub — WellbeingPrograms forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    WellbeingProgram,
)


class WellbeingProgramForm(TenantModelForm):
    class Meta:
        model = WellbeingProgram
        fields = ["title", "description", "program_type", "owner", "target_department", "start_date",
                  "end_date", "points_value", "external_resource_url", "is_confidential", "status"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "program_type": "EAP / Counseling is always treated as confidential, regardless of the box below.",
            "is_confidential": "Hides the per-employee roster (aggregate stats only). Forced on for EAP.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "owner" in self.fields:
                self.fields["owner"].queryset = (
                    get_user_model().objects.filter(tenant=self.tenant, is_active=True).order_by("username"))
            if "target_department" in self.fields:
                self.fields["target_department"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        # Mirror the model's save() force here too, so cleaned_data (and therefore the audit-log diff,
        # which reads it) records the TRUE persisted value — an admin unchecking "confidential" on an EAP
        # program must not leave a misleading "is_confidential -> False" trail.
        if cleaned.get("program_type") == "eap_counseling":
            cleaned["is_confidential"] = True
        return cleaned
