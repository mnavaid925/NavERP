from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.TraceabilitySerialization.DeviceIdentifiers import DeviceIdentifier

User = get_user_model()


class DeviceIdentifierForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DeviceIdentifier
        fields = [
            "device_name",
            "model_number",
            "primary_di",
            "issuing_agency",
            "device_class",
            "basic_udi_di",
            "gudid_status",
            "eudamed_status",
            "brand_name",
            "commercial_distribution_status",
            "catalog_number",
            "barcode_format",
            "is_sterile",
            "contains_latex",
            "is_single_use",
            "mri_safety_status",
            "storage_handling_instructions",
            "fda_listing_number",
            "submission_date",
            "approval_document",
            "regulatory_contact",
            "notes",
        ]
        widgets = {
            "device_name": forms.TextInput(attrs={"class": "form-input"}),
            "model_number": forms.TextInput(attrs={"class": "form-input"}),
            "primary_di": forms.TextInput(attrs={"class": "form-input"}),
            "issuing_agency": forms.Select(attrs={"class": "form-select"}),
            "device_class": forms.Select(attrs={"class": "form-select"}),
            "basic_udi_di": forms.TextInput(attrs={"class": "form-input"}),
            "gudid_status": forms.Select(attrs={"class": "form-select"}),
            "eudamed_status": forms.Select(attrs={"class": "form-select"}),
            "brand_name": forms.TextInput(attrs={"class": "form-input"}),
            "commercial_distribution_status": forms.Select(attrs={"class": "form-select"}),
            "catalog_number": forms.TextInput(attrs={"class": "form-input"}),
            "barcode_format": forms.Select(attrs={"class": "form-select"}),
            "is_sterile": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "contains_latex": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_single_use": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "mri_safety_status": forms.Select(attrs={"class": "form-select"}),
            "storage_handling_instructions": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "fda_listing_number": forms.TextInput(attrs={"class": "form-input"}),
            "submission_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "approval_document": forms.Select(attrs={"class": "form-select"}),
            "regulatory_contact": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["regulatory_contact"].queryset = User.objects.filter(tenant=self.tenant)
            ControlledDocument = apps.get_model("quality", "ControlledDocument")
            self.fields["approval_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["regulatory_contact", "approval_document"])
        return cleaned_data
