"""Projects 7.13 Agile & Scrum Management — SprintForm.
"""
from django.contrib.auth import get_user_model

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.models.AgileScrumManagement.Sprints import Sprint
from apps.projects.models.ProjectInitiation.Projects import Project


class SprintForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Sprint
        fields = [
            "project",
            "name",
            "goal",
            "status",
            "start_date",
            "end_date",
            "scrum_master",
            "standup_notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            User = get_user_model()
            self.fields["scrum_master"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "Sprint end date must be on or after start date.")
        return cleaned
