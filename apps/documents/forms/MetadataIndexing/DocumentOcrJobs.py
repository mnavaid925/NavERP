from django import forms
from django.core.exceptions import ValidationError

from apps.documents.models import Document, DocumentOcrJob, DocumentVersion


class DocumentOcrJobForm(forms.ModelForm):
    class Meta:
        model = DocumentOcrJob
        fields = [
            "document",
            "version",
            "ocr_engine",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "version": forms.Select(attrs={"class": "form-select"}),
            "ocr_engine": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant)
            self.fields["version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant)
        else:
            self.fields["document"].queryset = Document.objects.none()
            self.fields["version"].queryset = DocumentVersion.objects.none()

        self.fields["version"].empty_label = "— Latest Document Version —"

    def clean(self):
        cleaned_data = super().clean()
        doc = cleaned_data.get("document")
        if doc and self.tenant and doc.tenant != self.tenant:
            raise ValidationError("Selected document does not belong to your organization.")
        ver = cleaned_data.get("version")
        if ver and doc and ver.document != doc:
            raise ValidationError("Selected revision version does not belong to the selected document.")
        return cleaned_data
