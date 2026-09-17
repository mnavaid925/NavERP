"""Projects 7.13 Agile & Scrum Management — ProjectReleaseForm.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.models.AgileScrumManagement.ProjectReleases import ProjectRelease
from apps.projects.models.ProjectInitiation.Projects import Project


class ProjectReleaseForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectRelease
        fields = [
            "project",
            "name",
            "version_tag",
            "status",
            "release_date",
            "release_notes",
            "feature_flags",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
