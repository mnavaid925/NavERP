"""Projects 7.14 Client & External Collaboration — ClientPortalAccess forms.
"""
from django.contrib.auth import get_user_model

from apps.core.models.Party import Party
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.ClientExternalCollaboration.ClientPortals import ClientPortalAccess
from apps.projects.models.ProjectInitiation.Projects import Project


class ClientPortalAccessForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ClientPortalAccess
        fields = [
            "project",
            "client_contact",
            "portal_user",
            "can_view_progress",
            "can_view_milestones",
            "can_view_deliverables",
            "can_view_financials",
            "can_submit_feedback",
            "is_active",
            "expires_at",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["client_contact"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            User = get_user_model()
            self.fields["portal_user"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "client_contact", "portal_user"])
        return cleaned
