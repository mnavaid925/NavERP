from django import forms
from django.contrib.auth import get_user_model

from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgment

User = get_user_model()


class DocumentAcknowledgmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentAcknowledgment
        fields = [
            "document",
            "document_revision",
            "user",
            "employee",
            "due_date",
            "notes",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "document_revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 1.0"}),
            "user": forms.Select(attrs={"class": "form-select"}),
            "employee": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Training instructions or compliance notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["document"].queryset = ControlledDocument.objects.filter(
                tenant=self.tenant, lifecycle_state="effective"
            )
            self.fields["user"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["employee"].queryset = EmployeeProfile.objects.filter(
                tenant=self.tenant
            ).select_related("party")
        else:
            self.fields["document"].queryset = ControlledDocument.objects.none()
            self.fields["user"].queryset = User.objects.none()
            self.fields["employee"].queryset = EmployeeProfile.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["document", "user", "employee"])
        return cleaned_data
