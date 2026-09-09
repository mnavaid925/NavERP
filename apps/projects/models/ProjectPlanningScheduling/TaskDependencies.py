"""Projects 7.2 — TaskDependency [DEP-]: the sequencing network between work packages.

Bullet 2's row (Task Sequencing & Dependency Mapping): a directed edge from a predecessor work
package to a successor one, typed with the four standard PM link kinds, with ``lag_days``
carrying both lag (positive) and lead (negative) in one column — the bullet explicitly asks for
lag AND lead, and a signed field is the honest shape for "start two days before the predecessor
finishes".

Both endpoints must live in the SAME project (a network is per-project; cross-project
sequencing is program-level, 7.12's), which ``clean()`` enforces. The critical chain these edges
feed is computed on read by ``views._helpers.critical_path_ids`` — never stored.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class TaskDependency(TenantNumbered):
    NUMBER_PREFIX = "DEP"

    LINK_TYPE_CHOICES = [
        ("finish_to_start", "Finish-to-Start"),
        ("start_to_start", "Start-to-Start"),
        ("finish_to_finish", "Finish-to-Finish"),
        ("start_to_finish", "Start-to-Finish"),
    ]

    predecessor = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.CASCADE, related_name="successor_links",
        help_text="The earlier work package the successor waits on.")
    successor = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.CASCADE, related_name="predecessor_links")
    link_type = models.CharField(
        max_length=16, choices=LINK_TYPE_CHOICES, default="finish_to_start")
    lag_days = models.SmallIntegerField(
        default=0, help_text="Days between the linked points — positive = lag, negative = lead.")
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number"), ("tenant", "predecessor", "successor")
        indexes = [
            # The (tenant, predecessor, successor) unique already covers the `tenant, predecessor`
            # prefix; this serves the successor-side lookups (a task's predecessor links).
            models.Index(fields=["tenant", "successor"], name="dep_tnt_succ_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.predecessor} → {self.successor}"

    def clean(self):
        super().clean()
        if self.predecessor_id and self.successor_id:
            if self.predecessor_id == self.successor_id:
                raise ValidationError("A task cannot depend on itself.")
            if (self.predecessor.tenant_id != self.successor.tenant_id
                    or self.predecessor.project_id != self.successor.project_id):
                raise ValidationError(
                    "Both endpoints of a dependency must belong to the same project.")
