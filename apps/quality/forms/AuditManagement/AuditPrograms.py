from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import reject_foreign
from apps.quality.models.AuditManagement.AuditPrograms import AuditProgram

User = get_user_model()


class AuditProgramForm(forms.ModelForm):
    class Meta:
        model = AuditProgram
        fields = [
            "title",
            "program_year",
            "program_type",
            "risk_basis",
            "scope_description",
            "start_date",
            "end_date",
            "allocated_budget_hours",
            "program_manager",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FY2026 Enterprise Quality & Regulatory Audit Program"}),
            "program_year": forms.NumberInput(attrs={"class": "form-input", "placeholder": "2026"}),
            "program_type": forms.Select(attrs={"class": "form-select"}),
            "risk_basis": forms.Select(attrs={"class": "form-select"}),
            "scope_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Audit universe coverage, functional areas, sites, and objectives..."}),
            "start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "allocated_budget_hours": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "program_manager": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Additional administrative or governance notes..."}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant or getattr(kwargs.get("instance"), "tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["program_manager"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "Program end date cannot be earlier than start date.")
        reject_foreign(self, cleaned_data, ["program_manager"])
        return cleaned_data
