"""Projects 7.2 — ProjectMilestone form.

``actual_date`` is excluded — it is stamped by ``save()`` when the achieve verb fires, never
typed by a hand. ``status`` is excluded too — it is verb-driven governance state that only moves
through the tenant-admin-gated ``mst_achieve`` (with its cancelled/already-achieved guards);
leaving it on the form would let any member achieve a milestone through the ungated edit view
(7.1 precedent: verb-driven status is excluded from the form).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectMilestone


class MilestoneForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectMilestone
        fields = [
            "project", "anchor_task", "name", "description", "target_date", "is_phase_gate",
            "entry_criteria", "exit_criteria",
        ]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "anchor_task"])
        return cleaned
