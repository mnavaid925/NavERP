"""Projects 7.13 Agile & Scrum Management — SprintRetrospectiveForm.
"""
from django.contrib.auth import get_user_model

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.models.AgileScrumManagement.SprintRetrospectives import (
    SprintRetrospective,
)
from apps.projects.models.AgileScrumManagement.Sprints import Sprint


class SprintRetrospectiveForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SprintRetrospective
        fields = [
            "sprint",
            "conducted_date",
            "conducted_by",
            "status",
            "sentiment_score",
            "what_went_well",
            "what_needs_improvement",
            "action_items",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["sprint"].queryset = Sprint.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            User = get_user_model()
            self.fields["conducted_by"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")
