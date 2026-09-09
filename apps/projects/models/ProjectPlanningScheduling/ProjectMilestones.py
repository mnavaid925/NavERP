"""Projects 7.2 — ProjectMilestone [MST-]: key decision points and phase gates.

Bullet 4's row (Milestone & Phase-Gate Definition). A milestone pins a DATE that matters; a
milestone with ``is_phase_gate`` is additionally governed — it carries entry/exit criteria, and
the ``mst_achieve`` verb is the gate decision ("exit criteria met, proceed"). ``actual_date`` is
a system stamp, not a form field: ``save()`` writes it the first time the status becomes
``achieved`` and clears it if the row is reopened — you cannot backdate an achievement by hand
any more than you can un-hold a kickoff (the crm.CrmMilestone stamp idiom).

``anchor_task`` optionally ties the milestone to a WBS node (SET_NULL — deleting the task
un-anchors the milestone, it does not delete the milestone).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ProjectMilestone(TenantNumbered):
    NUMBER_PREFIX = "MST"

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_review", "In Review"),
        ("achieved", "Achieved"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="milestones")
    anchor_task = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="milestones",
        help_text="Optional WBS node this milestone lands on.")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_date = models.DateField()
    is_phase_gate = models.BooleanField(
        default=False,
        help_text="A governed decision point — carries entry/exit criteria and a go/no-go.")
    entry_criteria = models.TextField(
        blank=True, help_text="What must be true to enter the gate review.")
    exit_criteria = models.TextField(
        blank=True, help_text="What must be true to pass the gate.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="planned")
    actual_date = models.DateField(null=True, blank=True, editable=False)

    class Meta:
        # Milestones are read as a timeline, so date order IS the useful order here — a
        # deliberate exception to the register's usual newest-first.
        ordering = ["target_date", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="mst_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="mst_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def is_late(self):
        """Target passed without being achieved, and the milestone still live."""
        return (self.status in ("planned", "in_review")
                and self.target_date < timezone.localdate())

    def save(self, *args, **kwargs):
        if self.status == "achieved":
            if self.actual_date is None:
                self.actual_date = timezone.localdate()
        elif self.actual_date is not None:
            # Reopened — the stamp must go with the status it attested.
            self.actual_date = None
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.anchor_task_id and self.project_id \
                and self.anchor_task.project_id != self.project_id:
            raise ValidationError({"anchor_task": "The anchor task must belong to the same "
                                                  "project as the milestone."})
