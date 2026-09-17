"""Projects 7.13 Agile & Scrum Management — ProjectEpicForm.
"""
from django.contrib.auth import get_user_model

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.models.AgileScrumManagement.ProjectEpics import ProjectEpic
from apps.projects.models.ProjectInitiation.Projects import Project


class ProjectEpicForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectEpic
        fields = [
            "project",
            "name",
            "summary",
            "status",
            "owner",
            "target_start",
            "target_end",
            "color_code",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            User = get_user_model()
            self.fields["owner"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("target_start")
        end = cleaned.get("target_end")
        if start and end and start > end:
            self.add_error("target_end", "Target end date must be on or after target start date.")
        return cleaned
