from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit, Party
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.EhsManagement.HazardousMaterials import HazardousMaterial

User = get_user_model()


class HazardousMaterialForm(TenantModelForm):
    class Meta:
        model = HazardousMaterial
        fields = [
            "material_name",
            "trade_name",
            "cas_number",
            "un_number",
            "chemical_formula",
            "physical_state",
            "ghs_signal_word",
            "ghs_pictograms",
            "hazard_statements",
            "precautionary_statements",
            "nfpa_health",
            "nfpa_flammability",
            "nfpa_instability",
            "nfpa_special_hazard",
            "sds_revision",
            "sds_issue_date",
            "sds_expiry_date",
            "sds_document",
            "osha_pel",
            "acgih_tlv",
            "exposure_uom",
            "ppe_requirements",
            "incompatible_materials",
            "spill_cleanup_procedure",
            "org_unit",
            "storage_location_code",
            "maximum_storage_quantity",
            "quantity_uom",
            "supplier",
            "status",
            "managed_by",
            "notes",
        ]
        widgets = {
            "material_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Isopropyl Alcohol 99%"}),
            "trade_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. IPA Electronic Grade"}),
            "cas_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 67-63-0"}),
            "un_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. UN1219"}),
            "chemical_formula": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. C3H8O"}),
            "physical_state": forms.Select(attrs={"class": "form-select"}),
            "ghs_signal_word": forms.Select(attrs={"class": "form-select"}),
            "ghs_pictograms": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. flame,exclamation_mark"}),
            "hazard_statements": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "H225: Highly flammable liquid and vapor\nH319: Causes serious eye irritation"}),
            "precautionary_statements": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "P210: Keep away from heat/sparks/open flames\nP280: Wear protective gloves/eye protection"}),
            "nfpa_health": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 4}),
            "nfpa_flammability": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 4}),
            "nfpa_instability": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 4}),
            "nfpa_special_hazard": forms.Select(attrs={"class": "form-select"}),
            "sds_revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Rev 3.1"}),
            "sds_issue_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "sds_expiry_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "sds_document": forms.Select(attrs={"class": "form-select"}),
            "osha_pel": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 400 ppm TWA"}),
            "acgih_tlv": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 200 ppm TWA, 400 ppm STEL"}),
            "exposure_uom": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ppm, mg/m3"}),
            "ppe_requirements": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Nitrile gloves (>= 0.4mm), safety goggles, vapor respirator if ventilation inadequate"}),
            "incompatible_materials": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Strong oxidizers, acetaldehyde, chlorine, isocyanates"}),
            "spill_cleanup_procedure": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Eliminate ignition sources. Absorb with inert absorbent. Ventilate area."}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "storage_location_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Flammable-Cabinet-A1"}),
            "maximum_storage_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "quantity_uom": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. L, kg, gal"}),
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "managed_by": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["sds_document"].queryset = ControlledDocument.objects.filter(
                tenant=self.tenant
            ).order_by("number", "title")
            self.fields["supplier"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["managed_by"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["org_unit", "sds_document", "supplier", "managed_by"])
        return cleaned_data
