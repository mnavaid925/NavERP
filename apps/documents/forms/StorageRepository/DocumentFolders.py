import json
from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder


class DocumentFolderForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentFolder
        fields = [
            "name",
            "slug",
            "parent",
            "department",
            "owner",
            "color_code",
            "icon_name",
            "default_classification",
            "default_document_type",
            "is_virtual",
            "virtual_criteria_json",
            "is_active",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Legal & Contracts"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "leave blank to auto-generate"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "color_code": forms.TextInput(attrs={"class": "form-input", "type": "color"}),
            "icon_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "folder, briefcase, shield, file-text"}),
            "default_classification": forms.Select(attrs={"class": "form-select"}),
            "default_document_type": forms.Select(attrs={"class": "form-select"}),
            "is_virtual": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "virtual_criteria_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": '{"classification": "confidential", "document_type": "contract"}'}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            folders_qs = DocumentFolder.objects.filter(tenant=self.tenant)
            if self.instance and self.instance.pk:
                folders_qs = folders_qs.exclude(pk=self.instance.pk)
            self.fields["parent"].queryset = folders_qs.order_by("path", "name")
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["owner"].queryset = get_user_model().objects.filter(tenant=self.tenant).order_by("username")
        self.fields["slug"].required = False
        self.fields["parent"].required = False
        self.fields["department"].required = False
        self.fields["description"].required = False
        self.fields["virtual_criteria_json"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["parent", "department", "owner"])
        parent = cleaned.get("parent")
        if parent and self.instance and self.instance.pk:
            if parent.pk == self.instance.pk:
                self.add_error("parent", "A folder cannot be its own parent.")
            # Cycle check: walk ancestor tree
            ancestor = parent
            while ancestor is not None:
                if ancestor.pk == self.instance.pk:
                    self.add_error("parent", "Cyclical folder nesting is prohibited.")
                    break
                ancestor = ancestor.parent

        is_virtual = cleaned.get("is_virtual")
        criteria = cleaned.get("virtual_criteria_json")
        if is_virtual and criteria:
            try:
                parsed = json.loads(criteria)
                if not isinstance(parsed, dict):
                    self.add_error("virtual_criteria_json", "Virtual folder criteria must be a valid JSON dictionary.")
            except (ValueError, TypeError) as exc:
                self.add_error("virtual_criteria_json", f"Invalid JSON criteria: {exc}")
        return cleaned
