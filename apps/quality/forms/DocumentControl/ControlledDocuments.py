from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument

User = get_user_model()


class ControlledDocumentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ControlledDocument
        fields = [
            "title",
            "document_type",
            "department",
            "owner",
            "revision",
            "classification",
            "file",
            "description",
            "change_summary",
            "effective_date",
            "review_interval_months",
            "retention_years",
            "is_template",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Standard Operating Procedure title"}),
            "document_type": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "1.0"}),
            "classification": forms.Select(attrs={"class": "form-select"}),
            "file": forms.FileInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Document scope and purpose..."}),
            "change_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Reason or summary for this revision..."}),
            "effective_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "review_interval_months": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "retention_years": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "is_template": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant)
        else:
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["owner"].queryset = User.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["department", "owner"])
        review_months = cleaned_data.get("review_interval_months")
        if review_months is not None and review_months < 1:
            self.add_error("review_interval_months", "Review interval must be at least 1 month.")
        retention = cleaned_data.get("retention_years")
        if retention is not None and retention < 1:
            self.add_error("retention_years", "Retention period must be at least 1 year.")
        return cleaned_data


class ControlledDocumentRevisionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ControlledDocument
        fields = [
            "revision",
            "change_summary",
            "file",
            "description",
        ]
        widgets = {
            "revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 2.0"}),
            "change_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Detailed justification and summary of revisions..."}),
            "file": forms.FileInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Updated scope or description (optional)..."}),
        }
