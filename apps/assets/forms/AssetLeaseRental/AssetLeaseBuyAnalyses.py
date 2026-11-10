from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetCategory
from apps.assets.models.AssetLeaseRental.AssetLeaseBuyAnalyses import AssetLeaseBuyAnalysis

User = get_user_model()


class AssetLeaseBuyAnalysisForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetLeaseBuyAnalysis
        fields = [
            "title",
            "description",
            "target_asset_name",
            "category",
            "expected_useful_life_years",
            "purchase_price",
            "down_payment_pct",
            "loan_interest_rate_pct",
            "loan_term_years",
            "estimated_salvage_value",
            "annual_maintenance_cost_buy",
            "annual_insurance_tax_buy",
            "lease_term_months",
            "monthly_lease_payment",
            "upfront_lease_fees",
            "end_of_lease_purchase_option",
            "lessor_covers_maintenance",
            "annual_maintenance_cost_lease",
            "discount_rate_wacc_pct",
            "corporate_tax_rate_pct",
            "status",
            "evaluated_by",
            "evaluation_notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Capital Decision: Heavy Excavator Fleet Expansion"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Operational requirements, workload volume, and asset objectives..."}),
            "target_asset_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Caterpillar 336 Hydraulic Excavator"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "expected_useful_life_years": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "min": "0.5"}),
            "purchase_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "down_payment_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "loan_interest_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "loan_term_years": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "min": "0.5"}),
            "estimated_salvage_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "annual_maintenance_cost_buy": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "annual_insurance_tax_buy": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "lease_term_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "monthly_lease_payment": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "upfront_lease_fees": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "end_of_lease_purchase_option": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "lessor_covers_maintenance": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "annual_maintenance_cost_lease": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "discount_rate_wacc_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "corporate_tax_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "evaluated_by": forms.Select(attrs={"class": "form-select"}),
            "evaluation_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Executive conclusion and strategic qualitative remarks..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["category"].queryset = AssetCategory.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["evaluated_by"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["category", "evaluated_by"])

        pct_fields = [
            "down_payment_pct",
            "loan_interest_rate_pct",
            "discount_rate_wacc_pct",
            "corporate_tax_rate_pct",
        ]
        for f in pct_fields:
            val = cleaned.get(f)
            if val is not None and (val < 0 or val > 100):
                self.add_error(f, "Percentage must be between 0% and 100%.")

        non_negative_fields = [
            "purchase_price",
            "estimated_salvage_value",
            "annual_maintenance_cost_buy",
            "annual_insurance_tax_buy",
            "monthly_lease_payment",
            "upfront_lease_fees",
            "end_of_lease_purchase_option",
            "annual_maintenance_cost_lease",
        ]
        for f in non_negative_fields:
            val = cleaned.get(f)
            if val is not None and val < 0:
                self.add_error(f, "Amount cannot be negative.")

        return cleaned
