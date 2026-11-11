from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.AssetAnalytics._helpers import ZERO, scope_tenant_fields
from apps.assets.models.AssetAnalytics.AssetPortfolioScenarios import (
    AssetPortfolioScenario,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.core.models.OrgUnit import OrgUnit

User = get_user_model()


class AssetPortfolioScenarioForm(TenantUniqueMixin, TenantModelForm):
    """Form for creating and editing What-If Portfolio Scenarios [AWIF]."""

    _TENANT_FIELDS = {
        "scope_org_unit": OrgUnit,
        "scope_category": AssetCategory,
        "baseline_scenario": AssetPortfolioScenario,
        "owner": User,
    }

    class Meta:
        model = AssetPortfolioScenario
        fields = [
            "name",
            "scenario_type",
            "is_baseline",
            "base_fiscal_year",
            "horizon_years",
            "scope_org_unit",
            "scope_category",
            "currency",
            "baseline_scenario",
            "owner",
            "annual_capex_budget_limit",
            "discount_rate_pct",
            "inflation_rate_pct",
            "acceleration_months",
            "fleet_growth_pct",
            "consolidation_reduction_pct",
            "maintenance_efficiency_gain_pct",
            "assumptions_summary",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. FY2027 Accelerated Chiller & Fleet Replacement"}
            ),
            "scenario_type": forms.Select(attrs={"class": "form-select"}),
            "is_baseline": forms.CheckboxInput(attrs={"class": "form-check"}),
            "base_fiscal_year": forms.NumberInput(attrs={"class": "form-input", "min": "2000", "max": "2100"}),
            "horizon_years": forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "30"}),
            "scope_org_unit": forms.Select(attrs={"class": "form-select"}),
            "scope_category": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "baseline_scenario": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "annual_capex_budget_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "discount_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "inflation_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "50"}),
            "acceleration_months": forms.NumberInput(attrs={"class": "form-input"}),
            "fleet_growth_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "consolidation_reduction_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "maintenance_efficiency_gain_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "assumptions_summary": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Key financial, capacity, and risk-tolerance modeling assumptions..."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scope_tenant_fields(
            self,
            self._TENANT_FIELDS,
            global_querysets={"currency": Currency.objects.filter(is_active=True)},
        )
        if self.instance and self.instance.pk and "baseline_scenario" in self.fields:
            self.fields["baseline_scenario"].queryset = self.fields["baseline_scenario"].queryset.exclude(
                pk=self.instance.pk
            )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, list(self._TENANT_FIELDS.keys()))
        base = cleaned.get("baseline_scenario")
        if self.instance and self.instance.pk and base and base.pk == self.instance.pk:
            self.add_error("baseline_scenario", "A scenario cannot reference itself as its baseline.")
        horizon = cleaned.get("horizon_years")
        if horizon is not None and horizon < 1:
            self.add_error("horizon_years", "Horizon must be at least 1 year.")
        year = cleaned.get("base_fiscal_year")
        if year is not None and not (2000 <= year <= 2100):
            self.add_error("base_fiscal_year", "Base fiscal year must be between 2000 and 2100.")
        budget = cleaned.get("annual_capex_budget_limit")
        if budget is not None and budget < ZERO:
            self.add_error("annual_capex_budget_limit", "Budget cap cannot be negative.")
        disc = cleaned.get("discount_rate_pct")
        if disc is not None and (disc < ZERO or disc > Decimal("100.00")):
            self.add_error("discount_rate_pct", "Discount rate must be between 0% and 100%.")
        inf = cleaned.get("inflation_rate_pct")
        if inf is not None and (inf < ZERO or inf > Decimal("50.00")):
            self.add_error("inflation_rate_pct", "Inflation rate must be between 0% and 50%.")
        consol = cleaned.get("consolidation_reduction_pct")
        if consol is not None and (consol < ZERO or consol > Decimal("100.00")):
            self.add_error("consolidation_reduction_pct", "Consolidation reduction must be between 0% and 100%.")
        eff = cleaned.get("maintenance_efficiency_gain_pct")
        if eff is not None and (eff < ZERO or eff > Decimal("100.00")):
            self.add_error("maintenance_efficiency_gain_pct", "Efficiency gain must be between 0% and 100%.")
        return cleaned
