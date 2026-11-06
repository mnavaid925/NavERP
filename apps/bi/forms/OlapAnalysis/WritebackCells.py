import json
from decimal import Decimal
from django import forms
from django.db.models import Q

from apps.accounting.models import GLAccount
from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.OlapAnalysis.WhatIfScenarios import WhatIfScenario
from apps.bi.models.OlapAnalysis.WritebackCells import ScenarioWritebackCell
from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit


class ScenarioWritebackCellForm(TenantUniqueMixin, TenantModelForm):
    cell_coordinates_raw = forms.CharField(
        label="Dimensional Coordinates (JSON)",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Key-value coordinates of the intersection cell, e.g. {\"period\": \"2026-Q1\", \"region\": \"North America\"}",
    )

    class Meta:
        model = ScenarioWritebackCell
        fields = [
            "scenario",
            "gl_account",
            "org_unit",
            "baseline_value",
            "adjusted_value",
            "spread_method",
            "commentary",
        ]
        widgets = {
            "scenario": forms.Select(attrs={"class": "form-select"}),
            "gl_account": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "baseline_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "adjusted_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "spread_method": forms.Select(attrs={"class": "form-select"}),
            "commentary": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            scenario_qs = WhatIfScenario.objects.filter(tenant=self.tenant).exclude(status="committed")
            if self.instance and self.instance.pk and self.instance.scenario_id:
                scenario_qs = WhatIfScenario.objects.filter(tenant=self.tenant).filter(
                    Q(status__in=["draft", "simulated", "approved"]) | Q(pk=self.instance.scenario_id)
                )
            self.fields["scenario"].queryset = scenario_qs
            self.fields["gl_account"].queryset = GLAccount.objects.filter(tenant=self.tenant)
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant)

        if self.instance and self.instance.pk:
            if self.instance.cell_coordinates:
                self.fields["cell_coordinates_raw"].initial = json.dumps(self.instance.cell_coordinates, indent=2)
        else:
            self.fields["cell_coordinates_raw"].initial = json.dumps({
                "period": "2026-Q1",
                "channel": "Enterprise Direct",
            }, indent=2)

    def clean_scenario(self):
        scenario = self.cleaned_data.get("scenario")
        if scenario and scenario.status == "committed":
            raise forms.ValidationError("Adjustments cannot be attached to a committed scenario.")
        return scenario

    def clean_cell_coordinates_raw(self):
        val = self.cleaned_data.get("cell_coordinates_raw", "").strip()
        if not val:
            return {}
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Coordinates must be a JSON object of key-value pairs.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["scenario", "gl_account", "org_unit"])
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "cell_coordinates_raw" in self.cleaned_data:
            instance.cell_coordinates = self.cleaned_data["cell_coordinates_raw"]
        if commit:
            instance.save()
        return instance
