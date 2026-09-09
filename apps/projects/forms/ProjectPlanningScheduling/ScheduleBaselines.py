"""Projects 7.2 — ScheduleBaseline form.

The snapshot columns and ``is_active`` are excluded — they are written by ``freeze_snapshot()``
and the activate/promote verbs, never by a form. ``baseline_type`` stays on the form (create
needs it to choose frozen vs what-if) but is LOCKED on edit: a row's type only moves through the
gated ``bsl_promote`` verb, which snapshots and audits it — editing it by hand would mint an
evidence-less frozen row (7.1 precedent: verb-driven fields are locked on edit).
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
        if self.instance.pk and self.instance.baseline_type != cleaned.get("baseline_type"):
            self.add_error("baseline_type",
                           "A row's type is fixed — promote a what-if scenario instead of "
                           "editing it.")
        return cleaned
