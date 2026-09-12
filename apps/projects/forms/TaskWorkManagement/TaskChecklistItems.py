"""Projects 7.8 — TaskChecklistItem forms.

``TaskChecklistItemForm`` carries the checklist row's working data — ``task``, ``label`` and
``sequence``. ``tenant``, ``number``, ``is_done``, ``done_by``, ``done_at`` and ``created_by``
are all OFF it: the tick is the POST-only ``tcl_check`` verb's — ``is_done`` and its
``done_by``/``done_at`` stamps are written exactly once per direction by that verb, so the
evidence trail keeps its timestamps (the 7.4/7.6 verb-written-stamp idiom). ``label`` and
``sequence`` stay editable on done items: a tick item is a working row, not frozen evidence —
only the STAMPS are verb-only.

``TenantUniqueMixin`` is mixed in FIRST (the house idiom): it stamps ``instance.tenant`` before
``full_clean()`` runs on CREATE so the per-tenant ``unique_together`` binds, and ``clean()`` runs
``_reject_foreign`` on ``task`` — a narrowed ``<select>`` is UX, not an authorization boundary,
so the chosen task is re-checked against the form's workspace.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
# Direct sub-module import: the models package re-export lands in the Integrate step.
from apps.projects.models.TaskWorkManagement.TaskChecklistItems import TaskChecklistItem


class TaskChecklistItemForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = TaskChecklistItem
        fields = ["task", "label", "sequence"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["task"])
        return cleaned
