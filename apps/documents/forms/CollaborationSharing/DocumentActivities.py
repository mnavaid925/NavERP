from django import forms
from django.contrib.auth import get_user_model

from apps.documents.forms._common import TenantModelForm, reject_foreign
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.models.VersionControl.Documents import Document


class DocumentActivityForm(TenantModelForm):
    class Meta:
        model = DocumentActivity
        fields = [
            "document",
            "actor",
            "guest_name",
            "target_user",
            "action_type",
            "summary",
            "notification_channel",
        ]
        widgets = {
            "summary": forms.TextInput(attrs={"placeholder": "e.g. Shared contract with external counsel"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            user_model = get_user_model()
            self.fields["actor"].queryset = user_model.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "username")
            self.fields["target_user"].queryset = user_model.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "username")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["document", "actor", "target_user"],
        )
        return cleaned_data
