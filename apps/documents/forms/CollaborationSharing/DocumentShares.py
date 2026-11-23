from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantModelForm, reject_foreign
from apps.documents.models.CollaborationSharing.DocumentShares import DocumentShare
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


class DocumentShareForm(TenantModelForm):
    raw_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Optional password protection", "autocomplete": "new-password"}),
        help_text="Leave blank to maintain current password or allow password-free access",
    )

    class Meta:
        model = DocumentShare
        fields = [
            "document",
            "folder",
            "version",
            "share_type",
            "access_level",
            "shared_with_user",
            "shared_with_email",
            "shared_with_org_unit",
            "expires_at",
            "max_uses",
            "allow_download",
            "allow_print",
            "include_annotations",
            "share_message",
        ]
        widgets = {
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "share_message": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional message or notes for recipients"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["folder"].queryset = DocumentFolder.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant).select_related("document").order_by("-created_at")
            
            user_model = get_user_model()
            self.fields["shared_with_user"].queryset = user_model.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "username")
            self.fields["shared_with_org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["document", "folder", "version", "shared_with_user", "shared_with_org_unit"],
        )

        share_type = cleaned_data.get("share_type")
        if share_type == "internal_user" and not cleaned_data.get("shared_with_user"):
            self.add_error("shared_with_user", "Please select the internal user to share with.")
        elif share_type == "internal_dept" and not cleaned_data.get("shared_with_org_unit"):
            self.add_error("shared_with_org_unit", "Please select the internal department to share with.")
        elif share_type == "external_email" and not cleaned_data.get("shared_with_email"):
            self.add_error("shared_with_email", "Please specify the recipient email address for external sharing.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk and self.user and self.user.is_authenticated:
            instance.shared_by = self.user

        raw_password = self.cleaned_data.get("raw_password")
        if raw_password:
            instance.set_password(raw_password)

        if commit:
            instance.save()
            self.save_m2m()
        return instance
