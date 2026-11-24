from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.RecordsManagement.RecordDeclarations import RecordDeclaration
from apps.documents.models.RecordsManagement.RetentionSchedules import RetentionSchedule
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


class RecordDeclarationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RecordDeclaration
        fields = [
            "document",
            "version",
            "retention_schedule",
            "declaration_mode",
            "is_vital_record",
            "vital_review_frequency_months",
            "notes",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "version": forms.Select(attrs={"class": "form-select"}),
            "retention_schedule": forms.Select(attrs={"class": "form-select"}),
            "declaration_mode": forms.Select(attrs={"class": "form-select"}),
            "is_vital_record": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "vital_review_frequency_months": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["retention_schedule"].queryset = RetentionSchedule.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("code")
            if self.instance and self.instance.pk and self.instance.document_id:
                self.fields["version"].queryset = (
                    DocumentVersion.objects.filter(tenant=self.tenant, document_id=self.instance.document_id)
                    .select_related("document")
                    .order_by("-major_number", "-minor_number", "-patch_number")
                )
            else:
                self.fields["version"].queryset = (
                    DocumentVersion.objects.filter(tenant=self.tenant)
                    .select_related("document")
                    .order_by("-created_at")
                )
        else:
            self.fields["document"].queryset = Document.objects.none()
            self.fields["version"].queryset = DocumentVersion.objects.none()
            self.fields["retention_schedule"].queryset = RetentionSchedule.objects.none()

        self.fields["version"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["document", "version", "retention_schedule"])

        document = cleaned_data.get("document")
        version = cleaned_data.get("version")
        retention_schedule = cleaned_data.get("retention_schedule")

        if self.instance and self.instance.pk:
            if document and document != self.instance.document:
                self.add_error("document", "Cannot change document on an existing record declaration.")
            if version and version != self.instance.version:
                self.add_error("version", "Cannot change version on an existing record declaration.")
            if retention_schedule and retention_schedule != self.instance.retention_schedule:
                self.add_error("retention_schedule", "Cannot change retention schedule on an existing record declaration.")
        else:
            if document and self.tenant:
                existing_active = (
                    RecordDeclaration.objects.filter(tenant=self.tenant, document=document)
                    .exclude(record_status="disposed")
                    .exists()
                )
                if existing_active:
                    self.add_error("document", "An active record declaration already exists for this document.")

        if document and version:
            if version.document_id != document.id:
                self.add_error("version", "The selected version does not belong to the chosen document.")

        return cleaned_data
