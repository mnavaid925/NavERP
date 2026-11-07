import json

from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin
from apps.bi.models.EmbeddedMobileBi.KioskWallboardDisplays import KioskWallboardDisplay
from apps.core.forms import TenantModelForm


class KioskWallboardDisplayForm(TenantUniqueMixin, TenantModelForm):
    playlist_items_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "class": "form-textarea font-mono text-xs"}),
        label="Playlist Sequence (JSON)",
        help_text='JSON array of slides, e.g. [{"type": "dashboard", "title": "Sales Performance", "duration_seconds": 30}]',
    )
    operating_hours_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        label="Operating Hours Schedule (JSON)",
        help_text='JSON schedule dictionary, e.g. {"start": "08:00", "end": "18:00", "days": [1, 2, 3, 4, 5]}',
    )

    class Meta:
        model = KioskWallboardDisplay
        fields = [
            "name",
            "location_description",
            "kiosk_slug",
            "access_passcode",
            "is_public_kiosk",
            "status",
            "default_slide_duration_seconds",
            "transition_effect",
            "theme",
            "display_schedule",
            "auto_refresh_data_interval_seconds",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "location_description": forms.TextInput(attrs={"class": "form-input"}),
            "kiosk_slug": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "access_passcode": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "is_public_kiosk": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "default_slide_duration_seconds": forms.NumberInput(attrs={"class": "form-input", "min": 5}),
            "transition_effect": forms.Select(attrs={"class": "form-select"}),
            "theme": forms.Select(attrs={"class": "form-select"}),
            "display_schedule": forms.Select(attrs={"class": "form-select"}),
            "auto_refresh_data_interval_seconds": forms.NumberInput(attrs={"class": "form-input", "min": 10}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.playlist_items:
                self.fields["playlist_items_raw"].initial = json.dumps(
                    self.instance.playlist_items, indent=2
                )
            else:
                self.fields["playlist_items_raw"].initial = "[]"

            if self.instance.operating_hours_json:
                self.fields["operating_hours_raw"].initial = json.dumps(
                    self.instance.operating_hours_json, indent=2
                )
            else:
                self.fields["operating_hours_raw"].initial = "{}"
        else:
            self.fields["playlist_items_raw"].initial = "[]"
            self.fields["operating_hours_raw"].initial = "{}"

    def clean(self):
        cleaned_data = super().clean()

        raw_playlist = cleaned_data.get("playlist_items_raw", "").strip()
        if raw_playlist:
            try:
                parsed_playlist = json.loads(raw_playlist)
                if not isinstance(parsed_playlist, list):
                    self.add_error("playlist_items_raw", "Playlist items must be a JSON array of slide objects.")
                else:
                    self.instance.playlist_items = parsed_playlist
            except json.JSONDecodeError as exc:
                self.add_error("playlist_items_raw", f"Invalid JSON syntax in playlist: {exc}")
        else:
            self.instance.playlist_items = []

        raw_hours = cleaned_data.get("operating_hours_raw", "").strip()
        if raw_hours:
            try:
                parsed_hours = json.loads(raw_hours)
                if not isinstance(parsed_hours, dict):
                    self.add_error("operating_hours_raw", "Operating hours must be a JSON object.")
                else:
                    self.instance.operating_hours_json = parsed_hours
            except json.JSONDecodeError as exc:
                self.add_error("operating_hours_raw", f"Invalid JSON syntax in operating hours: {exc}")
        else:
            self.instance.operating_hours_json = {}

        return cleaned_data
