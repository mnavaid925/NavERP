import json
from django import forms

from apps.accounting.models import Budget, FiscalPeriod
from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.OlapAnalysis.OlapCubes import OlapCube
from apps.bi.models.OlapAnalysis.WhatIfScenarios import WhatIfScenario
from apps.core.forms import TenantModelForm


class WhatIfScenarioForm(TenantUniqueMixin, TenantModelForm):
    driver_parameters_raw = forms.CharField(
        label="Simulation Drivers (JSON)",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Key scenario driver multipliers: e.g. {\"revenue_growth_pct\": 10.5, \"labor_cost_inflation_pct\": 4.0}",
    )

    class Meta:
        model = WhatIfScenario
        fields = [
            "name",
            "slug",
            "description",
            "cube",
            "baseline_budget",
            "fiscal_period",
            "default_disaggregation",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FY2026 Optimistic Expansion Scenario"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "auto-generated-if-blank"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "cube": forms.Select(attrs={"class": "form-select"}),
            "baseline_budget": forms.Select(attrs={"class": "form-select"}),
            "fiscal_period": forms.Select(attrs={"class": "form-select"}),
            "default_disaggregation": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["cube"].queryset = OlapCube.objects.filter(tenant=self.tenant)
            self.fields["baseline_budget"].queryset = Budget.objects.filter(tenant=self.tenant)
            self.fields["fiscal_period"].queryset = FiscalPeriod.objects.filter(tenant=self.tenant)

        if self.instance and self.instance.pk:
            if self.instance.driver_parameters:
                self.fields["driver_parameters_raw"].initial = json.dumps(self.instance.driver_parameters, indent=2)
        else:
            self.fields["driver_parameters_raw"].initial = json.dumps({
                "revenue_growth_pct": 8.0,
                "cost_inflation_pct": 3.5,
                "headcount_multiplier": 1.05,
            }, indent=2)

    def clean_driver_parameters_raw(self):
        val = self.cleaned_data.get("driver_parameters_raw", "").strip()
        if not val:
            return {}
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Driver parameters must be a JSON object (key-value dictionary).")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["cube", "baseline_budget", "fiscal_period"])
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "driver_parameters_raw" in self.cleaned_data:
            instance.driver_parameters = self.cleaned_data["driver_parameters_raw"]
        if commit:
            instance.save()
        return instance
