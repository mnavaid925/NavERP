from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.MobileAssetManagement.AssetScanLogs import AssetScanLog
from apps.scm.models import Asset

User = get_user_model()


class AssetScanLogForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetScanLog
        fields = [
            "scanned_by",
            "scan_context",
            "scan_method",
            "raw_payload",
            "asset",
            "match_status",
            "gps_latitude",
            "gps_longitude",
            "gps_accuracy_m",
            "device_info",
            "notes",
            "client_sync_id",
            "is_offline_captured",
        ]
        widgets = {
            "scanned_by": forms.Select(attrs={"class": "form-select"}),
            "scan_context": forms.Select(attrs={"class": "form-select"}),
            "scan_method": forms.Select(attrs={"class": "form-select"}),
            "raw_payload": forms.TextInput(attrs={"class": "form-input", "placeholder": "Scanned Barcode / QR / RFID EPC"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "match_status": forms.Select(attrs={"class": "form-select"}),
            "gps_latitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Latitude"}),
            "gps_longitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Longitude"}),
            "gps_accuracy_m": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "placeholder": "Accuracy in meters"}),
            "device_info": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Zebra TC57 / iOS Chrome Mobile"}),
            "notes": forms.TextInput(attrs={"class": "form-input", "placeholder": "Optional scan notes..."}),
            "client_sync_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "Client UUID"}),
            "is_offline_captured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["scanned_by"].queryset = User.objects.filter(tenant=self.tenant)
        self.fields["asset"].required = False
        self.fields["gps_latitude"].required = False
        self.fields["gps_longitude"].required = False
        self.fields["gps_accuracy_m"].required = False
        self.fields["device_info"].required = False
        self.fields["notes"].required = False
        self.fields["client_sync_id"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["asset"])
        return cleaned_data
