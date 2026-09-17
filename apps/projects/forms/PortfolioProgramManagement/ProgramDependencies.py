"""Projects 7.12 Portfolio & Program Management — ProgramDependencyForm.
"""
from django.contrib.auth import get_user_model

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import _reject_foreign
from apps.projects.models.PortfolioProgramManagement.ProgramDependencies import (
    ProgramDependency,
)
from apps.projects.models.PortfolioProgramManagement.Programs import Program
from apps.projects.models.ProjectInitiation.Projects import Project


class ProgramDependencyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProgramDependency
        fields = [
            "source_project",
            "target_project",
            "program",
            "dependency_type",
            "criticality",
            "status",
            "lead_lag_days",
            "description",
            "owner",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["source_project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["target_project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["program"].queryset = Program.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            User = get_user_model()
            self.fields["owner"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["source_project", "target_project", "program"])
        src = cleaned.get("source_project")
        tgt = cleaned.get("target_project")
        if src and tgt and src.id == tgt.id:
            self.add_error("target_project", "A project cannot depend on itself.")
        return cleaned
