from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.NonConformance.QuarantineContainments import QuarantineContainment

User = get_user_model()


class QuarantineContainmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = QuarantineContainment
        fields = [
            "ncr",
            "title",
            "hold_type",
            "quarantine_location",
            "red_tag_number",
            "quantity_on_hold",
            "unit_of_measure",
            "hold_date",
            "hold_applied_by",
            "status",
            "release_criteria",
            "released_quantity",
            "release_date",
            "released_by",
            "disposition_notes",
        ]
        widgets = {
            "ncr": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Physical Quarantine Hold on Capacitor Batch X14"}),
            "hold_type": forms.Select(attrs={"class": "form-select"}),
            "quarantine_location": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Warehouse Quarantine Cage B, Bin Q-04"}),
            "red_tag_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. RED-2026-089"}),
            "quantity_on_hold": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input", "placeholder": "EA, KG, M"}),
            "hold_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "hold_applied_by": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "release_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Criteria required before lifting quarantine hold..."}),
            "released_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "release_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "released_by": forms.Select(attrs={"class": "form-select"}),
            "disposition_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Quarantine reconciliation notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["ncr"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant).order_by("-created_at")
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["hold_applied_by"].queryset = user_qs
            self.fields["released_by"].queryset = user_qs
        else:
            self.fields["ncr"].queryset = NonConformanceReport.objects.none()
            self.fields["hold_applied_by"].queryset = User.objects.none()
            self.fields["released_by"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["ncr", "hold_applied_by", "released_by"])
        return cleaned
