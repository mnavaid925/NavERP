import json

from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataIntegration.IngestionPipelines import IngestionPipeline
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.core.models.Monitoring import AlertRule


class EtlPipelineForm(TenantUniqueMixin, forms.ModelForm):
    upstream_dependencies_raw = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
        required=False,
        label="Upstream Dependencies (JSON Array)",
        help_text='JSON list of upstream BETL pipeline numbers or IDs, e.g. ["BETL-00001", "BETL-00002"]',
    )
    retry_policy_raw = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
        required=False,
        label="Retry Policy (JSON)",
        help_text='JSON config for retries, e.g. {"max_retries": 3, "retry_delay_seconds": 60, "backoff_factor": 2}',
    )

    class Meta:
        model = EtlPipeline
        fields = [
            "name",
            "description",
            "source_ingestion_pipeline",
            "source_staging_table",
            "target_table",
            "target_layer",
            "trigger_type",
            "cron_expression",
            "sla_timeout_seconds",
            "alert_on_sla_miss",
            "alert_rule",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Sales Mart Aggregation Pipeline"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe the pipeline transformation purpose"}),
            "source_ingestion_pipeline": forms.Select(attrs={"class": "form-select"}),
            "source_staging_table": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. stg_accounting_invoices"}),
            "target_table": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. fct_monthly_sales"}),
            "target_layer": forms.Select(attrs={"class": "form-select"}),
            "trigger_type": forms.Select(attrs={"class": "form-select"}),
            "cron_expression": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 0 2 * * *"}),
            "sla_timeout_seconds": forms.NumberInput(attrs={"class": "form-input", "min": 60}),
            "alert_on_sla_miss": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "alert_rule": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["source_ingestion_pipeline"].queryset = IngestionPipeline.objects.filter(tenant=self.tenant)
            self.fields["alert_rule"].queryset = AlertRule.objects.filter(tenant=self.tenant)
        if self.instance and self.instance.pk:
            if self.instance.upstream_dependencies:
                self.fields["upstream_dependencies_raw"].initial = json.dumps(self.instance.upstream_dependencies, indent=2)
            if self.instance.retry_policy:
                self.fields["retry_policy_raw"].initial = json.dumps(self.instance.retry_policy, indent=2)

    def clean_upstream_dependencies_raw(self):
        raw = self.cleaned_data.get("upstream_dependencies_raw", "").strip()
        if not raw:
            return []
        try:
            val = json.loads(raw)
            if not isinstance(val, list):
                raise forms.ValidationError("Must be a valid JSON array of pipeline identifiers.")
            return val
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_retry_policy_raw(self):
        raw = self.cleaned_data.get("retry_policy_raw", "").strip()
        if not raw:
            return {}
        try:
            val = json.loads(raw)
            if not isinstance(val, dict):
                raise forms.ValidationError("Must be a valid JSON object.")
            return val
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["source_ingestion_pipeline", "alert_rule"])
        trigger_type = cleaned.get("trigger_type")
        cron_expr = cleaned.get("cron_expression", "").strip() if cleaned.get("cron_expression") else ""
        if trigger_type == "scheduled_cron" and not cron_expr:
            self.add_error("cron_expression", "Cron expression is required when trigger type is scheduled cron.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "upstream_dependencies_raw" in self.cleaned_data:
            instance.upstream_dependencies = self.cleaned_data["upstream_dependencies_raw"]
        if "retry_policy_raw" in self.cleaned_data:
            instance.retry_policy = self.cleaned_data["retry_policy_raw"]
        if commit:
            instance.save()
        return instance
