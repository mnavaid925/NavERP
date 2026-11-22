from django import forms

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.VersionControl.Documents import Document


class DocumentForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            "title",
            "slug",
            "description",
            "document_type",
            "classification",
            "status",
            "versioning_scheme",
            "owner",
            "department",
            "max_versions_retained",
            "tags",
        ]
        exclude = [
            "tenant",
            "number",
            "current_version_label",
            "current_version_no",
            "is_locked",
            "locked_by",
            "locked_at",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Enter document title"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "auto-generated-if-blank"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Summary or purpose of document"}),
            "document_type": forms.Select(attrs={"class": "form-select"}),
            "classification": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "versioning_scheme": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "max_versions_retained": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "tags": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. legal, finance, 2026"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
        self.fields["department"].required = False
        self.fields["slug"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["owner", "department"])
        return cleaned_data
