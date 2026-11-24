from django import forms
from django.core.exceptions import ValidationError

from apps.documents.models.AuditReporting.AuditReportDefinitions import AuditReportDefinition


class AuditReportDefinitionForm(forms.ModelForm):
    """Form for creating and editing compliance and custom audit report definitions."""

    class Meta:
        model = AuditReportDefinition
        fields = [
            "name",
            "description",
            "report_type",
            "date_range_preset",
            "custom_start_date",
            "custom_end_date",
            "output_format",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 SOC2 Confidential Access Audit"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe the scope and objective of this audit report..."}),
            "report_type": forms.Select(attrs={"class": "form-select"}),
            "date_range_preset": forms.Select(attrs={"class": "form-select"}),
            "custom_start_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "custom_end_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "output_format": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        preset = cleaned_data.get("date_range_preset")
        start = cleaned_data.get("custom_start_date")
        end = cleaned_data.get("custom_end_date")

        if preset == "custom":
            if not start:
                self.add_error("custom_start_date", "Start date is required when using a custom date range.")
            if not end:
                self.add_error("custom_end_date", "End date is required when using a custom date range.")
            if start and end and start > end:
                self.add_error("custom_end_date", "End date must be on or after start date.")

        return cleaned_data
