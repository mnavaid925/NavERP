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
    coordinate_keys_raw = forms.CharField(
        label="Dimensional Coordinates (JSON)",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Key-value coordinates of the intersection cell (alias for cell_coordinates_raw)",
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
        if "data" in kwargs and kwargs["data"]:
            data = kwargs["data"].copy()
            if "baseline_amount" in data and "baseline_value" not in data:
                data["baseline_value"] = data["baseline_amount"]
            if "simulated_amount" in data and "adjusted_value" not in data:
                data["adjusted_value"] = data["simulated_amount"]
            if "adjustment_method" in data and "spread_method" not in data:
                data["spread_method"] = data["adjustment_method"]
            if "coordinate_keys_raw" in data and "cell_coordinates_raw" not in data:
                data["cell_coordinates_raw"] = data["coordinate_keys_raw"]
            elif "cell_coordinates_raw" in data and "coordinate_keys_raw" not in data:
                data["coordinate_keys_raw"] = data["cell_coordinates_raw"]
            kwargs["data"] = data
        elif len(args) > 0 and args[0]:
            data = args[0].copy()
            if "baseline_amount" in data and "baseline_value" not in data:
                data["baseline_value"] = data["baseline_amount"]
            if "simulated_amount" in data and "adjusted_value" not in data:
                data["adjusted_value"] = data["simulated_amount"]
            if "adjustment_method" in data and "spread_method" not in data:
                data["spread_method"] = data["adjustment_method"]
            if "coordinate_keys_raw" in data and "cell_coordinates_raw" not in data:
                data["cell_coordinates_raw"] = data["coordinate_keys_raw"]
            elif "cell_coordinates_raw" in data and "coordinate_keys_raw" not in data:
                data["coordinate_keys_raw"] = data["cell_coordinates_raw"]
            args = (data,) + args[1:]

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
                encoded = json.dumps(self.instance.cell_coordinates, indent=2)
                self.fields["cell_coordinates_raw"].initial = encoded
                self.fields["coordinate_keys_raw"].initial = encoded
        else:
            default_init = json.dumps({
                "period": "2026-Q1",
                "channel": "Enterprise Direct",
            }, indent=2)
            self.fields["cell_coordinates_raw"].initial = default_init
            self.fields["coordinate_keys_raw"].initial = default_init

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

    def clean_coordinate_keys_raw(self):
        val = self.cleaned_data.get("coordinate_keys_raw", "").strip()
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
        coords = self.cleaned_data.get("coordinate_keys_raw") or self.cleaned_data.get("cell_coordinates_raw")
        if coords is not None:
            instance.cell_coordinates = coords
        if commit:
            instance.save()
        return instance
