from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.RecordsManagement.DestructionCertificates import DestructionCertificate
from apps.documents.models.RecordsManagement.RecordDeclarations import RecordDeclaration


class DestructionCertificateForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DestructionCertificate
        fields = [
            "record_declaration",
            "disposition_type",
            "destruction_method",
            "certificate_notes",
        ]
        widgets = {
            "record_declaration": forms.Select(attrs={"class": "form-select"}),
            "disposition_type": forms.Select(attrs={"class": "form-select"}),
            "destruction_method": forms.Select(attrs={"class": "form-select"}),
            "certificate_notes": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "Witness names, disposal facility tracking numbers, or destruction authorization notes...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["record_declaration"].queryset = (
                RecordDeclaration.objects.filter(tenant=self.tenant)
                .exclude(record_status="disposed")
                .select_related("document", "retention_schedule")
                .order_by("-declaration_date")
            )
        else:
            self.fields["record_declaration"].queryset = RecordDeclaration.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["record_declaration"])

        declaration = cleaned_data.get("record_declaration")
        if declaration and declaration.document:
            if declaration.document.legal_holds.filter(is_active=True).exists():
                self.add_error(
                    "record_declaration",
                    "Cannot create a destruction certificate for this record: An active legal hold is currently placed on the document.",
                )

        return cleaned_data
