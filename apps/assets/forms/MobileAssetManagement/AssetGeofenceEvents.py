from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.MobileAssetManagement.AssetGeofenceEvents import AssetGeofenceEvent
from apps.scm.models import Asset

User = get_user_model()


class AssetGeofenceEventForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetGeofenceEvent
        fields = [
            "asset",
            "fence_name",
            "center_latitude",
            "center_longitude",
            "radius_meters",
            "recorded_latitude",
            "recorded_longitude",
            "recorded_accuracy_m",
            "distance_from_center_m",
            "event_type",
            "severity",
            "status",
            "acknowledged_by",
            "resolution_notes",
        ]
        widgets = {
            "asset": forms.Select(attrs={"class": "form-select"}),
            "fence_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Main Plant Yard Perimeter"}),
            "center_latitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Center Lat"}),
            "center_longitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Center Long"}),
            "radius_meters": forms.NumberInput(attrs={"class": "form-input", "min": "1", "placeholder": "Radius (m)"}),
            "recorded_latitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Recorded Lat"}),
            "recorded_longitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Recorded Long"}),
            "recorded_accuracy_m": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "placeholder": "Accuracy (m)"}),
            "distance_from_center_m": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "placeholder": "Distance (m)"}),
            "event_type": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "acknowledged_by": forms.Select(attrs={"class": "form-select"}),
            "resolution_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Security notes, clearance verification..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["acknowledged_by"].queryset = User.objects.filter(tenant=self.tenant)
        self.fields["recorded_accuracy_m"].required = False
        self.fields["acknowledged_by"].required = False
        self.fields["resolution_notes"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["asset", "acknowledged_by"])
        return cleaned_data
