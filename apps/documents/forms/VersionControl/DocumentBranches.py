from django import forms

from apps.accounts.models import User
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign, validate_safe_doc_upload
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentBranches import DocumentBranch
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


class DocumentBranchForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = DocumentBranch
        fields = [
            "document",
            "name",
            "description",
            "base_version",
            "branch_type",
            "created_by",
        ]
        exclude = [
            "tenant",
            "number",
            "status",
            "merged_at",
            "merged_by",
            "merged_into_version",
            "merge_strategy",
            "merge_notes",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. eu-variant, draft-v2"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Purpose of branch / what-if scenario"}),
            "base_version": forms.Select(attrs={"class": "form-select"}),
            "branch_type": forms.Select(attrs={"class": "form-select"}),
            "created_by": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["base_version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant).order_by("-created_at")
            self.fields["created_by"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")
        self.fields["description"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["document", "base_version", "created_by"])
        document = cleaned_data.get("document")
        base_version = cleaned_data.get("base_version")
        if document and base_version and base_version.document_id != document.id:
            self.add_error("base_version", "The selected base version does not belong to the selected document.")
        return cleaned_data


class BranchMergeForm(forms.Form):
    merge_strategy = forms.ChoiceField(
        choices=DocumentBranch.MERGE_STRATEGY_CHOICES,
        initial="new_major_version",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Merge Strategy",
    )
    change_summary = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Summary of modifications merged from branch"}),
        label="Merge Version Change Summary *",
    )
    merge_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Review notes, approvals, or merge rationale"}),
        label="Merge Notes & Justification",
    )
    file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-input"}),
        label="Merged Document File Payload",
    )
    extracted_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Merged text content layer"}),
        label="Merged Extracted Text",
    )

    def clean_file(self):
        f = self.cleaned_data.get("file")
        return validate_safe_doc_upload(f)
