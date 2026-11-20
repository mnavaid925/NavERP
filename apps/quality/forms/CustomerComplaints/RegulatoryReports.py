from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CustomerComplaints.RegulatoryReports import RegulatoryReport


class RegulatoryReportForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RegulatoryReport
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "submission_status",
            "submission_date",
            "agency_acknowledgement_date",
        ]
        widgets = {
            "statutory_due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "event_summary": forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
            "patient_remedial_action": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            if "complaint" in self.fields:
                from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
                self.fields["complaint"].queryset = CustomerComplaint.objects.filter(tenant=self.tenant)
            user_qs = get_user_model().objects.filter(tenant=self.tenant)
            if "prepared_by" in self.fields:
                self.fields["prepared_by"].queryset = user_qs
            if "reviewed_by" in self.fields:
                self.fields["reviewed_by"].queryset = user_qs

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["complaint", "prepared_by", "reviewed_by"])

        statutory_due_date = cleaned_data.get("statutory_due_date")
        if not statutory_due_date:
            self.add_error("statutory_due_date", "A statutory regulatory submission due date is mandated by law.")

        return cleaned_data
