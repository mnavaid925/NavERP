"""Projects 7.13 Agile & Scrum Management — SprintImpedimentForm.
"""
from django.contrib.auth import get_user_model

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.models.AgileScrumManagement.SprintImpediments import (
    SprintImpediment,
)
from apps.projects.models.AgileScrumManagement.Sprints import Sprint


class SprintImpedimentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SprintImpediment
        fields = [
            "sprint",
            "title",
            "description",
            "severity",
            "status",
            "owner",
            "resolution_notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["sprint"].queryset = Sprint.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            User = get_user_model()
            self.fields["owner"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")
