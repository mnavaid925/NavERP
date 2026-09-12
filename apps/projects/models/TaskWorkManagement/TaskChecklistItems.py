"""Projects 7.8 — TaskChecklistItem [TCL-]: one tick item inside a task's checklist.

Realizes bullet **1's checklists** ("Individual and team tasks, sub-tasks, checklists, and bulk
operations") and feeds ``ProjectTask.checklist_progress`` — the per-task done/total percentage is
computed on read there, never a stored column, and it is this table that makes it possible: a
TextField could not carry one-time done-stamps per row.

**The tick is verb-written, exactly once per direction.** ``is_done``, ``done_by`` and
``done_at`` are OFF the model form and OFF every generic writer: the POST-only ``tcl_check``
verb is their ONLY writer — open → done stamps all three together, done → open clears all
three (the un-tick goes through the SAME verb + audit — one writer per direction), with
``previous`` captured BEFORE the mutation (the 7.4/7.6 verb-written-stamp idiom).

**A tick item is a working row, not frozen evidence.** ``label`` and ``sequence`` stay editable
on done items — only the STAMPS are verb-only; there is no lock state on this row.

**No money column.** Nothing on a checklist item is priced; cost lives on 7.4's registers (L29).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class TaskChecklistItem(TenantNumbered):
    NUMBER_PREFIX = "TCL"

    #: The task whose checklist this row belongs to. CASCADE — a checklist item has no life
    #: outside its task (the same idiom every child row of a parent register uses).
    task = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.CASCADE, related_name="checklist_items")
    label = models.CharField(max_length=255)
    #: Order within the task's checklist. Defaults to 0 — with the ``id`` tiebreak in Meta.ordering
    #: a never-sequenced checklist still reads in append order.
    sequence = models.PositiveSmallIntegerField(default=0)
    #: VERB-WRITTEN by ``tcl_check`` ONLY — stamped exactly once per direction, never on a form.
    is_done = models.BooleanField(default=False)
    #: The done stamps — ``tcl_check``'s ONLY. SET_NULL so un-ticking (or the user's deletion)
    #: never orphans the row, and the audit trail outlives both.
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="checked_task_checklist_items")
    done_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["task_id", "sequence", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "task"], name="tcl_tnt_task_idx"),
            models.Index(fields=["tenant", "is_done"], name="tcl_tnt_done_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.label}"
