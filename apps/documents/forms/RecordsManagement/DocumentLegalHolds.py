from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models.LegalHold import LegalHold as CoreLegalHold
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.RecordsManagement.DocumentLegalHolds import DocumentLegalHold
from apps.documents.models.VersionControl.Documents import Document

User = get_user_model()


class DocumentLegalHoldForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentLegalHold
        fields = [
            "matter_name",
            "matter_number",
            "hold_reason",
            "description",
            "document",
            "custodian",
            "core_legal_hold",
        ]
        widgets = {
            "matter_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Acme Corp v. Beta Tech Litigation"}),
            "matter_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CV-2026-9042"}),
            "hold_reason": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "document": forms.Select(attrs={"class": "form-select"}),
            "custodian": forms.Select(attrs={"class": "form-select"}),
            "core_legal_hold": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["custodian"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")
            self.fields["core_legal_hold"].queryset = CoreLegalHold.objects.filter(tenant=self.tenant).order_by("name")
        else:
            self.fields["document"].queryset = Document.objects.none()
            self.fields["custodian"].queryset = User.objects.none()
            self.fields["core_legal_hold"].queryset = CoreLegalHold.objects.none()

        self.fields["custodian"].required = False
        self.fields["core_legal_hold"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["document", "custodian", "core_legal_hold"])
        return cleaned_data


class LegalHoldReleaseForm(forms.Form):
    release_justification = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "form-textarea",
            "rows": 4,
            "placeholder": "Document the legal basis and authorization for releasing this hold (e.g. Case settled, matter closed by outside counsel, court order dated...)",
        }),
        required=True,
        help_text="Mandatory audit trail justification required for defensible hold release.",
    )
