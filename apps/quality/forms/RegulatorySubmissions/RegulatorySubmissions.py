from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit, Party
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.RegulatorySubmissions.RegulatorySubmissions import RegulatorySubmission

User = get_user_model()


class RegulatorySubmissionForm(TenantModelForm):
    class Meta:
        model = RegulatorySubmission
        fields = [
            "title",
            "submission_type",
            "target_authority",
            "org_unit",
            "product_name",
            "product_code",
            "device_class",
            "application_number",
            "status",
            "planned_submission_date",
            "actual_submission_date",
            "decision_date",
            "lead_author",
            "qa_approver",
            "technical_dossier",
            "technical_sections_summary",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CardioPulse Model X 510(k) Premarket Notification"}),
            "submission_type": forms.Select(attrs={"class": "form-select"}),
            "target_authority": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "product_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CardioPulse Monitor"}),
            "product_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CPM-200"}),
            "device_class": forms.Select(attrs={"class": "form-select"}),
            "application_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. K230145"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "planned_submission_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "actual_submission_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "decision_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "lead_author": forms.Select(attrs={"class": "form-select"}),
            "qa_approver": forms.Select(attrs={"class": "form-select"}),
            "technical_dossier": forms.Select(attrs={"class": "form-select"}),
            "technical_sections_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Summary of GSPR checklist, electrical safety IEC 60601-1, software verification IEC 62304..."}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["target_authority"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["lead_author"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["qa_approver"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["technical_dossier"].queryset = ControlledDocument.objects.filter(
                tenant=self.tenant
            ).order_by("number", "title")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["target_authority", "org_unit", "lead_author", "qa_approver", "technical_dossier"],
        )
        planned = cleaned_data.get("planned_submission_date")
        actual = cleaned_data.get("actual_submission_date")
        decision = cleaned_data.get("decision_date")
        if actual and decision and decision < actual:
            self.add_error("decision_date", "Decision date cannot be prior to actual submission date.")
        return cleaned_data
