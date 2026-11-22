from django import forms

from apps.accounts.models import User
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


class DocumentVersionForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = DocumentVersion
        fields = [
            "document",
            "version_label",
            "major_number",
            "minor_number",
            "patch_number",
            "version_type",
            "file",
            "file_name",
            "change_summary",
            "extracted_text",
            "is_official",
            "status",
            "author",
            "branch",
        ]
        exclude = [
            "tenant",
            "number",
            "file_size",
            "file_hash",
            "mime_type",
            "restored_from_version",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "version_label": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 1.0, 1.1, 2.0"}),
            "major_number": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "minor_number": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "patch_number": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "version_type": forms.Select(attrs={"class": "form-select"}),
            "file": forms.FileInput(attrs={"class": "form-input"}),
            "file_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Document file name"}),
            "change_summary": forms.TextInput(attrs={"class": "form-input", "placeholder": "Brief change summary"}),
            "extracted_text": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Text layer used for search and diff comparison"}),
            "is_official": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "author": forms.Select(attrs={"class": "form-select"}),
            "branch": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["author"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")
            # DocumentBranch may be empty initially
            from apps.documents.models.VersionControl.DocumentBranches import DocumentBranch
            self.fields["branch"].queryset = DocumentBranch.objects.filter(tenant=self.tenant).order_by("name")
        self.fields["author"].required = False
        self.fields["branch"].required = False
        self.fields["file"].required = False
        self.fields["file_name"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["document", "author", "branch"])
        document = cleaned_data.get("document")
        branch = cleaned_data.get("branch")
        if document and branch and branch.document_id != document.id:
            self.add_error("branch", "The selected branch does not belong to the selected document.")
        return cleaned_data


class VersionCompareForm(forms.Form):
    version_a = forms.ModelChoiceField(
        queryset=DocumentVersion.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Base Version (A)",
    )
    version_b = forms.ModelChoiceField(
        queryset=DocumentVersion.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Comparison Version (B)",
    )

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        document = kwargs.pop("document", None)
        super().__init__(*args, **kwargs)
        if tenant and document:
            qs = DocumentVersion.objects.filter(tenant=tenant, document=document).order_by("-created_at")
            self.fields["version_a"].queryset = qs
            self.fields["version_b"].queryset = qs
