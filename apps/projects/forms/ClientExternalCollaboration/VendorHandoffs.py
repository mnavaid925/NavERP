"""Projects 7.14 Client & External Collaboration — VendorHandoff forms.
"""
from apps.core.models.Party import Party
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.ClientExternalCollaboration.VendorHandoffs import VendorHandoff
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ProjectPlanningScheduling.ProjectTasks import ProjectTask


class VendorHandoffForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = VendorHandoff
        fields = [
            "project",
            "vendor",
            "task",
            "title",
            "description",
            "handoff_date",
            "due_date",
            "status",
            "deliverable_link",
            "scorecard_rating",
            "performance_notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["vendor"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["task"].queryset = ProjectTask.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "vendor", "task"])
        handoff = cleaned.get("handoff_date")
        due = cleaned.get("due_date")
        if handoff and due and handoff > due:
            self.add_error("due_date", "Due date must be on or after handoff date.")
        return cleaned
