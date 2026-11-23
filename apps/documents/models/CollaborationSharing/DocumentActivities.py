from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentActivity(TenantNumbered):
    """Activity feed event and targeted notification log for document collaboration actions."""

    NUMBER_PREFIX = "DACT"

    ACTION_TYPE_CHOICES = (
        ("document_shared", "Document Shared"),
        ("share_revoked", "Share Link Revoked"),
        ("link_accessed", "Share Link Accessed"),
        ("file_downloaded", "File Downloaded"),
        ("coauthor_joined", "Collaborator Joined Session"),
        ("coauthor_left", "Collaborator Left Session"),
        ("comment_added", "Comment / Annotation Added"),
        ("task_assigned", "Task / Action Item Assigned"),
        ("task_completed", "Task Completed"),
        ("user_mentioned", "User Mentioned in Discussion"),
        ("version_created", "New Version Uploaded"),
    )

    NOTIFICATION_CHANNEL_CHOICES = (
        ("in_app", "In-App Notification"),
        ("email_digest", "Included in Email Digest"),
        ("none", "Silent Activity Log"),
    )

    ACTION_TYPE_CSS = {
        "document_shared": "badge-info",
        "share_revoked": "badge-red",
        "link_accessed": "badge-slate",
        "file_downloaded": "badge-muted",
        "coauthor_joined": "badge-green",
        "coauthor_left": "badge-slate",
        "comment_added": "badge-amber",
        "task_assigned": "badge-info",
        "task_completed": "badge-green",
        "user_mentioned": "badge-amber",
        "version_created": "badge-info",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="collaboration_activities",
        db_index=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_activities",
        help_text="User initiating the action (null if anonymous external guest or system background task)",
    )
    guest_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of external guest actor if action was triggered by link recipient",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_document_activities",
        help_text="Recipient targeted for notification feed or action item assignment",
    )
    action_type = models.CharField(
        max_length=30,
        choices=ACTION_TYPE_CHOICES,
        db_index=True,
    )
    summary = models.CharField(
        max_length=255,
        help_text="Concise human-readable description of event",
    )
    details_json = models.TextField(
        blank=True,
        default="{}",
        help_text="Optional JSON payload with context, metadata, or coordinates",
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Read state for target_user notification inbox",
    )
    read_at = models.DateTimeField(null=True, blank=True)
    notification_channel = models.CharField(
        max_length=20,
        choices=NOTIFICATION_CHANNEL_CHOICES,
        default="in_app",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document Activity"
        verbose_name_plural = "Document Activities"
        indexes = [
            models.Index(fields=["tenant", "target_user", "is_read"], name="doc_dact_tnt_tgt_idx"),
            models.Index(fields=["tenant", "action_type"], name="doc_dact_tnt_act_idx"),
        ]

    def __str__(self):
        return f"{self.number}: {self.get_action_type_display()} on {self.document.title}"

    @property
    def actor_display_name(self):
        if self.actor:
            return self.actor.get_full_name() or self.actor.username
        return self.guest_name or "Guest Collaborator"

    def get_action_type_badge(self):
        return self.ACTION_TYPE_CSS.get(self.action_type, "badge-slate")

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])
