"""Projects 7.2 — ScheduleBaseline form.

The snapshot columns and ``is_active`` are excluded — they are written by ``freeze_snapshot()``
and the activate/promote verbs, never by a form.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ScheduleBaseline


class BaselineForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ScheduleBaseline
        fields = ["project", "name", "baseline_type", "strategy_note", "note"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project"])
        return cleaned
