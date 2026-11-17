from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class DesignReview(TenantNumbered):
    NUMBER_PREFIX = "QREV"

    REVIEW_STAGE_CHOICES = [
        ("planning", "Design Planning Review"),
        ("concept", "Concept & Feasibility Review"),
        ("input_freeze", "Design Input Freeze Gate"),
        ("detailed_design", "Detailed Architecture / Output Review"),
        ("verification_gate", "Design Verification Gate"),
        ("validation_gate", "Design Validation Gate"),
        ("transfer_gate", "Design Transfer Readiness Gate"),
        ("post_launch", "Post-Launch / Change Review"),
    ]

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("approved", "Approved (Gate Cleared)"),
        ("conditional", "Conditional Approval"),
        ("rejected", "Rejected / Gate Hold"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "scheduled": "badge-slate",
        "in_progress": "badge-info",
        "approved": "badge-green",
        "conditional": "badge-amber",
        "rejected": "badge-red",
        "cancelled": "badge-muted",
    }

    STAGE_CSS = {
        "planning": "badge-slate",
        "concept": "badge-slate",
        "input_freeze": "badge-info",
        "detailed_design": "badge-amber",
        "verification_gate": "badge-info",
        "validation_gate": "badge-green",
        "transfer_gate": "badge-green",
        "post_launch": "badge-muted",
    }

    project = models.ForeignKey("quality.DesignProject", on_delete=models.CASCADE, related_name="reviews")
    title = models.CharField(max_length=255)
    review_stage = models.CharField(max_length=28, choices=REVIEW_STAGE_CHOICES, default="input_freeze", db_index=True)
    review_date = models.DateField()
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="scheduled", db_index=True)
    lead_reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="led_design_reviews")
    independent_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="independent_design_reviews",
        help_text="Independent reviewer with no direct responsibility for the stage per 21 CFR § 820.30(e)",
    )
    agenda = models.TextField(blank=True)
    discussion_summary = models.TextField(blank=True)
    conclusions = models.TextField(blank=True)
    action_items = models.TextField(blank=True, help_text="Assigned action items and required resolutions")
    action_items_resolved = models.BooleanField(default=False)
    electronic_signature = models.ForeignKey(
        "quality.ElectronicSignatureRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="design_reviews",
        help_text="21 CFR Part 11 signature manifest authorizing gate closure",
    )

    class Meta:
        ordering = ["project", "-review_date", "-created_at"]
        verbose_name = "Design Review"
        verbose_name_plural = "Design Reviews"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qrev_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "project"], name="idx_qrev_ten_project"),
            models.Index(fields=["tenant", "review_stage"], name="idx_qrev_ten_stage"),
            models.Index(fields=["tenant", "status"], name="idx_qrev_ten_status"),
        ]

    def __str__(self):
        return f"{self.number} — {self.get_review_stage_display()} ({self.title})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def stage_css(self):
        return self.STAGE_CSS.get(self.review_stage, "badge-slate")

    @property
    def is_cleared(self):
        return self.status == "approved" and (self.action_items_resolved or not self.action_items)
