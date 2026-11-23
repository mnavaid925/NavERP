from django import forms
from django.contrib.auth import get_user_model

from apps.documents.forms._common import TenantModelForm, reject_foreign
from apps.documents.models.CollaborationSharing.CoauthorSessions import CoauthorSession
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


class CoauthorSessionForm(TenantModelForm):
    class Meta:
        model = CoauthorSession
        fields = [
            "document",
            "version",
            "draft",
            "user",
            "guest_name",
            "color_code",
            "status",
            "is_editing",
            "current_section",
        ]
        widgets = {
            "color_code": forms.TextInput(attrs={"type": "color"}),
            "current_section": forms.TextInput(attrs={"placeholder": "e.g. Paragraph 3, Clause 4.2"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant).select_related("document").order_by("-created_at")
            self.fields["draft"].queryset = DocumentDraft.objects.filter(tenant=self.tenant).order_by("title")
            user_model = get_user_model()
            self.fields["user"].queryset = user_model.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "username")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["document", "version", "draft", "user"],
        )
        return cleaned_data
