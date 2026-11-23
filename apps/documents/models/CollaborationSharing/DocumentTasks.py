from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentTask(TenantNumbered):
    """Action item, review assignment, or feedback task attached to a document or comment."""

    NUMBER_PREFIX = "DTSK"

    TASK_TYPE_CHOICES = (
        ("review", "Document Review"),
        ("approval_signoff", "Informal Team Sign-Off"),
        ("revision_requested", "Author Revision Required"),
        ("fact_check", "Fact-Check & Verification"),
        ("redline_review", "Redline / Suggested Edit Review"),
        ("general_todo", "General Action Item"),
    )

    PRIORITY_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent / Immediate"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("overdue", "Overdue"),
    )

    TASK_TYPE_CSS = {
        "review": "badge-info",
        "approval_signoff": "badge-green",
        "revision_requested": "badge-amber",
        "fact_check": "badge-slate",
        "redline_review": "badge-red",
        "general_todo": "badge-muted",
    }

    PRIORITY_CSS = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "urgent": "badge-red",
    }

    STATUS_CSS = {
        "pending": "badge-amber",
        "in_progress": "badge-info",
        "completed": "badge-green",
        "cancelled": "badge-slate",
        "overdue": "badge-red",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="tasks",
        db_index=True,
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
        help_text="Optional physical version to which this task applies",
    )
    review_comment = models.ForeignKey(
        "documents.DocumentReviewComment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_items",
        help_text="Originating review comment or annotation if converted into an action item",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_type = models.CharField(
        max_length=30,
        choices=TASK_TYPE_CHOICES,
        default="review",
        db_index=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="medium",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_document_tasks",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_document_tasks",
    )
    assigned_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_tasks",
        help_text="Optional department or team assignment",
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    reminder_date = models.DateField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_document_tasks",
    )
    completion_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document Task"
        verbose_name_plural = "Document Tasks"
        indexes = [
            models.Index(fields=["tenant", "due_date"], name="doc_dtsk_tnt_due_idx"),
            models.Index(fields=["tenant", "assigned_to"], name="doc_dtsk_tnt_usr_idx"),
        ]

    def __str__(self):
        return f"{self.number}: {self.title} ({self.document.title})"

    @property
    def is_overdue(self):
        if self.status in ("completed", "cancelled"):
            return False
        return bool(self.due_date and self.due_date < timezone.now().date())

    @property
    def effective_status(self):
        if self.is_overdue:
            return "overdue"
        return self.status

    def get_status_badge(self):
        return self.STATUS_CSS.get(self.effective_status, "badge-slate")

    def get_priority_badge(self):
        return self.PRIORITY_CSS.get(self.priority, "badge-slate")

    def get_task_type_badge(self):
        return self.TASK_TYPE_CSS.get(self.task_type, "badge-slate")

    def complete(self, user=None, notes=""):
        self.status = "completed"
        self.completed_at = timezone.now()
        if user and user.is_authenticated:
            self.completed_by = user
        if notes:
            self.completion_notes = notes
        self.save(update_fields=["status", "completed_at", "completed_by", "completion_notes", "updated_at"])

    def reopen(self):
        self.status = "pending"
        self.completed_at = None
        self.completed_by = None
        self.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
