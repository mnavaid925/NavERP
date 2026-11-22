from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models import (
    Document,
    DocumentApprovalRequest,
    DocumentSignature,
    DocumentVersion,
)


class DocumentSignatureForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentSignature
        fields = [
            "document",
            "version",
            "approval_request",
            "signer_name",
            "signer_title",
            "signer_email",
            "signature_type",
            "signature_meaning",
            "signature_glyph",
            "certificate_serial",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "version": forms.Select(attrs={"class": "form-select"}),
            "approval_request": forms.Select(attrs={"class": "form-select"}),
            "signer_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Full Legal Name"}),
            "signer_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Corporate / Professional Title"}),
            "signer_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "signer@example.com"}),
            "signature_type": forms.Select(attrs={"class": "form-select"}),
            "signature_meaning": forms.Select(attrs={"class": "form-select"}),
            "signature_glyph": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": "SVG Path or Stylized Base64 Stroke Data"}),
            "certificate_serial": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "X.509 Certificate Thumbprint / Serial"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant).order_by("-created_at")
            self.fields["approval_request"].queryset = DocumentApprovalRequest.objects.filter(tenant=self.tenant).order_by("-created_at")
        self.fields["version"].required = False
        self.fields["approval_request"].required = False
        self.fields["signer_title"].required = False
        self.fields["signer_email"].required = False
        self.fields["signature_glyph"].required = False
        self.fields["certificate_serial"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["document", "version", "approval_request"])
        doc = cleaned.get("document")
        ver = cleaned.get("version")
        if doc and ver and ver.document_id != doc.id:
            self.add_error("version", "Selected version does not belong to this document.")
        return cleaned


class SignatureVerificationForm(forms.Form):
    token = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "Enter 32-character hex verification token / UUID..."}),
        required=True,
    )
