from django import forms

from apps.bi.forms._common import TenantUniqueMixin
from apps.bi.models.DataWarehouse.LakehouseZones import LakehouseZone
from apps.core.forms import TenantModelForm


class LakehouseZoneForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = LakehouseZone
        fields = [
            "name",
            "code",
            "zone_type",
            "storage_backend",
            "default_format",
            "base_uri_path",
            "is_read_only",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Bronze Raw Ingestion Zone"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. bronze"}),
            "zone_type": forms.Select(attrs={"class": "form-select"}),
            "storage_backend": forms.Select(attrs={"class": "form-select"}),
            "default_format": forms.Select(attrs={"class": "form-select"}),
            "base_uri_path": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. s3://analytics-lake/bronze/ or internal"}),
            "is_read_only": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Zone ingestion SLA, governance rules, and retention..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().lower()
        if code:
            existing = LakehouseZone.objects.filter(tenant=self.tenant, code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("A lakehouse zone with this slug code already exists in your workspace.")
        return code
