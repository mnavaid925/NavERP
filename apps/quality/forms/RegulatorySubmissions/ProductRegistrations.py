from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import Party
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.RegulatorySubmissions.ProductRegistrations import ProductRegistration
from apps.quality.models.RegulatorySubmissions.RegulatorySubmissions import RegulatorySubmission

User = get_user_model()


class ProductRegistrationForm(TenantModelForm):
    class Meta:
        model = ProductRegistration
        fields = [
            "registration_title",
            "registration_type",
            "jurisdiction_country",
            "regulatory_authority",
            "authorized_representative",
            "product_name",
            "product_code",
            "intended_purpose",
            "license_certificate_number",
            "establishment_id",
            "status",
            "initial_approval_date",
            "effective_date",
            "expiration_date",
            "renewal_due_date",
            "renewal_lead_days",
            "regulatory_lead",
            "linked_submission",
            "notes",
        ]
        widgets = {
            "registration_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. US FDA 510(k) Market Clearance — CardioPulse"}),
            "registration_type": forms.Select(attrs={"class": "form-select"}),
            "jurisdiction_country": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. United States, European Union, Japan"}),
            "regulatory_authority": forms.Select(attrs={"class": "form-select"}),
            "authorized_representative": forms.Select(attrs={"class": "form-select"}),
            "product_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CardioPulse Patient Monitor"}),
            "product_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CPM-200"}),
            "intended_purpose": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Continuous monitoring of ECG, SpO2, and non-invasive blood pressure..."}),
            "license_certificate_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 510(k) K230145 / CE 712948"}),
            "establishment_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FEI 3001234567 / SRN DE-MF-000012345"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "initial_approval_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effective_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expiration_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "renewal_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "renewal_lead_days": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "regulatory_lead": forms.Select(attrs={"class": "form-select"}),
            "linked_submission": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["regulatory_authority"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["authorized_representative"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["regulatory_lead"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["linked_submission"].queryset = RegulatorySubmission.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["regulatory_authority", "authorized_representative", "regulatory_lead", "linked_submission"],
        )
        effective = cleaned_data.get("effective_date")
        expiration = cleaned_data.get("expiration_date")
        if effective and expiration and expiration < effective:
            self.add_error("expiration_date", "Expiration date cannot be prior to effective date.")
        return cleaned_data
