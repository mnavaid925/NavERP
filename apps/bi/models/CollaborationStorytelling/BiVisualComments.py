from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.bi.models._base import TenantNumbered


class BiVisualComment(TenantNumbered):
    NUMBER_PREFIX = "VCOM"

    TARGET_TYPE_CHOICES = [
        ("dashboard", "Dashboard Canvas"),
        ("widget", "Visual Chart / Card"),
        ("report", "Operational Report"),
        ("story", "Data Story Slide"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_review", "In Review"),
        ("acknowledged", "Acknowledged"),
        ("resolved", "Resolved"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent / Action Required"),
    ]

    target_type = models.CharField(
        max_length=20,
        choices=TARGET_TYPE_CHOICES,
        default="dashboard",
    )

    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comments",
        help_text="Target dashboard canvas for discussion",
    )
    widget = models.ForeignKey(
        "bi.BiDashboardWidget",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comments",
        help_text="Specific chart card or visual metric widget",
    )
    report = models.ForeignKey(
        "bi.ReportDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comments",
        help_text="Target operational report",
    )
    story = models.ForeignKey(
        "bi.BiDataStory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comments",
        help_text="Target data story presentation",
    )
    slide_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Target slide identifier when commenting on a story",
    )

    parent_comment = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
        help_text="Parent comment for threaded conversations",
    )

    content = models.TextField(help_text="Discussion body or visual annotation text")
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="open",
    )
    priority = models.CharField(
        max_length=16,
        choices=PRIORITY_CHOICES,
        default="medium",
    )

    filter_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Contextual filter slice active when comment was recorded",
    )
    coordinate_x = models.FloatField(
        null=True,
        blank=True,
        help_text="X-coordinate percentage (0-100) on visual canvas pin",
    )
    coordinate_y = models.FloatField(
        null=True,
        blank=True,
        help_text="Y-coordinate percentage (0-100) on visual canvas pin",
    )

    mentions_json = models.JSONField(
        default=list,
        blank=True,
        help_text="List of @mentioned user handles or IDs",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_authored_comments",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_resolved_comments",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bi_visual_comment"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_vcom_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_vcom_ten_stat"),
            models.Index(fields=["tenant", "target_type"], name="idx_vcom_ten_type"),
            models.Index(fields=["tenant", "dashboard"], name="idx_vcom_ten_dash"),
            models.Index(fields=["tenant", "story"], name="idx_vcom_ten_story"),
            models.Index(fields=["tenant", "author"], name="idx_vcom_ten_author"),
            models.Index(fields=["tenant", "created_at"], name="idx_vcom_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} ({self.get_target_type_display()}) - {self.status}"

    def mark_resolved(self, user):
        self.status = "resolved"
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save()
