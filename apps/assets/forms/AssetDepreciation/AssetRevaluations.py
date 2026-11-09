from django import forms

from apps.accounting.models import FixedAsset, GLAccount
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetDepreciation.AssetRevaluations import AssetRevaluation
from apps.core.models import Party
from apps.scm.models import Asset


class AssetRevaluationForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetRevaluation
        fields = [
            "title",
            "fixed_asset",
            "operational_asset",
            "event_type",
            "valuation_method",
            "valuation_date",
            "appraiser",
            "appraiser_name_fallback",
            "new_fair_market_value",
            "new_salvage_value",
            "remaining_useful_life_months",
            "impairment_loss_account",
            "revaluation_surplus_account",
            "reason_and_methodology",
        ]
        exclude = [
            "tenant",
            "number",
            "historical_cost",
            "accumulated_depreciation_before",
            "carrying_value_before",
            "revaluation_adjustment",
            "journal_entry",
            "status",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 2026 Fleet Impairment Assessment"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "event_type": forms.Select(attrs={"class": "form-select"}),
            "valuation_method": forms.Select(attrs={"class": "form-select"}),
            "valuation_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "appraiser": forms.Select(attrs={"class": "form-select"}),
            "appraiser_name_fallback": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Valuation Partners LLC"}),
            "new_fair_market_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "new_salvage_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "remaining_useful_life_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "impairment_loss_account": forms.Select(attrs={"class": "form-select"}),
            "revaluation_surplus_account": forms.Select(attrs={"class": "form-select"}),
            "reason_and_methodology": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Document appraisal approach, observable market inputs, or physical impairment cause..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["appraiser"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["impairment_loss_account"].queryset = GLAccount.objects.filter(tenant=self.tenant).order_by("code")
            self.fields["revaluation_surplus_account"].queryset = GLAccount.objects.filter(tenant=self.tenant).order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(
                self,
                cleaned_data,
                [
                    "fixed_asset",
                    "operational_asset",
                    "appraiser",
                    "impairment_loss_account",
                    "revaluation_surplus_account",
                ],
            )
        return cleaned_data
