from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.SecurityAccessControl.DocumentAccessPermissions import DocumentAccessPermission
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document

User = get_user_model()


class DocumentAccessPermissionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentAccessPermission
        fields = [
            "document",
            "folder",
            "grantee_type",
            "user",
            "org_unit",
            "role_name",
            "permission_level",
            "can_read",
            "can_write",
            "can_delete",
            "can_download",
            "can_print",
            "can_share",
            "valid_from",
            "valid_until",
            "is_active",
            "notes",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "folder": forms.Select(attrs={"class": "form-select"}),
            "grantee_type": forms.Select(attrs={"class": "form-select", "id": "id_grantee_type"}),
            "user": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "role_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Legal Counsel, Compliance Auditor"}),
            "permission_level": forms.Select(attrs={"class": "form-select", "id": "id_permission_level"}),
            "can_read": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "can_write": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "can_delete": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "can_download": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "can_print": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "can_share": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "valid_from": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "valid_until": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.TextInput(attrs={"class": "form-input", "placeholder": "Business justification or ticket reference"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["folder"].queryset = DocumentFolder.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["user"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")

        self.fields["document"].required = False
        self.fields["folder"].required = False
        self.fields["user"].required = False
        self.fields["org_unit"].required = False
        self.fields["role_name"].required = False
        self.fields["notes"].required = False
        self.fields["valid_from"].required = False
        self.fields["valid_until"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["document", "folder", "user", "org_unit"])

        doc = cleaned_data.get("document")
        folder = cleaned_data.get("folder")
        if not doc and not folder:
            raise ValidationError("You must specify either a target Document or a target Folder.")

        grantee_type = cleaned_data.get("grantee_type")
        if grantee_type == "user":
            if not cleaned_data.get("user"):
                self.add_error("user", "User must be selected when Grantee Type is 'Specific User'.")
            cleaned_data["org_unit"] = None
            cleaned_data["role_name"] = ""
        elif grantee_type == "org_unit":
            if not cleaned_data.get("org_unit"):
                self.add_error("org_unit", "Organizational Unit must be selected when Grantee Type is 'Org Unit'.")
            cleaned_data["user"] = None
            cleaned_data["role_name"] = ""
        elif grantee_type == "role":
            if not cleaned_data.get("role_name"):
                self.add_error("role_name", "Role Name is required when Grantee Type is 'Role'.")
            cleaned_data["user"] = None
            cleaned_data["org_unit"] = None
        elif grantee_type == "tenant_wide":
            cleaned_data["user"] = None
            cleaned_data["org_unit"] = None
            cleaned_data["role_name"] = ""

        v_from = cleaned_data.get("valid_from")
        v_until = cleaned_data.get("valid_until")
        if v_from and v_until and v_from > v_until:
            self.add_error("valid_until", "Valid Until date must be after Valid From date.")

        return cleaned_data
