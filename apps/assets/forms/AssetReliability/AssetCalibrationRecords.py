from django import forms

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetReliability.AssetCalibrationRecords import AssetCalibrationRecord
from apps.core.models import Document, Party
from apps.scm.models import Asset as OperationalAsset


class AssetCalibrationRecordForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetCalibrationRecord
        fields = [
            "instrument_tag",
            "fixed_asset",
            "operational_asset",
            "calibrated_by",
            "service_vendor",
            "calibration_date",
            "calibration_frequency_days",
            "next_due_date",
            "reference_standard_used",
            "traceability_certificate_no",
            "setpoint_nominal",
            "allowable_tolerance",
            "tolerance_unit",
            "as_found_reading",
            "as_left_reading",
            "calibration_result",
            "certificate_number",
            "certificate_expiry",
            "certificate_document",
            "notes",
        ]
        widgets = {
            "instrument_tag": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PT-101 (Discharge Pressure Transmitter)"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "calibrated_by": forms.Select(attrs={"class": "form-select"}),
            "service_vendor": forms.Select(attrs={"class": "form-select"}),
            "calibration_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "calibration_frequency_days": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "next_due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "reference_standard_used": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Fluke 754 Calibrator S/N 948214"}),
            "traceability_certificate_no": forms.TextInput(attrs={"class": "form-input", "placeholder": "NIST-2026-98124"}),
            "setpoint_nominal": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001", "placeholder": "100.0000"}),
            "allowable_tolerance": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001", "placeholder": "0.5000"}),
            "tolerance_unit": forms.Select(attrs={"class": "form-select"}),
            "as_found_reading": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001", "placeholder": "Initial reading"}),
            "as_left_reading": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001", "placeholder": "Final reading"}),
            "calibration_result": forms.Select(attrs={"class": "form-select"}),
            "certificate_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "CAL-CERT-2026-081"}),
            "certificate_expiry": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "certificate_document": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Metrology room temperature: 21°C, humidity: 45%..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)
            self.fields["service_vendor"].queryset = Party.objects.filter(
                tenant=self.tenant,
                party_roles__role="vendor",
            ).distinct()
            self.fields["certificate_document"].queryset = Document.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["fixed_asset", "operational_asset", "service_vendor", "certificate_document"],
        )
        return cleaned_data
