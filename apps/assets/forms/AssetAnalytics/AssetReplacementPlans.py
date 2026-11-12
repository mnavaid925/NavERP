from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models.Budgeting.Budgets import Budget
from apps.accounting.models.FixedAssets.FixedAssetsRegister import FixedAsset
from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.AssetAnalytics._helpers import (
    ZERO,
    scope_tenant_fields,
    validate_non_negative_fields,
)
from apps.assets.models.AssetAnalytics.AssetLifecycleCostAnalyses import (
    AssetLifecycleCostAnalysis,
)
from apps.assets.models.AssetAnalytics.AssetReplacementPlans import AssetReplacementPlan
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.assets.models.AssetProcurement.AssetRequisitions import AssetRequisition
from apps.assets.models.AssetReliability.AssetConditionAssessments import (
    AssetConditionAssessment,
)
from apps.core.models.OrgUnit import OrgUnit
from apps.scm.models.AssetManagement.Assets import Asset
from apps.scm.models.InventoryManagement.Locations import Location

User = get_user_model()


class AssetReplacementPlanForm(TenantUniqueMixin, TenantModelForm):
    """Form for creating and editing Asset Replacement Plans [ARPL]."""

    _TENANT_FIELDS = {
        "fixed_asset": FixedAsset,
        "operational_asset": Asset,
        "asset_category": AssetCategory,
        "asset_model": AssetModel,
        "org_unit": OrgUnit,
        "location": Location,
        "condition_assessment": AssetConditionAssessment,
        "lifecycle_analysis": AssetLifecycleCostAnalysis,
        "capital_budget": Budget,
        "linked_requisition": AssetRequisition,
        "planner": User,
    }

    _SELECT_RELATED = {
        "fixed_asset": ("location", "custodian"),
        "operational_asset": ("org_unit", "location", "fixed_asset"),
        "asset_model": ("category", "manufacturer"),
        "condition_assessment": ("operational_asset", "fixed_asset", "asset_category"),
        "lifecycle_analysis": ("operational_asset", "fixed_asset", "asset_category"),
        "capital_budget": ("fiscal_period",),
        "linked_requisition": ("currency", "target_org_unit"),
    }

    _MONETARY_FIELDS = (
        "current_replacement_value",
        "deferred_maintenance_cost",
        "estimated_replacement_cost",
        "estimated_salvage_recovery",
        "deferral_penalty_cost",
    )

    class Meta:
        model = AssetReplacementPlan
        fields = [
            "title",
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "asset_model",
            "org_unit",
            "location",
            "currency",
            "condition_assessment",
            "lifecycle_analysis",
            "capital_budget",
            "linked_requisition",
            "planner",
            "predicted_eol_date",
            "remaining_useful_life_months",
            "planned_replacement_year",
            "planned_quarter",
            "replacement_strategy",
            "funding_status",
            "condition_score",
            "criticality_weight",
            "failure_risk_score",
            "current_replacement_value",
            "deferred_maintenance_cost",
            "estimated_replacement_cost",
            "inflation_rate_pct",
            "estimated_salvage_recovery",
            "deferral_penalty_cost",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Cooling Tower #3 End-of-Life Capital Replacement"}
            ),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "asset_category": forms.Select(attrs={"class": "form-select"}),
            "asset_model": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "location": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "condition_assessment": forms.Select(attrs={"class": "form-select"}),
            "lifecycle_analysis": forms.Select(attrs={"class": "form-select"}),
            "capital_budget": forms.Select(attrs={"class": "form-select"}),
            "linked_requisition": forms.Select(attrs={"class": "form-select"}),
            "planner": forms.Select(attrs={"class": "form-select"}),
            "predicted_eol_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "remaining_useful_life_months": forms.NumberInput(attrs={"class": "form-input", "min": "0", "max": "1200"}),
            "planned_replacement_year": forms.NumberInput(attrs={"class": "form-input", "min": "2000", "max": "2100"}),
            "planned_quarter": forms.Select(attrs={"class": "form-select"}),
            "replacement_strategy": forms.Select(attrs={"class": "form-select"}),
            "funding_status": forms.Select(attrs={"class": "form-select"}),
            "condition_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "criticality_weight": forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "10"}),
            "failure_risk_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "current_replacement_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "deferred_maintenance_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "estimated_replacement_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "inflation_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "50"}),
            "estimated_salvage_recovery": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "deferral_penalty_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "notes": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Engineering justification, lead time, and capital funding notes..."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scope_tenant_fields(
            self,
            self._TENANT_FIELDS,
            global_querysets={"currency": Currency.objects.filter(is_active=True)},
            select_related_map=self._SELECT_RELATED,
        )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, list(self._TENANT_FIELDS.keys()))
        crit = cleaned.get("criticality_weight")
        if crit is not None and not (1 <= crit <= 10):
            self.add_error("criticality_weight", "Criticality weight must be between 1 and 10.")
        rul = cleaned.get("remaining_useful_life_months")
        if rul is not None and not (0 <= rul <= 1200):
            self.add_error("remaining_useful_life_months", "Remaining useful life must be between 0 and 1200 months.")
        cond = cleaned.get("condition_score")
        if cond is not None and (cond < ZERO or cond > Decimal("100.00")):
            self.add_error("condition_score", "Condition score must be between 0 and 100.")
        risk = cleaned.get("failure_risk_score")
        if risk is not None and (risk < ZERO or risk > Decimal("100.00")):
            self.add_error("failure_risk_score", "Failure risk score must be between 0 and 100.")
        inf = cleaned.get("inflation_rate_pct")
        if inf is not None and (inf < ZERO or inf > Decimal("50.00")):
            self.add_error("inflation_rate_pct", "Inflation rate must be between 0% and 50%.")
        year = cleaned.get("planned_replacement_year")
        if year is not None and not (2000 <= year <= 2100):
            self.add_error("planned_replacement_year", "Planned replacement year must be between 2000 and 2100.")
        validate_non_negative_fields(self, cleaned, self._MONETARY_FIELDS)
        return cleaned
