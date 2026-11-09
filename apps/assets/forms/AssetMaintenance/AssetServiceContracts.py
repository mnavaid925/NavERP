from django import forms

from apps.accounting.models import Currency, FixedAsset
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetMaintenance.AssetServiceContracts import AssetServiceContract
from apps.core.models import Party
from apps.scm.models import Asset


class AssetServiceContractForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetServiceContract
        fields = [
            "contract_number",
            "title",
            "vendor",
            "fixed_asset",
            "operational_asset",
            "contract_type",
            "start_date",
            "end_date",
            "contract_value",
            "currency",
            "billing_frequency",
            "sla_response_hours",
            "sla_resolution_hours",
            "pm_visits_included",
            "coverage_terms",
            "auto_renew",
            "contact_person",
            "contact_phone",
            "contact_email",
            "notes",
        ]
        exclude = [
            "tenant",
            "number",
            "status",
            "pm_visits_completed",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "contract_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. AMC-2026-CAT-09"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Caterpillar Engine Comprehensive Maintenance"}),
            "vendor": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "contract_type": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "contract_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "billing_frequency": forms.Select(attrs={"class": "form-select"}),
            "sla_response_hours": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "sla_resolution_hours": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "pm_visits_included": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "coverage_terms": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Coverage scope, parts included/excluded, emergency response clauses..."}),
            "auto_renew": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "contact_person": forms.TextInput(attrs={"class": "form-input", "placeholder": "Vendor contact name"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "Phone / hotline"}),
            "contact_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "Support email"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self, "tenant", None) or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["vendor"].queryset = Party.objects.filter(tenant=tenant)
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=tenant)
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=tenant)
            self.fields["currency"].queryset = Currency.objects.filter(tenant=tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["vendor", "fixed_asset", "operational_asset", "currency"])
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "Contract end date cannot be earlier than start date.")
        return cleaned


class AssetServiceContractRenewForm(forms.Form):
    new_end_date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    new_contract_value = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Renewal terms and remarks..."}),
    )
