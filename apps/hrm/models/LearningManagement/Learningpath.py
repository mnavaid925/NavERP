"""HRM 3.23 Learning Management (LMS) — Learningpath models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class LearningPath(TenantNumbered):
    """A role-based learning journey (3.23 Learning Paths) — an ordered curriculum of
    ``TrainingCourse``s (via ``LearningPathItem``) optionally targeted at a ``Designation`` and/or a
    ``core.OrgUnit`` department. Reuses the 3.2 org masters — no new role/department table."""

    NUMBER_PREFIX = "LNP"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name="learning_paths",
                                           help_text="Role this path is aimed at (optional).")
    target_department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="learning_paths", limit_choices_to={"kind": "department"},
                                          help_text="Department this path is aimed at (optional).")
    is_mandatory = models.BooleanField(default=False, help_text="Compliance path (vs. optional development).")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_lnp_tenant_active_idx"),
            models.Index(fields=["tenant", "is_mandatory"], name="hrm_lnp_tenant_mand_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.title}" if self.number else self.title
