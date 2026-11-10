from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
from apps.assets.models.AssetDisposal.AssetScrapSalvages import AssetScrapSalvage
from apps.core.models import Document, Party
from apps.scm.models import Asset as OperationalAsset

User = get_user_model()


class AssetScrapSalvageForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetScrapSalvage
        fields = [
            "disposal_request",
            "fixed_asset",
            "operational_asset",
            "recycler_partner",
            "supervisor",
            "certificate_of_destruction",
            "hazardous_manifest_doc",
            "scrap_method",
            "decommissioning_date",
            "total_scrap_weight_kg",
            "ferrous_weight_kg",
            "non_ferrous_weight_kg",
            "e_waste_weight_kg",
            "salvage_proceeds",
            "dismantling_cost",
            "has_hazardous_materials",
            "hazardous_waste_class",
            "epa_manifest_number",
            "abatement_certified",
            "data_sanitized",
            "sanitization_method",
            "sanitization_verified_by",
            "cod_number",
            "cod_issue_date",
            "cod_issuing_agency",
            "carrier_name",
            "bill_of_lading_number",
            "notes",
        ]
        widgets = {
            "disposal_request": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "recycler_partner": forms.Select(attrs={"class": "form-select"}),
            "supervisor": forms.Select(attrs={"class": "form-select"}),
            "certificate_of_destruction": forms.Select(attrs={"class": "form-select"}),
            "hazardous_manifest_doc": forms.Select(attrs={"class": "form-select"}),
            "scrap_method": forms.Select(attrs={"class": "form-select"}),
            "decommissioning_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "total_scrap_weight_kg": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "ferrous_weight_kg": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "non_ferrous_weight_kg": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "e_waste_weight_kg": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "salvage_proceeds": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "dismantling_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "has_hazardous_materials": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "hazardous_waste_class": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. RCRA D008 (Lead), PCB Class II"}),
            "epa_manifest_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 018472945JJK"}),
            "abatement_certified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "data_sanitized": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "sanitization_method": forms.Select(attrs={"class": "form-select"}),
            "sanitization_verified_by": forms.TextInput(attrs={"class": "form-input", "placeholder": "Auditor Name & Certification ID"}),
            "cod_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. COD-ITAD-2026-904"}),
            "cod_issue_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "cod_issuing_agency": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Sims Lifecycle Services / R2 Certified Recycler"}),
            "carrier_name": forms.TextInput(attrs={"class": "form-input"}),
            "bill_of_lading_number": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Dismantling steps, recovered part serials, hazardous containment notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["disposal_request"].queryset = AssetDisposalRequest.objects.filter(tenant=self.tenant)
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)
            self.fields["recycler_partner"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["supervisor"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            doc_qs = Document.objects.filter(tenant=self.tenant)
            self.fields["certificate_of_destruction"].queryset = doc_qs
            self.fields["hazardous_manifest_doc"].queryset = doc_qs

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "disposal_request",
                "fixed_asset",
                "operational_asset",
                "recycler_partner",
                "supervisor",
                "certificate_of_destruction",
                "hazardous_manifest_doc",
            ],
        )
        dr = cleaned.get("disposal_request")
        fa = cleaned.get("fixed_asset")
        if dr and fa and dr.fixed_asset_id and fa.pk != dr.fixed_asset_id:
            self.add_error("fixed_asset", f"Fixed asset must match the asset linked to disposal request {dr.number} ({dr.fixed_asset}).")
        return cleaned


class AssetScrapAbatementForm(forms.Form):
    hazardous_waste_class = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        required=False,
    )
    epa_manifest_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        required=True,
    )
    abatement_notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Remediation verification notes..."}),
        required=False,
    )


class AssetScrapCertificateForm(forms.Form):
    cod_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        required=True,
    )
    cod_issue_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}),
        required=True,
    )
    cod_issuing_agency = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        required=True,
    )
