from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.StorageRepository.DocumentRelationships import DocumentRelationship
from apps.documents.models.VersionControl.Documents import Document


class DocumentRelationshipForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentRelationship
        fields = [
            "source_document",
            "target_document",
            "relationship_type",
            "is_bidirectional",
            "dependency_level",
            "description",
        ]
        widgets = {
            "source_document": forms.Select(attrs={"class": "form-select"}),
            "target_document": forms.Select(attrs={"class": "form-select"}),
            "relationship_type": forms.Select(attrs={"class": "form-select"}),
            "is_bidirectional": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "dependency_level": forms.Select(attrs={"class": "form-select"}),
            "description": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Master agreement incorporates SOW Schedule A"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            docs_qs = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["source_document"].queryset = docs_qs
            self.fields["target_document"].queryset = docs_qs
        self.fields["description"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["source_document", "target_document"])
        source = cleaned.get("source_document")
        target = cleaned.get("target_document")
        if source and target and source.pk == target.pk:
            self.add_error("target_document", "A document cannot create a relationship link to itself.")
        return cleaned
