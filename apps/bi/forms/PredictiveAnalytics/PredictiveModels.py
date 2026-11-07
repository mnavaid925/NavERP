import json
from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.PredictiveAnalytics.PredictiveModels import PredictiveModel
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class PredictiveModelForm(TenantUniqueMixin, TenantModelForm):
    features_list_raw = forms.CharField(
        label="Training Features (JSON)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="JSON list of input feature names used for model fitting",
    )
    hyperparameters_raw = forms.CharField(
        label="Hyperparameters (JSON)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="JSON dictionary of model tuning parameters",
    )

    class Meta:
        model = PredictiveModel
        fields = [
            "name",
            "slug",
            "description",
            "problem_type",
            "algorithm",
            "semantic_model",
            "warehouse_table",
            "target_metric",
            "model_version",
            "drift_threshold",
            "is_active",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Demand Forecast Q4"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "auto-generated-if-blank"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "problem_type": forms.Select(attrs={"class": "form-select"}),
            "algorithm": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "target_metric": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. revenue, churn_flag"}),
            "model_version": forms.TextInput(attrs={"class": "form-input", "placeholder": "1.0.0"}),
            "drift_threshold": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        if "data" in kwargs and kwargs["data"]:
            data = kwargs["data"].copy()
            if "features_list" in data and "features_list_raw" not in data:
                data["features_list_raw"] = json.dumps(data["features_list"]) if isinstance(data["features_list"], list) else str(data["features_list"])
            if "hyperparameters" in data and "hyperparameters_raw" not in data:
                data["hyperparameters_raw"] = json.dumps(data["hyperparameters"]) if isinstance(data["hyperparameters"], dict) else str(data["hyperparameters"])
            kwargs["data"] = data
        elif len(args) > 0 and args[0]:
            data = args[0].copy()
            if "features_list" in data and "features_list_raw" not in data:
                data["features_list_raw"] = json.dumps(data["features_list"]) if isinstance(data["features_list"], list) else str(data["features_list"])
            if "hyperparameters" in data and "hyperparameters_raw" not in data:
                data["hyperparameters_raw"] = json.dumps(data["hyperparameters"]) if isinstance(data["hyperparameters"], dict) else str(data["hyperparameters"])
            args = (data,) + args[1:]

        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False
        if self.tenant is not None:
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant)

        if self.instance and self.instance.pk:
            if self.instance.features_list:
                self.fields["features_list_raw"].initial = json.dumps(self.instance.features_list, indent=2)
            if self.instance.hyperparameters:
                self.fields["hyperparameters_raw"].initial = json.dumps(self.instance.hyperparameters, indent=2)
        else:
            self.fields["features_list_raw"].initial = json.dumps(["historical_sales", "seasonal_index", "marketing_spend", "promotional_discount"], indent=2)
            self.fields["hyperparameters_raw"].initial = json.dumps({"learning_rate": 0.05, "n_estimators": 100, "max_depth": 5}, indent=2)

    def clean_features_list_raw(self):
        val = self.cleaned_data.get("features_list_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Features must be a JSON list of column names.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc

    def clean_hyperparameters_raw(self):
        val = self.cleaned_data.get("hyperparameters_raw", "").strip()
        if not val:
            return {}
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Hyperparameters must be a JSON dictionary.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["semantic_model", "warehouse_table"])
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.features_list = self.cleaned_data.get("features_list_raw", [])
        instance.hyperparameters = self.cleaned_data.get("hyperparameters_raw", {})
        if commit:
            instance.save()
        return instance
