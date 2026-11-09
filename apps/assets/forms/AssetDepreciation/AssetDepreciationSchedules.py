from django import forms

from apps.accounting.models import FiscalPeriod, FixedAsset, GLAccount
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetDepreciation.AssetDepreciationSchedules import AssetDepreciationSchedule
from apps.core.models import OrgUnit
from apps.scm.models import Asset


class AssetDepreciationScheduleForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetDepreciationSchedule
        fields = [
            "fixed_asset",
            "operational_asset",
            "fiscal_period",
            "fiscal_year",
            "period_number",
            "period_frequency",
            "schedule_date",
            "depreciation_method",
            "starting_book_value",
            "depreciation_amount",
            "total_units_expected",
            "units_produced_period",
            "expense_account",
            "accumulated_account",
            "cost_center",
            "notes",
        ]
        exclude = [
            "tenant",
            "number",
            "accumulated_depreciation_after",
            "ending_book_value",
            "journal_entry",
            "status",
            "posted_at",
            "posted_by",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "fiscal_period": forms.Select(attrs={"class": "form-select"}),
            "fiscal_year": forms.NumberInput(attrs={"class": "form-input", "min": "2000", "max": "2100"}),
            "period_number": forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "12"}),
            "period_frequency": forms.Select(attrs={"class": "form-select"}),
            "schedule_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "depreciation_method": forms.Select(attrs={"class": "form-select"}),
            "starting_book_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "depreciation_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "total_units_expected": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "units_produced_period": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "expense_account": forms.Select(attrs={"class": "form-select"}),
            "accumulated_account": forms.Select(attrs={"class": "form-select"}),
            "cost_center": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Schedule notes..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["fiscal_period"].queryset = FiscalPeriod.objects.filter(tenant=self.tenant).order_by("-start_date")
            self.fields["expense_account"].queryset = GLAccount.objects.filter(tenant=self.tenant).order_by("code")
            self.fields["accumulated_account"].queryset = GLAccount.objects.filter(tenant=self.tenant).order_by("code")
            self.fields["cost_center"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(
                self,
                cleaned_data,
                [
                    "fixed_asset",
                    "operational_asset",
                    "fiscal_period",
                    "expense_account",
                    "accumulated_account",
                    "cost_center",
                ],
            )
        return cleaned_data
