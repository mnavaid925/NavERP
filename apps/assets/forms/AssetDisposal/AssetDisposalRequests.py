from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetCategory
from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
from apps.core.models import OrgUnit
from apps.scm.models import Asset as OperationalAsset

User = get_user_model()


class AssetDisposalRequestForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetDisposalRequest
        fields = [
            "title",
            "fixed_asset",
            "operational_asset",
            "category",
            "cost_center",
            "requested_by",
            "appraised_by",
            "disposal_method",
            "retirement_reason",
            "justification_notes",
            "acquisition_cost",
            "accumulated_depreciation",
            "net_book_value",
            "estimated_residual_value",
            "estimated_removal_cost",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Retirement & Salvage of Obsolete Extrusion Press Line"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "cost_center": forms.Select(attrs={"class": "form-select"}),
            "requested_by": forms.Select(attrs={"class": "form-select"}),
            "appraised_by": forms.Select(attrs={"class": "form-select"}),
            "disposal_method": forms.Select(attrs={"class": "form-select"}),
            "retirement_reason": forms.Select(attrs={"class": "form-select"}),
            "justification_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Technical, economic, or safety justification for asset decommissioning..."}),
            "acquisition_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "accumulated_depreciation": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "net_book_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "estimated_residual_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "estimated_removal_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in [
            "acquisition_cost",
            "accumulated_depreciation",
            "net_book_value",
            "estimated_residual_value",
            "estimated_removal_cost",
        ]:
            if f in self.fields:
                self.fields[f].required = False

        if self.tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)
            self.fields["category"].queryset = AssetCategory.objects.filter(tenant=self.tenant)
            self.fields["cost_center"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["requested_by"].queryset = user_qs
            self.fields["appraised_by"].queryset = user_qs

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "fixed_asset",
                "operational_asset",
                "category",
                "cost_center",
                "requested_by",
                "appraised_by",
            ],
        )

        # Auto-derive financial amounts from fixed_asset if empty/zero
        fa = cleaned.get("fixed_asset")
        if fa:
            if not cleaned.get("acquisition_cost"):
                cleaned["acquisition_cost"] = fa.acquisition_cost or Decimal("0.00")
            if not cleaned.get("accumulated_depreciation"):
                cleaned["accumulated_depreciation"] = getattr(fa, "accumulated_depreciation", Decimal("0.00")) or Decimal("0.00")
            if not cleaned.get("net_book_value"):
                cleaned["net_book_value"] = getattr(fa, "net_book_value", Decimal("0.00")) or (
                    cleaned["acquisition_cost"] - cleaned["accumulated_depreciation"]
                )

        for f in ["acquisition_cost", "accumulated_depreciation", "net_book_value", "estimated_residual_value", "estimated_removal_cost"]:
            if cleaned.get(f) is None:
                cleaned[f] = Decimal("0.00")

        return cleaned


class AssetDisposalAppraisalForm(forms.Form):
    appraised_by = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )
    estimated_residual_value = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        required=True,
    )
    estimated_removal_cost = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        required=False,
        initial=Decimal("0.00"),
    )
    appraisal_notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Appraiser inspection comments and valuation rationale..."}),
        required=False,
    )

    def __init__(self, tenant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant:
            self.fields["appraised_by"].queryset = User.objects.filter(tenant=tenant, is_active=True).order_by("username")


class AssetDisposalRejectForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "State why this asset retirement request is declined..."}),
        required=True,
    )
