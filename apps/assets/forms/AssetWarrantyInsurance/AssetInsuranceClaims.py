from django import forms

from apps.accounting.models import Currency, FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetIncidentReport
from apps.assets.models.AssetWarrantyInsurance.AssetInsuranceClaims import AssetInsuranceClaim
from apps.assets.models.AssetWarrantyInsurance.AssetInsurancePolicies import AssetInsurancePolicy
from apps.core.models import Document, Party
from apps.scm.models import Asset as OperationalAsset


class AssetInsuranceClaimForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetInsuranceClaim
        fields = [
            "title",
            "policy",
            "fixed_asset",
            "operational_asset",
            "incident_report",
            "incident_date",
            "peril_type",
            "incident_description",
            "incident_location",
            "carrier_claim_number",
            "adjuster_party",
            "adjuster_name",
            "currency",
            "claimed_loss_amount",
            "deductible_applied",
            "salvage_recovery_amount",
            "settlement_method",
            "settlement_notes",
            "proof_of_loss_document",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Electrical Surge Damage on Transformer Substation"}),
            "policy": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "incident_report": forms.Select(attrs={"class": "form-select"}),
            "incident_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "peril_type": forms.Select(attrs={"class": "form-select"}),
            "incident_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Narrative of casualty event, damage scope, immediate stabilization measures..."}),
            "incident_location": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Building B - Main Switchgear Room"}),
            "carrier_claim_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CLM-TRV-2026-00491"}),
            "adjuster_party": forms.Select(attrs={"class": "form-select"}),
            "adjuster_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Sarah Jenkins (Crawford & Co)"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "claimed_loss_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "deductible_applied": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "salvage_recovery_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "settlement_method": forms.Select(attrs={"class": "form-select"}),
            "settlement_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Forensic engineering notes, subrogation remarks, or adjuster remarks..."}),
            "proof_of_loss_document": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["policy"].queryset = AssetInsurancePolicy.objects.filter(tenant=self.tenant)
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)
            self.fields["incident_report"].queryset = AssetIncidentReport.objects.filter(tenant=self.tenant)
            self.fields["adjuster_party"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role="vendor",
            ).distinct()
            self.fields["currency"].queryset = Currency.objects.filter(tenant=self.tenant)
            self.fields["proof_of_loss_document"].queryset = Document.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        claimed = cleaned_data.get("claimed_loss_amount") or 0
        deductible = cleaned_data.get("deductible_applied") or 0
        if deductible > claimed:
            self.add_error("deductible_applied", "Policy deductible cannot exceed gross claimed loss amount.")

        reject_foreign(
            self,
            cleaned_data,
            [
                "policy",
                "fixed_asset",
                "operational_asset",
                "incident_report",
                "adjuster_party",
                "currency",
                "proof_of_loss_document",
            ],
        )
        return cleaned_data
