"""HRM 3.19 Performance Review — Reviewrating models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class ReviewRating(TenantNumbered):
    """A per-competency/question rating line under a review (3.19.3/3.19.4). ``weight`` mirrors
    ``Objective.weight``/``KeyResult.weight`` so the review's ``overall_rating`` derives as a
    weighted mean rather than a hand-typed duplicate."""

    NUMBER_PREFIX = "RVR"

    CATEGORY_CHOICES = [
        ("competency", "Competency"),
        ("goal", "Goal"),
        ("value", "Company Value"),
        ("custom", "Custom"),
    ]

    review = models.ForeignKey("hrm.PerformanceReview", on_delete=models.CASCADE, related_name="ratings")
    criterion_label = models.CharField(max_length=255, help_text="The competency/question text.")
    criterion_category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default="competency")
    rating_value = models.DecimalField(max_digits=4, decimal_places=2,
                                       help_text="Per-criterion score (within the template's rating scale).")
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)],
                                 help_text="Weight among sibling ratings under the same review (equal-split by default).")
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["review", "-weight", "criterion_label"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "review"], name="hrm_rvr_tenant_review_idx"),
        ]

    def clean(self):
        if self.rating_value is not None and self.rating_value < 0:
            raise ValidationError({"rating_value": "Rating cannot be negative."})
        if (self.rating_value is not None and self.review_id and self.review.template_id
                and self.rating_value > self.review.template.rating_scale_max):
            raise ValidationError(
                {"rating_value": f"Rating cannot exceed the template's scale max ({self.review.template.rating_scale_max})."})
        if self.weight is not None and self.weight < 0:
            raise ValidationError({"weight": "Weight cannot be negative."})

    def __str__(self):
        return f"{self.number} · {self.criterion_label} ({self.rating_value})"
