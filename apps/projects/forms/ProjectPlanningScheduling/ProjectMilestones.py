"""Projects 7.2 — ProjectMilestone form.

``actual_date`` is excluded — it is stamped by ``save()`` when the achieve verb fires, never
typed by a hand.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectMilestone


class MilestoneForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectMilestone
        fields = [
            "project", "anchor_task", "name", "description", "target_date", "is_phase_gate",
            "entry_criteria", "exit_criteria", "status",
        ]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "anchor_task"])
        return cleaned
