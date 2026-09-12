"""Projects 7.8 — TaskBlock [TBK-]: the evidence row behind a task's manual block.

Realizes bullet **5's blocking half** ("Task Dependencies & Blocking — Predecessor/successor
links, blocked status, and unblock criteria"): dependency blocking is DERIVED from 7.2's
``TaskDependency`` network on ``ProjectTask.is_dependency_blocked`` (Ruling 3 — never a stored
column, a stored boolean goes stale and has no evidence trail), while a real-world blocker gets
ONE of these rows — the reason, the ``unblock_criteria`` that must be met, and the verb-written
stamps that make the trail auditable.

**Evidence-row ruling (verbatim constraint): rows are minted ONLY by the POST-only ``tsk_block``
verb and closed ONLY by the POST-only ``tsk_unblock`` verb — no ``tbk_create``/``tbk_edit``/
``tbk_delete`` routes ship at all, and no ``TaskBlock`` ModelForm exists.** Consequently:

* ``blocked_by``/``blocked_at`` are stamped by ``tsk_block`` exactly once, at minting.
* ``unblocked_by``/``unblocked_at`` and ``resolution_note`` are written EXACTLY ONCE by
  ``tsk_unblock`` — the exit requires a resolution note, so how the criteria were met is part
  of the evidence. ``previous`` (the active state) is captured BEFORE the mutation.
* A row is ACTIVE while ``unblocked_at`` is null (the ``is_active`` property — the
  ``tbk_tnt_unblocked_idx`` serves exactly this lookup via
  ``ProjectTask.is_manually_blocked``). An active block is frozen while it stands; once
  unblocked the row is frozen evidence entirely (the 7.4/7.6 frozen-row idiom).
* ``reason``/``unblock_criteria`` are captured at minting and never edited afterwards.

``is_blocked`` on the task stays DERIVED (Ruling 3) — nothing blocking is stored on the task.

**No money column.** Nothing on a blocker is priced; cost lives on 7.4's registers (L29).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class TaskBlock(TenantNumbered):
    NUMBER_PREFIX = "TBK"

    #: The blocked task. CASCADE — a blocker has no life outside its task (the same idiom every
    #: child row of a parent register uses).
    task = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.CASCADE, related_name="blocks")
    #: Why it is blocked — required at minting (``tsk_block``), frozen thereafter.
    reason = models.TextField()
    #: What must be true to unblock — required at minting (bullet 5's exact ask), so the exit
    #: condition is agreed BEFORE the wait starts, not negotiated during it.
    unblock_criteria = models.TextField()
    #: How the criteria were met — written EXACTLY ONCE by ``tsk_unblock`` (required there).
    resolution_note = models.TextField(blank=True)
    #: The block stamps — ``tsk_block``'s ONLY, written once at minting. SET_NULL so the user's
    #: deletion never orphans the row, and the evidence trail outlives both.
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="task_blocks_raised")
    blocked_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: The unblock stamps — ``tsk_unblock``'s ONLY, written EXACTLY ONCE (unblock-twice is
    #: refused: once ``unblocked_at`` is set the row is closed evidence).
    unblocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="task_blocks_cleared")
    unblocked_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "task"], name="tbk_tnt_task_idx"),
            # Serves the active-block lookup ``unblocked_at__isnull=True`` (the
            # ``ProjectTask.is_manually_blocked`` property reads exactly this).
            models.Index(fields=["tenant", "unblocked_at"], name="tbk_tnt_unblocked_idx"),
        ]

    @property
    def is_active(self):
        """True while the block stands — ``unblocked_at`` is null. Derived, never stored."""
        return self.unblocked_at is None

    def __str__(self):
        return f"{self.number} — {self.task}"
