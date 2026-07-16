"""HRM 3.23 Learning Management (LMS) — Learningpathitem models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class LearningPathItem(TenantOwned):
    """One ordered ``TrainingCourse`` step in a ``LearningPath`` (3.23 Learning Paths). A CASCADE
    child of the path; the course is PROTECT (a course referenced by a path can't be deleted out from
    under it). Prerequisite gating reuses ``TrainingCourse.prerequisite_course`` (no new rule field)."""

    path = models.ForeignKey("hrm.LearningPath", on_delete=models.CASCADE, related_name="items")
    course = models.ForeignKey("hrm.TrainingCourse", on_delete=models.PROTECT, related_name="path_items")
    sequence = models.PositiveIntegerField(default=0, help_text="Ordered completion position in the path.")
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        ordering = ["path", "sequence"]
        unique_together = ("tenant", "path", "course")
        indexes = [
            models.Index(fields=["tenant", "path"], name="hrm_lpi_tenant_path_idx"),
            models.Index(fields=["tenant", "course"], name="hrm_lpi_tenant_course_idx"),
        ]

    def clean(self):
        # Light-touch prerequisite gating: if this course's prerequisite is ALSO in this path, it must
        # sit at an earlier sequence. If the prerequisite isn't in the path, it's assumed satisfied
        # elsewhere (no hard error) — reuses TrainingCourse.prerequisite_course, no new rule table.
        if self.course_id and self.path_id:
            prereq_id = getattr(self.course, "prerequisite_course_id", None)
            if prereq_id:
                earlier = (LearningPathItem.objects
                           .filter(tenant_id=self.tenant_id, path_id=self.path_id, course_id=prereq_id)
                           .exclude(pk=self.pk).first())
                if earlier is not None and earlier.sequence >= self.sequence:
                    raise ValidationError(
                        {"sequence": "This course's prerequisite must appear earlier in the path."})

    def __str__(self):
        if self.path_id and self.course_id:
            return f"{self.path.title} · {self.sequence}. {self.course.title}"
        return super().__str__()
