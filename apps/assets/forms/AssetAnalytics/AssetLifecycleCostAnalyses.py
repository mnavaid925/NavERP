from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

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
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.core.models.OrgUnit import OrgUnit
from apps.scm.models.AssetManagement.Assets import Asset

User = get_user_model()


class AssetLifecycleCostAnalysisForm(TenantUniqueMixin, TenantModelForm):
    """Form for creating and editing Asset Lifecycle Cost Analysis studies [ALCC]."""

    _TENANT_FIELDS = {
        "fixed_asset": FixedAsset,
        "operational_asset": Asset,
        "asset_category": AssetCategory,
        "asset_model": AssetModel,
        "org_unit": OrgUnit,
        "analyzed_by": User,
    }

    _MONETARY_FIELDS = (
        "acquisition_capital_cost",
        "installation_commissioning_cost",
        "preventive_maintenance_cost",
        "corrective_maintenance_cost",
        "service_contract_cost",
        "energy_utility_cost",
        "downtime_opportunity_cost",
        "insurance_compliance_cost",
        "accumulated_depreciation_cost",
        "expected_salvage_value",
        "warranty_insurance_recoveries",
        "current_replacement_value",
    )

    class Meta:
        model = AssetLifecycleCostAnalysis
        fields = [
            "title",
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "asset_model",
            "org_unit",
            "currency",
            "analyzed_by",
            "analysis_date",
            "analysis_horizon_years",
            "discount_rate_pct",
            "lifecycle_stage",
            "status",
            "acquisition_capital_cost",
            "installation_commissioning_cost",
            "preventive_maintenance_cost",
            "corrective_maintenance_cost",
            "service_contract_cost",
            "energy_utility_cost",
            "downtime_opportunity_cost",
            "insurance_compliance_cost",
            "accumulated_depreciation_cost",
            "expected_salvage_value",
            "warranty_insurance_recoveries",
            "current_replacement_value",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Chiller Plant #2 10-Year TCO & Replacement Study"}
            ),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "asset_category": forms.Select(attrs={"class": "form-select"}),
            "asset_model": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "analyzed_by": forms.Select(attrs={"class": "form-select"}),
            "analysis_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "analysis_horizon_years": forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "50"}),
            "discount_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "lifecycle_stage": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "acquisition_capital_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "installation_commissioning_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "preventive_maintenance_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "corrective_maintenance_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "service_contract_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "energy_utility_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "downtime_opportunity_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "insurance_compliance_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "accumulated_depreciation_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "expected_salvage_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "warranty_insurance_recoveries": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "current_replacement_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "notes": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "LCC assumptions, operating conditions, and EOL rationale..."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scope_tenant_fields(
            self,
            self._TENANT_FIELDS,
            global_querysets={"currency": Currency.objects.filter(is_active=True)},
        )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, list(self._TENANT_FIELDS.keys()))
        horizon = cleaned.get("analysis_horizon_years")
        if horizon is not None and horizon < 1:
            self.add_error("analysis_horizon_years", "Analysis horizon must be at least 1 year.")
        rate = cleaned.get("discount_rate_pct")
        if rate is not None and (rate < ZERO or rate > Decimal("100.00")):
            self.add_error("discount_rate_pct", "Discount rate must be between 0.00% and 100.00%.")
        validate_non_negative_fields(self, cleaned, self._MONETARY_FIELDS)
        return cleaned
