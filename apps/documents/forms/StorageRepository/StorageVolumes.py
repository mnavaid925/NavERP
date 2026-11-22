import re
from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume


class StorageVolumeForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = StorageVolume
        fields = [
            "name",
            "code",
            "backend_type",
            "tier",
            "base_path",
            "region",
            "endpoint_url",
            "max_capacity_bytes",
            "warning_threshold_pct",
            "is_default",
            "is_active",
            "compression_type",
            "deduplication_enabled",
            "encryption_type",
            "rollover_volume",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Primary NVMe Hot Store"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. VOL-HOT-01"}),
            "backend_type": forms.Select(attrs={"class": "form-select"}),
            "tier": forms.Select(attrs={"class": "form-select"}),
            "base_path": forms.TextInput(attrs={"class": "form-input", "placeholder": "/var/data/dms or s3-bucket-name"}),
            "region": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. us-east-1, eu-central-1"}),
            "endpoint_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. https://s3.us-east-1.amazonaws.com"}),
            "max_capacity_bytes": forms.NumberInput(attrs={"class": "form-input", "min": "1048576"}),
            "warning_threshold_pct": forms.NumberInput(attrs={"class": "form-input", "min": "50", "max": "99"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "compression_type": forms.Select(attrs={"class": "form-select"}),
            "deduplication_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "encryption_type": forms.Select(attrs={"class": "form-select"}),
            "rollover_volume": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            volumes_qs = StorageVolume.objects.filter(tenant=self.tenant)
            if self.instance and self.instance.pk:
                volumes_qs = volumes_qs.exclude(pk=self.instance.pk)
            self.fields["rollover_volume"].queryset = volumes_qs.order_by("name")
        self.fields["region"].required = False
        self.fields["endpoint_url"].required = False
        self.fields["rollover_volume"].required = False
        self.fields["description"].required = False

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        if not re.match(r"^[A-Z0-9_\-]+$", code):
            raise forms.ValidationError("Volume code must contain only uppercase letters, numbers, hyphens, and underscores.")
        return code

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["rollover_volume"])
        rollover = cleaned.get("rollover_volume")
        if rollover and self.instance and self.instance.pk:
            if rollover.pk == self.instance.pk:
                self.add_error("rollover_volume", "A volume cannot be its own rollover target.")
        return cleaned
