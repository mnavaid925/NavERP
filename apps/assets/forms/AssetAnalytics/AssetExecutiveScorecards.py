from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.AssetAnalytics._helpers import ZERO, scope_tenant_fields
from apps.assets.models.AssetAnalytics.AssetExecutiveScorecards import (
    AssetExecutiveScorecard,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.core.models.OrgUnit import OrgUnit

User = get_user_model()


class AssetExecutiveScorecardForm(TenantUniqueMixin, TenantModelForm):
    """Form for authoring and configuring Executive Asset KPI Scorecards [AKPI] in draft mode."""

    _TENANT_FIELDS = {
        "org_unit": OrgUnit,
        "asset_category": AssetCategory,
        "prepared_by": User,
        "approved_by": User,
    }

    class Meta:
        model = AssetExecutiveScorecard
        fields = [
            "title",
            "period_type",
            "period_start",
            "period_end",
            "org_unit",
            "asset_category",
            "currency",
            "prepared_by",
            "approved_by",
            "target_asset_roi_pct",
            "target_mcr_pct",
            "target_compliance_rate_pct",
            "annual_asset_return_amount",
            "executive_summary",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. FY2026 Q4 Board Asset Intelligence Scorecard"}
            ),
            "period_type": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "asset_category": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "prepared_by": forms.Select(attrs={"class": "form-select"}),
            "approved_by": forms.Select(attrs={"class": "form-select"}),
            "target_asset_roi_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "target_mcr_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "target_compliance_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "annual_asset_return_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "executive_summary": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Executive board commentary, reliability highlights, and strategic capex ask..."}
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
        start = cleaned.get("period_start")
        end = cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "Period end date cannot be earlier than period start date.")
        mcr = cleaned.get("target_mcr_pct")
        if mcr is not None and (mcr < ZERO or mcr > Decimal("100.00")):
            self.add_error("target_mcr_pct", "Target MCR % must be between 0% and 100%.")
        comp = cleaned.get("target_compliance_rate_pct")
        if comp is not None and (comp < ZERO or comp > Decimal("100.00")):
            self.add_error("target_compliance_rate_pct", "Target compliance pass rate must be between 0% and 100%.")
        return cleaned
