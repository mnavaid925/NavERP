"""HRM 3.19 Performance Review — Reviewtemplate models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.PerformanceReview.REVIEW_TYPE_CHOICESs import REVIEW_TYPE_CHOICES
from apps.hrm.models.PerformanceReview.REVIEW_TYPE_CHOICESs import REVIEW_TYPE_CHOICES


class ReviewTemplate(TenantNumbered):
    """The review-form definition per participant type (3.19.3/3.19.4). A cycle can attach several
    templates (one per ``review_type``) so the peer form can differ from the manager form."""

    NUMBER_PREFIX = "RVT"

    REVIEW_TYPE_CHOICES = REVIEW_TYPE_CHOICES

    name = models.CharField(max_length=150)
    review_type = models.CharField(max_length=15, choices=REVIEW_TYPE_CHOICES, default="self")
    rating_scale_max = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(2), MaxValueValidator(10)],
        help_text="Top of the rating scale (5-point is the de-facto standard).")
    include_goals = models.BooleanField(
        default=False, help_text="Pull the subject's 3.18 Objectives into a goal-review section.")
    is_anonymous = models.BooleanField(
        default=False, help_text="Default anonymity (peer/360 commonly True); overridable per review.")
    description = models.TextField(blank=True, help_text="Instructions shown to the reviewer.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["review_type", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "review_type"], name="hrm_rvt_tenant_type_idx"),
            models.Index(fields=["tenant", "is_active"], name="hrm_rvt_tenant_active_idx"),
        ]

    @property
    def usage_count(self):
        return self.reviews.count()

    def __str__(self):
        return f"{self.number} · {self.name} ({self.get_review_type_display()})"
