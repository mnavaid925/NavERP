from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset, GLAccount
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetDepreciation.AssetTransfers import AssetTransfer
from apps.core.models import OrgUnit, Party
from apps.scm.models import Asset, Location

User = get_user_model()


class AssetTransferForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetTransfer
        fields = [
            "title",
            "fixed_asset",
            "operational_asset",
            "transfer_type",
            "transfer_date",
            "source_department",
            "source_location",
            "source_custodian",
            "source_expense_account",
            "destination_department",
            "destination_location",
            "destination_custodian",
            "destination_expense_account",
            "transportation_cost",
            "transferred_by",
            "reason",
        ]
        exclude = [
            "tenant",
            "number",
            "carrying_value_at_transfer",
            "journal_entry",
            "status",
            "received_by",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Relocation of CNC Lathe to Plant 2"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "transfer_type": forms.Select(attrs={"class": "form-select"}),
            "transfer_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "source_department": forms.Select(attrs={"class": "form-select"}),
            "source_location": forms.Select(attrs={"class": "form-select"}),
            "source_custodian": forms.Select(attrs={"class": "form-select"}),
            "source_expense_account": forms.Select(attrs={"class": "form-select"}),
            "destination_department": forms.Select(attrs={"class": "form-select"}),
            "destination_location": forms.Select(attrs={"class": "form-select"}),
            "destination_custodian": forms.Select(attrs={"class": "form-select"}),
            "destination_expense_account": forms.Select(attrs={"class": "form-select"}),
            "transportation_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "transferred_by": forms.Select(attrs={"class": "form-select"}),
            "reason": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Operational justification, relocation logistics, and approval notes..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=self.tenant).order_by("name")
            org_units = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["source_department"].queryset = org_units
            self.fields["destination_department"].queryset = org_units
            locations = Location.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["source_location"].queryset = locations
            self.fields["destination_location"].queryset = locations
            parties = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["source_custodian"].queryset = parties
            self.fields["destination_custodian"].queryset = parties
            gl_accounts = GLAccount.objects.filter(tenant=self.tenant).order_by("code")
            self.fields["source_expense_account"].queryset = gl_accounts
            self.fields["destination_expense_account"].queryset = gl_accounts
            self.fields["transferred_by"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(
                self,
                cleaned_data,
                [
                    "fixed_asset",
                    "operational_asset",
                    "source_department",
                    "source_location",
                    "source_custodian",
                    "source_expense_account",
                    "destination_department",
                    "destination_location",
                    "destination_custodian",
                    "destination_expense_account",
                ],
            )
        return cleaned_data
