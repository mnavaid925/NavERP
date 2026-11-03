import json

from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataIntegration.DataSourceConnectors import DataSourceConnector
from apps.bi.models.DataIntegration.IngestionPipelines import IngestionPipeline
from apps.core.models.Integration import MappingTemplate, RateLimitPolicy


class IngestionPipelineForm(TenantUniqueMixin, forms.ModelForm):
    file_parsing_options_raw = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
        required=False,
        label="File Parsing Options (JSON)",
        help_text="Optional CSV/JSON parsing options, e.g. {\"delimiter\": \",\", \"has_header\": true, \"encoding\": \"utf-8\"}",
    )

    class Meta:
        model = IngestionPipeline
        fields = [
            "name",
            "connector",
            "ingestion_mode",
            "source_entity",
            "target_staging_table",
            "schedule_cadence",
            "cron_expression",
            "file_format",
            "webhook_secret",
            "rate_limit_policy",
            "mapping_template",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Daily Invoices Ingestion to Staging"}),
            "connector": forms.Select(attrs={"class": "form-select"}),
            "ingestion_mode": forms.Select(attrs={"class": "form-select"}),
            "source_entity": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. accounting_invoice or /api/v1/orders"}),
            "target_staging_table": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. stg_accounting_invoices"}),
            "schedule_cadence": forms.Select(attrs={"class": "form-select"}),
            "cron_expression": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 0 2 * * * (optional custom cron)"}),
            "file_format": forms.Select(attrs={"class": "form-select"}),
            "webhook_secret": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": "Optional shared secret token"}),
            "rate_limit_policy": forms.Select(attrs={"class": "form-select"}),
            "mapping_template": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["connector"].queryset = DataSourceConnector.objects.filter(tenant=self.tenant)
            self.fields["rate_limit_policy"].queryset = RateLimitPolicy.objects.filter(tenant=self.tenant)
            self.fields["mapping_template"].queryset = MappingTemplate.objects.filter(tenant=self.tenant)
        if self.instance and self.instance.pk and self.instance.file_parsing_options:
            self.fields["file_parsing_options_raw"].initial = json.dumps(self.instance.file_parsing_options, indent=2)

    def clean_file_parsing_options_raw(self):
        raw = self.cleaned_data.get("file_parsing_options_raw", "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("File parsing options must be a valid JSON object.")
            return parsed
        except json.JSONDecodeError as err:
            raise forms.ValidationError(f"Invalid JSON syntax: {err}")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["connector", "rate_limit_policy", "mapping_template"])
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "file_parsing_options_raw" in self.cleaned_data:
            instance.file_parsing_options = self.cleaned_data["file_parsing_options_raw"]
        if self.tenant and not instance.tenant_id:
            instance.tenant = self.tenant
        if commit:
            instance.save()
            self.save_m2m()
        return instance
