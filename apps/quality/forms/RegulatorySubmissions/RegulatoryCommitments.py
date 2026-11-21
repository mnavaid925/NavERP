from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import Party
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.AuditManagement.RegulatoryInspectionHosts import RegulatoryInspectionHost
from apps.quality.models.RegulatorySubmissions.ProductRegistrations import ProductRegistration
from apps.quality.models.RegulatorySubmissions.RegulatoryCommitments import RegulatoryCommitment
from apps.quality.models.RegulatorySubmissions.RegulatorySubmissions import RegulatorySubmission

User = get_user_model()


class RegulatoryCommitmentForm(TenantModelForm):
    class Meta:
        model = RegulatoryCommitment
        fields = [
            "title",
            "commitment_type",
            "regulatory_agency",
            "linked_submission",
            "linked_registration",
            "linked_inspection",
            "agency_reference_number",
            "correspondence_date",
            "commitment_description",
            "responsible_owner",
            "due_date",
            "completion_date",
            "status",
            "verification_method",
            "agency_feedback",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FDA AI Response: Biocompatibility Cytotoxicity Protocol"}),
            "commitment_type": forms.Select(attrs={"class": "form-select"}),
            "regulatory_agency": forms.Select(attrs={"class": "form-select"}),
            "linked_submission": forms.Select(attrs={"class": "form-select"}),
            "linked_registration": forms.Select(attrs={"class": "form-select"}),
            "linked_inspection": forms.Select(attrs={"class": "form-select"}),
            "agency_reference_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FDA Deficiency Item 4 / 483 Obs 2"}),
            "correspondence_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "commitment_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Formal commitment details, protocol commitments, agency questions..."}),
            "responsible_owner": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "completion_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "verification_method": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Evidence protocol, bench test report, updated labeling..."}),
            "agency_feedback": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Official response from agency, acceptance confirmation..."}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["regulatory_agency"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["linked_submission"].queryset = RegulatorySubmission.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["linked_registration"].queryset = ProductRegistration.objects.filter(
                tenant=self.tenant
            ).order_by("product_name")
            self.fields["linked_inspection"].queryset = RegulatoryInspectionHost.objects.filter(
                tenant=self.tenant
            ).order_by("-scheduled_start_date")
            self.fields["responsible_owner"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["regulatory_agency", "linked_submission", "linked_registration", "linked_inspection", "responsible_owner"],
        )
        corr_date = cleaned_data.get("correspondence_date")
        comp_date = cleaned_data.get("completion_date")
        if corr_date and comp_date and comp_date < corr_date:
            self.add_error("completion_date", "Completion date cannot be prior to agency correspondence date.")
        return cleaned_data
