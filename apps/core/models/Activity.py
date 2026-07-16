"""core — Activity models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class Activity(models.Model):
    """Generic task / call / email / meeting / note attachable to any record."""

    KIND_CHOICES = [
        ("task", "Task"),
        ("call", "Call"),
        ("email", "Email"),
        ("meeting", "Meeting"),
        ("note", "Note"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="activities", db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="task")
    subject = models.CharField(max_length=255)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.BigIntegerField(null=True, blank=True)
    related = GenericForeignKey("content_type", "object_id")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-due_at", "-created_at"]
        verbose_name_plural = "activities"
        indexes = [
            models.Index(fields=["tenant", "status"], name="activity_tenant_status_idx"),
            models.Index(fields=["tenant", "owner"], name="activity_tenant_owner_idx"),
        ]

    def __str__(self):
        return self.subject
