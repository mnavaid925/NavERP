import os
from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.StorageRepository.DocumentBatchImports import DocumentBatchImport
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume


class DocumentBatchImportForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentBatchImport
        fields = [
            "batch_name",
            "source_type",
            "target_folder",
            "storage_volume",
            "archive_file",
        ]
        widgets = {
            "batch_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 2026 Legal Archive Migration"}),
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "target_folder": forms.Select(attrs={"class": "form-select"}),
            "storage_volume": forms.Select(attrs={"class": "form-select"}),
            "archive_file": forms.FileInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["target_folder"].queryset = DocumentFolder.objects.filter(tenant=self.tenant).order_by("path", "name")
            self.fields["storage_volume"].queryset = StorageVolume.objects.filter(tenant=self.tenant, is_active=True).order_by("name")
        self.fields["target_folder"].required = False
        self.fields["storage_volume"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["target_folder", "storage_volume"])
        archive = cleaned.get("archive_file")
        source_type = cleaned.get("source_type")

        if archive and hasattr(archive, "name"):
            ext = os.path.splitext(archive.name)[1].lower()
            allowed = [".zip", ".tar", ".gz", ".tgz", ".csv", ".json"]
            if ext not in allowed:
                self.add_error("archive_file", f"Unsupported batch import package format '{ext}'. Allowed formats: {', '.join(allowed)}")

        if source_type == "zip_archive" and not archive and not self.instance.archive_file:
            self.add_error("archive_file", "ZIP Archive Package requires an archive file payload.")

        return cleaned
