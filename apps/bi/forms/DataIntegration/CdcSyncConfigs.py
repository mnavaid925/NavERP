from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataIntegration.CdcSyncConfigs import CdcSyncConfig
from apps.bi.models.DataIntegration.IngestionPipelines import IngestionPipeline


class CdcSyncConfigForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = CdcSyncConfig
        fields = [
            "pipeline",
            "capture_method",
            "sync_mode",
            "primary_key_fields",
            "cursor_field",
            "schema_drift_policy",
            "capture_deletes",
            "soft_delete_field",
        ]
        widgets = {
            "pipeline": forms.Select(attrs={"class": "form-select"}),
            "capture_method": forms.Select(attrs={"class": "form-select"}),
            "sync_mode": forms.Select(attrs={"class": "form-select"}),
            "primary_key_fields": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": "e.g. id or order_id,tenant_id"}),
            "cursor_field": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": "e.g. updated_at or lsn"}),
            "schema_drift_policy": forms.Select(attrs={"class": "form-select"}),
            "capture_deletes": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "soft_delete_field": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": "e.g. is_deleted"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            qs = IngestionPipeline.objects.filter(tenant=self.tenant)
            # If creating a new CDC config, exclude pipelines that already have one
            if not self.instance or not self.instance.pk:
                qs = qs.filter(cdc_config__isnull=True)
            self.fields["pipeline"].queryset = qs

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["pipeline"])
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.tenant and not instance.tenant_id:
            instance.tenant = self.tenant
        if commit:
            instance.save()
            self.save_m2m()
        return instance
