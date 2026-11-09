from django import forms

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetReliability.AssetTelemetryReadings import AssetTelemetryReading
from apps.scm.models import Asset as OperationalAsset


class AssetTelemetryReadingForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetTelemetryReading
        fields = [
            "sensor_identifier",
            "fixed_asset",
            "operational_asset",
            "recorded_by",
            "recorded_at",
            "source",
            "metric_type",
            "metric_unit",
            "reading_value",
            "baseline_value",
            "is_anomaly",
            "anomaly_confidence",
            "alert_notes",
        ]
        widgets = {
            "sensor_identifier": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. VIB-PUMP-01-AXIAL"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "recorded_by": forms.Select(attrs={"class": "form-select"}),
            "recorded_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-input"}),
            "source": forms.Select(attrs={"class": "form-select"}),
            "metric_type": forms.Select(attrs={"class": "form-select"}),
            "metric_unit": forms.Select(attrs={"class": "form-select"}),
            "reading_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001", "placeholder": "Measured value"}),
            "baseline_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001", "placeholder": "Expected baseline"}),
            "is_anomaly": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "anomaly_confidence": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100, "step": "0.01", "placeholder": "0-100%"}),
            "alert_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Telemetry analysis notes, high harmonics observed, acoustic spike details..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["fixed_asset", "operational_asset"])
        return cleaned_data
