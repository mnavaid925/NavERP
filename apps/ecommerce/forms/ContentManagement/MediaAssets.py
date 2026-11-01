from django import forms
from django.core.exceptions import ValidationError

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin
from apps.ecommerce.models.ContentManagement.MediaAssets import MediaAsset


class MediaAssetForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MediaAsset
        fields = [
            "title",
            "file_url",
            "alt_text",
            "caption",
            "media_type",
            "folder_category",
            "file_size_bytes",
            "mime_type",
            "width_px",
            "height_px",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Asset display name or headline"}
            ),
            "file_url": forms.URLInput(
                attrs={"class": "form-input font-mono", "placeholder": "https://cdn.example.com/assets/banner.jpg"}
            ),
            "alt_text": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Descriptive alt text for screen readers"}
            ),
            "caption": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Optional visible caption"}
            ),
            "media_type": forms.Select(attrs={"class": "form-select"}),
            "folder_category": forms.Select(attrs={"class": "form-select"}),
            "file_size_bytes": forms.NumberInput(
                attrs={"class": "form-input", "min": 0}
            ),
            "mime_type": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "image/jpeg, image/png, video/mp4, etc."}
            ),
            "width_px": forms.NumberInput(
                attrs={"class": "form-input", "min": 0, "placeholder": "Width in px (optional)"}
            ),
            "height_px": forms.NumberInput(
                attrs={"class": "form-input", "min": 0, "placeholder": "Height in px (optional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["alt_text"].required = False
        self.fields["caption"].required = False
        self.fields["width_px"].required = False
        self.fields["height_px"].required = False
        self.fields["file_size_bytes"].required = False

    def clean_file_url(self):
        url = self.cleaned_data.get("file_url", "").strip()
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise ValidationError("Asset URL must begin with http:// or https://")
        return url
