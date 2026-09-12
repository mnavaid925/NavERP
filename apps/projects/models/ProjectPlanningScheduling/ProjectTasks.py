"""Projects 7.2 — ProjectTask [TSK-]: the WBS node and the schedulable activity in one row.

One row per node of the project's Work Breakdown Structure. ``node_type`` discriminates the two
kinds the WBS knows: a ``deliverable`` is a summary node whose dates/effort are the ROLLUP of the
work packages beneath it (computed on read in the tree view, never stored), and a
``work_package`` is the schedulable leaf that carries its own planned dates, effort estimate and
estimation method. This is the row NavERP-ERD.md calls ``ProjectTask`` for Module 7 — sub-module
7.8 (Task & Work Management) extends it in place with execution fields rather than declaring a
second task table.

The tree is a plain ``parent`` self-FK (the codebase-wide pattern — OrgUnit, GLAccount,
ItemCategory; no MPTT anywhere). Sibling order is ``sequence``; the hierarchical ``1.2.3`` WBS
code is DERIVED in the tree view from the prefetched tree and never stored.

Scope: 7.2 owns the PLAN — the fields through ``confidence``, the tree and its rollups, the
dependency network and the planning CRUD. No money columns (7.4's), no risk rows (7.5's).

7.8 EXECUTION HAND-OFF — Task & Work Management extends THIS row in place (Ruling 1: no second
task table). It adds the execution fields below (``assignee`` the doer — ``owner`` stays the
accountable manager, team bookings live on 7.3's ResourceAllocation; ``priority``/``moscow``;
the Eisenhower flags; the ``percent_complete`` attestation; and the verb-written
``actual_start``/``actual_end`` stamps, ``editable=False`` so no form can reach them) and the
derived execution properties at the foot of the class (``is_overdue``, ``is_dependency_blocked``,
``is_manually_blocked``, ``is_blocked``, ``checklist_progress``, ``eisenhower_quadrant``) —
every one computed on read, never a stored column. The execution write surface is the separate
``TaskExecutionForm`` plus the POST-only ``tsk_start``/``tsk_complete``/``tsk_block``/
``tsk_unblock``/``tsk_bulk_update`` verbs (views/TaskWorkManagement/ProjectTasks.py); blocking
is DERIVED (Ruling 3) — dependency blocking reads the 7.2 ``TaskDependency`` network over
``predecessor_links``, a real-world blocker is a ``TaskBlock`` evidence row minted only by
``tsk_block``.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models

# Direct sub-module imports of this vertical's sibling entities (the models package re-exports
# land in the Integrate step). Load-bearing, not decorative: importing them here registers both
# models the moment the models package loads, so the reverse relations the derived properties
# read — ``blocks`` (TaskBlock) and ``checklist_items`` (TaskChecklistItem) — exist at runtime.
# Their FKs are string-declared ("projects.ProjectTask"), so this is not an import cycle.
from apps.projects.models.TaskWorkManagement.TaskBlocks import TaskBlock  # noqa: F401
from apps.projects.models.TaskWorkManagement.TaskChecklistItems import (  # noqa: F401
    TaskChecklistItem)


class ProjectTask(TenantNumbered):
    NUMBER_PREFIX = "TSK"

    NODE_TYPE_CHOICES = [
        ("deliverable", "Deliverable"),
        ("work_package", "Work Package"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]
    ESTIMATION_CHOICES = [
        ("bottom_up", "Bottom-Up"),
        ("top_down", "Top-Down"),
        ("analogous", "Analogous"),
        ("parametric", "Parametric"),
    ]
    CONFIDENCE_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]
    # -- 7.8 execution choices (alongside the planning four) -----------------------------------------
    PRIORITY_CHOICES = [
        ("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical"),
    ]
    MOSCOW_CHOICES = [
        ("must_have", "Must Have"), ("should_have", "Should Have"),
        ("could_have", "Could Have"), ("wont_have", "Won't Have"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="tasks")
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children",
        help_text="WBS parent. A node without one roots the tree for its project.")
    node_type = models.CharField(
        max_length=12, choices=NODE_TYPE_CHOICES, default="work_package",
        help_text="Deliverable = summary node rolled up from its children; work package = the "
                  "schedulable leaf.")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="planned_project_tasks")

    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default="planned",
        help_text="Planning status. Execution workflow (assignments, actuals) is 7.8's.")

    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)
    effort_hours = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Estimated effort for this work package.")
    estimation_method = models.CharField(
        max_length=12, choices=ESTIMATION_CHOICES, default="bottom_up")
    confidence = models.CharField(max_length=8, choices=CONFIDENCE_CHOICES, default="medium")

    # -- 7.8 execution fields (the in-place extension; nothing above is altered or reordered) -------
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_project_tasks",
        help_text="The doer. The accountable manager stays owner; team bookings live on "
                  "ResourceAllocation (7.3 staffing).")
    priority = models.CharField(
        max_length=8, choices=PRIORITY_CHOICES, default="medium")
    moscow = models.CharField(
        max_length=12, choices=MOSCOW_CHOICES, null=True, blank=True,
        help_text="MoSCoW classification. No default on purpose — unclassified is a state, "
                  "not a value.")
    is_urgent = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    percent_complete = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Task-grain attestation (0–100). A deliverable's rollup is computed on read, "
                  "never stored; the attested CostControlAccount.percent_complete (7.4) is "
                  "superseded by this figure, not written by it.")
    actual_start = models.DateField(
        null=True, blank=True, editable=False,
        help_text="VERB-WRITTEN by tsk_start only — the 7.4/7.6 verb-written-stamp idiom.")
    actual_end = models.DateField(
        null=True, blank=True, editable=False,
        help_text="VERB-WRITTEN by tsk_complete only (which also stamps percent_complete=100).")

    sequence = models.PositiveSmallIntegerField(
        default=0, help_text="Order among siblings in the WBS.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["project_id", "sequence", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="tsk_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="tsk_tnt_status_idx"),
            models.Index(fields=["tenant", "project", "parent"], name="tsk_tnt_prj_parent_idx"),
            models.Index(fields=["tenant", "node_type"], name="tsk_tnt_ntype_idx"),
            # 7.8 execution lenses (the in-place extension) — the assignee's "my tasks" board
            # filter and the priority-ranked columns.
            models.Index(fields=["tenant", "assignee"], name="tsk_tnt_assignee_idx"),
            models.Index(fields=["tenant", "priority"], name="tsk_tnt_priority_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def duration_days(self):
        """Calendar days inclusive of both ends — derived, never a column."""
        if self.planned_start and self.planned_end:
            return (self.planned_end - self.planned_start).days + 1
        return None

    # -- 7.8 derived execution state (computed on read, never columns — Rulings 3/5) -----------------

    @property
    def is_overdue(self):
        """Past its planned end while still live. False when ``planned_end`` is unset; the clock
        is ``timezone.localdate()`` (L16), never ``date.today()``."""
        if not self.planned_end:
            return False
        return self.planned_end < timezone.localdate() \
            and self.status in ("planned", "in_progress")

    @property
    def is_dependency_blocked(self):
        """DERIVED from 7.2's ``TaskDependency`` network over ``predecessor_links`` — never a
        stored column (Ruling 3: a stored boolean goes stale and has no evidence trail). An
        unfinished FS predecessor holds this task's FINISH; an un-started SS predecessor holds
        its START. FF/SF links never block. Empty links → False."""
        for link in self.predecessor_links.all():
            if link.link_type == "finish_to_start" \
                    and link.predecessor.status not in ("done", "cancelled"):
                return True
            if link.link_type == "start_to_start" and link.predecessor.status == "planned":
                return True
        return False

    @property
    def is_manually_blocked(self):
        """True while a ``TaskBlock`` evidence row stands open — exactly the lookup the
        ``tbk_tnt_unblocked_idx`` serves."""
        return self.blocks.filter(unblocked_at__isnull=True).exists()

    @property
    def is_blocked(self):
        """Either blocker source: the derived dependency state or an open manual block row."""
        return self.is_dependency_blocked or self.is_manually_blocked

    @property
    def checklist_progress(self):
        """Done/total percentage over this task's checklist — ``None`` when there is no
        checklist, else an int 0–100. A computed input to the progress lens, never a column."""
        total = self.checklist_items.count()
        if total == 0:
            return None
        return int(round(self.checklist_items.filter(is_done=True).count() / total * 100))

    @property
    def eisenhower_quadrant(self):
        """Bullet 2's matrix, derived from the two flags — exact lowercase quadrant keys."""
        if self.is_urgent and self.is_important:
            return "do_first"
        if self.is_important:
            return "schedule"
        if self.is_urgent:
            return "delegate"
        return "eliminate"

    def clean(self):
        super().clean()
        if self.planned_start and self.planned_end and self.planned_end < self.planned_start:
            raise ValidationError({"planned_end": "Planned end cannot precede planned start."})
        if self.parent_id and self.project_id \
                and self.parent.project_id != self.project_id:
            raise ValidationError({"parent": "The parent task must belong to the same project "
                                             "as the task."})
