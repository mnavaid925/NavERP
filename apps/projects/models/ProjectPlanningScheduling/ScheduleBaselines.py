"""Projects 7.2 — ScheduleBaseline [BSL-]: the frozen schedule and its what-if variants.

Bullet 5's row (Schedule Baseline & Version Control). A ``baseline``-typed row is FROZEN — its
edit and delete views refuse it, because a baseline that could be quietly rewritten would not be
a baseline. A ``what_if`` row is the working copy for schedule-compression experiments
(fast-tracking/crashing, in ``strategy_note``); ``bsl_promote`` freezes it in place of the live
one. The ``ProjectKickoff.baseline_acknowledged_*`` stamps from 7.1 attest to THIS row: the
active baseline of the project.

The snapshot columns (``planned_finish`` / ``task_count`` / ``total_effort_hours``) are
freeze-time evidence, deliberately stored rather than derived: a frozen baseline that
recomputed itself under the live plan would not be frozen. Task-level snapshots are a future
extension — 7.2 freezes summary figures only.

``is_active`` marks the one baseline a project is managed against. Enforced by the verbs inside
``transaction.atomic()`` (deactivate all, activate one) and NOT by a conditional unique
constraint — MySQL/MariaDB cannot enforce a partial unique index, and a constraint Django
silently declines to create would be a lie in the schema.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ScheduleBaseline(TenantNumbered):
    NUMBER_PREFIX = "BSL"

    BASELINE_TYPE_CHOICES = [
        ("baseline", "Frozen Baseline"),
        ("what_if", "What-If Scenario"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="schedule_baselines")
    name = models.CharField(max_length=255)
    baseline_type = models.CharField(
        max_length=8, choices=BASELINE_TYPE_CHOICES, default="baseline")
    is_active = models.BooleanField(
        default=False,
        help_text="The baseline this project is managed against. Exactly one per project — "
                  "the activate/promote verbs keep it that way atomically.")
    frozen_on = models.DateField(null=True, blank=True, editable=False)
    planned_finish = models.DateField(null=True, blank=True, editable=False)
    task_count = models.PositiveIntegerField(null=True, blank=True, editable=False)
    total_effort_hours = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, editable=False)
    strategy_note = models.TextField(
        blank=True, help_text="Schedule compression applied — fast-tracking, crashing.")
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="bsl_tnt_project_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def is_frozen(self):
        return self.baseline_type == "baseline"

    def freeze_snapshot(self):
        """Copy the project's live plan into the snapshot columns, and stamp the freeze date.

        Called by the create view (when the row is born a baseline) and by ``bsl_promote``
        BEFORE ``save()``. ONE aggregate over the project's tasks — no full-row load. Undated
        tasks count toward ``task_count`` but contribute nothing to the finish (``Max`` skips
        NULLs, and an all-undated plan snapshots a NULL finish); ``effort`` is q2-clamped like
        every money-shaped decimal in this app.
        """
        row = self.project.tasks.aggregate(
            finish=Max("planned_end"), n=Count("pk"), effort=Sum("effort_hours"))
        self.planned_finish = row["finish"]
        self.task_count = row["n"]
        self.total_effort_hours = q2(row["effort"] or ZERO)
        self.frozen_on = timezone.localdate()
