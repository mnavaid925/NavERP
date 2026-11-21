from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit, Party
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.EhsManagement.HazardousMaterials import HazardousMaterial
from apps.quality.models.EhsManagement.WasteDisposalManifests import WasteDisposalManifest

User = get_user_model()


class WasteDisposalManifestForm(TenantModelForm):
    class Meta:
        model = WasteDisposalManifest
        fields = [
            "manifest_title",
            "regulatory_manifest_id",
            "manifest_type",
            "generator_org_unit",
            "generator_epa_id",
            "accumulation_start_date",
            "waste_description",
            "epa_waste_codes",
            "associated_hazardous_material",
            "physical_state",
            "is_ignitable",
            "is_corrosive",
            "is_reactive",
            "is_toxic",
            "container_type",
            "container_count",
            "quantity_value",
            "quantity_uom",
            "transporter",
            "transporter_epa_id",
            "tsdf_facility",
            "tsdf_epa_id",
            "shipment_date",
            "tsdf_receipt_date",
            "management_method_code",
            "certificate_of_disposal_number",
            "certificate_received_date",
            "discrepancy_details",
            "certifying_officer",
            "notes",
        ]
        widgets = {
            "manifest_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 Solvent and Contaminated Debris Shipment"}),
            "regulatory_manifest_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 012345678JJK (EPA Form 8700-22)"}),
            "manifest_type": forms.Select(attrs={"class": "form-select"}),
            "generator_org_unit": forms.Select(attrs={"class": "form-select"}),
            "generator_epa_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. MAD001234567"}),
            "accumulation_start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "waste_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "e.g. Waste Flammable Liquid, N.O.S. (Acetone, Xylene), 3, UN1993, PG II"}),
            "epa_waste_codes": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. D001, F003"}),
            "associated_hazardous_material": forms.Select(attrs={"class": "form-select"}),
            "physical_state": forms.Select(attrs={"class": "form-select"}),
            "is_ignitable": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_corrosive": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_reactive": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_toxic": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "container_type": forms.Select(attrs={"class": "form-select"}),
            "container_count": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "quantity_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "quantity_uom": forms.Select(attrs={"class": "form-select"}),
            "transporter": forms.Select(attrs={"class": "form-select"}),
            "transporter_epa_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. NJD000123456"}),
            "tsdf_facility": forms.Select(attrs={"class": "form-select"}),
            "tsdf_epa_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CAD000987654"}),
            "shipment_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "tsdf_receipt_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "management_method_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. H040 Incineration"}),
            "certificate_of_disposal_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. COD-2026-9812"}),
            "certificate_received_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "discrepancy_details": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Note any discrepancy in weight, piece count, or container type upon receipt"}),
            "certifying_officer": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["generator_org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["associated_hazardous_material"].queryset = HazardousMaterial.objects.filter(
                tenant=self.tenant
            ).order_by("material_name")
            self.fields["transporter"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["tsdf_facility"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["certifying_officer"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "generator_org_unit",
                "associated_hazardous_material",
                "transporter",
                "tsdf_facility",
                "certifying_officer",
            ],
        )
        return cleaned_data
