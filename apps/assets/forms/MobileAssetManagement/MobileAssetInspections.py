from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.MobileAssetManagement.MobileAssetInspections import MobileAssetInspection
from apps.scm.models import Asset

User = get_user_model()


class MobileAssetInspectionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MobileAssetInspection
        fields = [
            "title",
            "inspection_type",
            "asset",
            "fixed_asset",
            "inspector",
            "inspection_date",
            "scheduled_date",
            "overall_result",
            "condition_rating",
            "meter_reading",
            "checklist_summary",
            "photo_url",
            "photo_caption",
            "voice_notes_transcription",
            "corrective_action_required",
            "findings_summary",
            "gps_latitude",
            "gps_longitude",
            "location_accuracy_m",
            "client_sync_id",
            "is_offline_captured",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Daily Forklift Pre-Shift Walkaround"}),
            "inspection_type": forms.Select(attrs={"class": "form-select"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "inspector": forms.Select(attrs={"class": "form-select"}),
            "inspection_date": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "scheduled_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "overall_result": forms.Select(attrs={"class": "form-select"}),
            "condition_rating": forms.Select(attrs={"class": "form-select"}),
            "meter_reading": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Hours / km"}),
            "checklist_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Itemized checklist findings (e.g. Fluids OK, Tires 80%, Brakes Pass)..."}),
            "photo_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://cdn.example.com/inspections/photo1.jpg"}),
            "photo_caption": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Minor oil seepage on hydraulic cylinder seal"}),
            "voice_notes_transcription": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Technician speech-to-text dictation notes..."}),
            "corrective_action_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "findings_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Executive summary of defects, leaks, wear, or abnormal vibrations..."}),
            "gps_latitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Latitude (e.g. 37.774929)"}),
            "gps_longitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Longitude (e.g. -122.419416)"}),
            "location_accuracy_m": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "placeholder": "Accuracy in meters"}),
            "client_sync_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "Client UUID"}),
            "is_offline_captured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["inspector"].queryset = User.objects.filter(tenant=self.tenant)
        self.fields["fixed_asset"].required = False
        self.fields["scheduled_date"].required = False
        self.fields["meter_reading"].required = False
        self.fields["checklist_summary"].required = False
        self.fields["photo_url"].required = False
        self.fields["photo_caption"].required = False
        self.fields["voice_notes_transcription"].required = False
        self.fields["findings_summary"].required = False
        self.fields["gps_latitude"].required = False
        self.fields["gps_longitude"].required = False
        self.fields["location_accuracy_m"].required = False
        self.fields["client_sync_id"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["asset", "fixed_asset", "inspector"])
        return cleaned_data
