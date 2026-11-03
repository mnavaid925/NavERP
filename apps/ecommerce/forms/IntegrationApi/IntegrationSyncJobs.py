from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.IntegrationApi.EcommerceConnectors import EcommerceConnector
from apps.ecommerce.models.IntegrationApi.IntegrationSyncJobs import IntegrationSyncJob


class IntegrationSyncJobForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = IntegrationSyncJob
        exclude = [
            "tenant",
            "number",
            "status",
            "records_total",
            "records_processed",
            "records_succeeded",
            "records_failed",
            "started_at",
            "finished_at",
            "duration_seconds",
            "retry_count",
            "parent_job",
            "triggered_by",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "connector": forms.Select(attrs={"class": "form-select"}),
            "sync_entity": forms.Select(attrs={"class": "form-select"}),
            "direction": forms.Select(attrs={"class": "form-select"}),
            "trigger_type": forms.Select(attrs={"class": "form-select"}),
            "batch_id": forms.TextInput(
                attrs={
                    "class": "form-input font-mono",
                    "placeholder": "Optional execution UUID or batch ID",
                }
            ),
            "max_retries": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "3"}
            ),
            "payload_preview": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-xs",
                    "rows": 4,
                    "placeholder": "Sample JSON payload or filter parameters...",
                }
            ),
            "error_summary": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Error summary or diagnostic trace if reporting a failure...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["connector"].queryset = EcommerceConnector.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean_max_retries(self):
        val = self.cleaned_data.get("max_retries")
        if val is not None:
            if val < 0:
                raise forms.ValidationError("Maximum retries cannot be negative.")
            if val > 20:
                raise forms.ValidationError("Maximum retries cannot exceed 20 attempts.")
        return val

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["connector"])
        return cleaned_data
