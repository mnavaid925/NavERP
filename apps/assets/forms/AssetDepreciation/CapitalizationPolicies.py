from django import forms

from apps.accounting.models import GLAccount
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetDepreciation.CapitalizationPolicies import CapitalizationPolicy


class CapitalizationPolicyForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = CapitalizationPolicy
        fields = [
            "name",
            "policy_scope",
            "category",
            "minimum_cost_threshold",
            "minimum_useful_life_months",
            "default_classification",
            "de_minimis_safe_harbor",
            "applicable_gaap_standard",
            "default_cip_account",
            "default_expense_account",
            "effective_from",
            "effective_to",
            "is_active",
            "policy_notes",
        ]
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. IRS De Minimis Safe Harbor Rule ($2,500)"}),
            "policy_scope": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "minimum_cost_threshold": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "minimum_useful_life_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "default_classification": forms.Select(attrs={"class": "form-select"}),
            "de_minimis_safe_harbor": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "applicable_gaap_standard": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. US GAAP / IFRS IAS 16"}),
            "default_cip_account": forms.Select(attrs={"class": "form-select"}),
            "default_expense_account": forms.Select(attrs={"class": "form-select"}),
            "effective_from": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effective_to": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "policy_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Accounting policy documentation, threshold justification, and audit notes..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["category"].queryset = AssetCategory.objects.filter(tenant=self.tenant, is_active=True).order_by("code")
            gl_accounts = GLAccount.objects.filter(tenant=self.tenant).order_by("code")
            self.fields["default_cip_account"].queryset = gl_accounts
            self.fields["default_expense_account"].queryset = gl_accounts

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(
                self,
                cleaned_data,
                [
                    "category",
                    "default_cip_account",
                    "default_expense_account",
                ],
            )
        return cleaned_data
