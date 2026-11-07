import json
from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.PredictiveAnalytics.OptimizationScenarios import OptimizationScenario
from apps.core.forms import TenantModelForm


class OptimizationScenarioForm(TenantUniqueMixin, TenantModelForm):
    decision_variables_raw = forms.CharField(
        label="Decision Variables (JSON)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Controllable levers, boundaries, and increments",
    )
    constraint_rules_raw = forms.CharField(
        label="Constraint Rules (JSON)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Operational boundaries and mathematical constraints",
    )

    class Meta:
        model = OptimizationScenario
        fields = [
            "name",
            "slug",
            "description",
            "objective_type",
            "target_metric_name",
            "kpi_definition",
            "baseline_value",
            "target_value",
            "solver_algorithm",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 Logistics Cost Minimization"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "auto-generated-if-blank"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "objective_type": forms.Select(attrs={"class": "form-select"}),
            "target_metric_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. gross_margin, operating_expense"}),
            "kpi_definition": forms.Select(attrs={"class": "form-select"}),
            "baseline_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "target_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "solver_algorithm": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        if "data" in kwargs and kwargs["data"]:
            data = kwargs["data"].copy()
            if "decision_variables" in data and "decision_variables_raw" not in data:
                data["decision_variables_raw"] = json.dumps(data["decision_variables"]) if isinstance(data["decision_variables"], list) else str(data["decision_variables"])
            if "constraint_rules" in data and "constraint_rules_raw" not in data:
                data["constraint_rules_raw"] = json.dumps(data["constraint_rules"]) if isinstance(data["constraint_rules"], list) else str(data["constraint_rules"])
            kwargs["data"] = data
        elif len(args) > 0 and args[0]:
            data = args[0].copy()
            if "decision_variables" in data and "decision_variables_raw" not in data:
                data["decision_variables_raw"] = json.dumps(data["decision_variables"]) if isinstance(data["decision_variables"], list) else str(data["decision_variables"])
            if "constraint_rules" in data and "constraint_rules_raw" not in data:
                data["constraint_rules_raw"] = json.dumps(data["constraint_rules"]) if isinstance(data["constraint_rules"], list) else str(data["constraint_rules"])
            args = (data,) + args[1:]

        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False
        if self.tenant is not None:
            self.fields["kpi_definition"].queryset = KpiDefinition.objects.filter(tenant=self.tenant)

        if self.instance and self.instance.pk:
            if self.instance.decision_variables:
                self.fields["decision_variables_raw"].initial = json.dumps(self.instance.decision_variables, indent=2)
            if self.instance.constraint_rules:
                self.fields["constraint_rules_raw"].initial = json.dumps(self.instance.constraint_rules, indent=2)
        else:
            self.fields["decision_variables_raw"].initial = json.dumps([
                {"name": "marketing_budget", "min": 10000, "max": 50000, "step": 1000},
                {"name": "headcount_allocation", "min": 5, "max": 20, "step": 1}
            ], indent=2)
            self.fields["constraint_rules_raw"].initial = json.dumps([
                {"name": "total_spend_cap", "expression": "marketing_budget + (headcount_allocation * 5000) <= 120000"}
            ], indent=2)

    def clean_decision_variables_raw(self):
        val = self.cleaned_data.get("decision_variables_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Decision variables must be a JSON list of objects.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc

    def clean_constraint_rules_raw(self):
        val = self.cleaned_data.get("constraint_rules_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Constraints must be a JSON list of objects.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc

    def clean_kpi_definition(self):
        return reject_foreign(self.tenant, self.cleaned_data.get("kpi_definition"))

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.decision_variables = self.cleaned_data.get("decision_variables_raw", [])
        instance.constraint_rules = self.cleaned_data.get("constraint_rules_raw", [])
        if commit:
            instance.save()
        return instance
