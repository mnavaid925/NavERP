from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CalibrationAnalysis.CalibrationRecords import CalibrationRecord

User = get_user_model()


class CalibrationRecordForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CalibrationRecord
        exclude = ("tenant", "number", "approved_at", "created_at", "updated_at")
        widgets = {
            "gage": forms.Select(attrs={"class": "form-select"}),
            "calibration_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "calibration_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "service_vendor": forms.Select(attrs={"class": "form-select"}),
            "certificate_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CERT-2026-8812"}),
            "as_found_condition": forms.Select(attrs={"class": "form-select"}),
            "as_left_condition": forms.Select(attrs={"class": "form-select"}),
            "overall_result": forms.Select(attrs={"class": "form-select"}),
            "ambient_temperature_c": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "ambient_relative_humidity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "expanded_uncertainty": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "test_uncertainty_ratio": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "max_observed_error": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "guardband_applied": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "standards_used": forms.SelectMultiple(attrs={"class": "form-select", "size": 4}),
            "standard_traceability_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "technician_name": forms.TextInput(attrs={"class": "form-input"}),
            "calibrated_by_user": forms.Select(attrs={"class": "form-select"}),
            "approved_by": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["gage"].queryset = CalibrationGage.objects.filter(tenant=self.tenant)
            self.fields["service_vendor"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["standards_used"].queryset = CalibrationGage.objects.filter(
                tenant=self.tenant, is_reference_standard=True
            )
            self.fields["calibrated_by_user"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["approved_by"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self, cleaned,
            ["gage", "service_vendor", "standards_used", "calibrated_by_user", "approved_by"]
        )
        cal_date = cleaned.get("calibration_date")
        if cal_date and cal_date > timezone.now().date():
            self.add_error("calibration_date", "Calibration date cannot be in the future.")
        return cleaned
