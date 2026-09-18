"""Projects 7.14 Client & External Collaboration — ClientApprovalRequest forms.
"""
from apps.core.models.Document import Document
from apps.core.models.Party import Party
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.ClientExternalCollaboration.ClientFeedbacks import ClientApprovalRequest
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ProjectPlanningScheduling.ProjectMilestones import ProjectMilestone


class ClientApprovalRequestForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ClientApprovalRequest
        fields = [
            "project",
            "deliverable_name",
            "document",
            "milestone",
            "assigned_contact",
            "status",
            "due_date",
            "review_notes",
            "client_feedback",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["document"].queryset = Document.objects.filter(
                tenant=self.tenant
            ).order_by("-uploaded_at")
            self.fields["milestone"].queryset = ProjectMilestone.objects.filter(
                tenant=self.tenant
            ).order_by("target_date")
            self.fields["assigned_contact"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "document", "milestone", "assigned_contact"])
        return cleaned
