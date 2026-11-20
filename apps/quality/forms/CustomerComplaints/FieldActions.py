from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CustomerComplaints.FieldActions import FieldAction


class FieldActionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = FieldAction
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "initiation_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "distribution_start_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "distribution_end_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "agency_notification_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "termination_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "affected_lot_numbers": forms.Textarea(attrs={"rows": 3, "class": "form-textarea", "placeholder": "e.g. LOT-2026-A1, LOT-2026-A2"}),
            "reason_for_action": forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
            "hhe_summary": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "closure_summary": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            if "initiating_complaint" in self.fields:
                from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
                self.fields["initiating_complaint"].queryset = CustomerComplaint.objects.filter(tenant=self.tenant)
            if "coordinator" in self.fields:
                self.fields["coordinator"].queryset = get_user_model().objects.filter(tenant=self.tenant)
            if "fsn_document" in self.fields:
                from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
                self.fields["fsn_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["initiating_complaint", "coordinator", "fsn_document"])

        total_units = cleaned_data.get("total_units_distributed") or 0
        quarantined = cleaned_data.get("units_quarantined_field") or 0
        recovered = cleaned_data.get("units_recovered_destroyed") or 0
        if total_units > 0 and (quarantined + recovered) > total_units:
            self.add_error(
                "units_recovered_destroyed",
                "Total units quarantined and recovered cannot exceed total units distributed to commerce.",
            )

        return cleaned_data
