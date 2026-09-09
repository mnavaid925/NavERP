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

Scope: 7.2 owns the PLAN. No money columns (7.4's), no actuals/assignments (7.8's), no risk
rows (7.5's).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


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
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def duration_days(self):
        """Calendar days inclusive of both ends — derived, never a column."""
        if self.planned_start and self.planned_end:
            return (self.planned_end - self.planned_start).days + 1
        return None

    def clean(self):
        super().clean()
        if self.planned_start and self.planned_end and self.planned_end < self.planned_start:
            raise ValidationError({"planned_end": "Planned end cannot precede planned start."})
        if self.parent_id and self.project_id \
                and self.parent.project_id != self.project_id:
            raise ValidationError({"parent": "The parent task must belong to the same project "
                                             "as the task."})
