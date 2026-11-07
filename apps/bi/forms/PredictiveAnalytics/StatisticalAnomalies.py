import json
from django import forms

from apps.bi.forms._common import reject_foreign
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.PredictiveAnalytics.PredictiveModels import PredictiveModel
from apps.bi.models.PredictiveAnalytics.StatisticalAnomalies import StatisticalAnomaly
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class StatisticalAnomalyForm(TenantModelForm):
    root_cause_factors_raw = forms.CharField(
        label="Root-Cause Factors (JSON)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Contributing segment drivers and dimensional explanations",
    )

    class Meta:
        model = StatisticalAnomaly
        fields = [
            "title",
            "model",
            "semantic_model",
            "kpi_definition",
            "metric_name",
            "anomaly_type",
            "detection_method",
            "severity",
            "observed_value",
            "expected_value",
            "deviation_percentage",
            "anomaly_timestamp",
            "triage_status",
            "resolution_notes",
            "assigned_to",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Unexplained Revenue Spike in Region East"}),
            "model": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "kpi_definition": forms.Select(attrs={"class": "form-select"}),
            "metric_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. revenue, failed_logins"}),
            "anomaly_type": forms.Select(attrs={"class": "form-select"}),
            "detection_method": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "observed_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "expected_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "deviation_percentage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "anomaly_timestamp": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "triage_status": forms.Select(attrs={"class": "form-select"}),
            "resolution_notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea", "placeholder": "Investigation notes, root-cause confirmation, or remediation"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        if "data" in kwargs and kwargs["data"]:
            data = kwargs["data"].copy()
            if "root_cause_factors" in data and "root_cause_factors_raw" not in data:
                data["root_cause_factors_raw"] = json.dumps(data["root_cause_factors"]) if isinstance(data["root_cause_factors"], list) else str(data["root_cause_factors"])
            kwargs["data"] = data
        elif len(args) > 0 and args[0]:
            data = args[0].copy()
            if "root_cause_factors" in data and "root_cause_factors_raw" not in data:
                data["root_cause_factors_raw"] = json.dumps(data["root_cause_factors"]) if isinstance(data["root_cause_factors"], list) else str(data["root_cause_factors"])
            args = (data,) + args[1:]

        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["model"].queryset = PredictiveModel.objects.filter(tenant=self.tenant)
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
            self.fields["kpi_definition"].queryset = KpiDefinition.objects.filter(tenant=self.tenant)

        if self.instance and self.instance.pk:
            if self.instance.root_cause_factors:
                self.fields["root_cause_factors_raw"].initial = json.dumps(self.instance.root_cause_factors, indent=2)
            if self.instance.anomaly_timestamp:
                self.fields["anomaly_timestamp"].initial = self.instance.anomaly_timestamp.strftime("%Y-%m-%dT%H:%M")
        else:
            self.fields["root_cause_factors_raw"].initial = json.dumps([
                {"dimension": "Region", "segment": "North America", "contribution_percentage": 65.0},
                {"dimension": "ProductCategory", "segment": "Cloud Services", "contribution_percentage": 25.0}
            ], indent=2)

    def clean_root_cause_factors_raw(self):
        val = self.cleaned_data.get("root_cause_factors_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Root causes must be a JSON list of objects.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc

    def clean_model(self):
        return reject_foreign(self.tenant, self.cleaned_data.get("model"))

    def clean_semantic_model(self):
        return reject_foreign(self.tenant, self.cleaned_data.get("semantic_model"))

    def clean_kpi_definition(self):
        return reject_foreign(self.tenant, self.cleaned_data.get("kpi_definition"))

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.root_cause_factors = self.cleaned_data.get("root_cause_factors_raw", [])
        if commit:
            instance.save()
        return instance
