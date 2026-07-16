"""core — AuditLog models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class AuditLog(models.Model):
    """Append-only record of data/config changes (who / what / when / before→after)."""

    ACTION_CHOICES = [("create", "Create"), ("update", "Update"), ("delete", "Delete")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs", db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.BigIntegerField(null=True, blank=True)
    related = GenericForeignKey("content_type", "object_id")
    target = models.CharField(max_length=255, blank=True)  # human label of the affected object
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    changes = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]
        indexes = [
            models.Index(fields=["tenant", "at"], name="auditlog_tenant_at_idx"),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.target} @ {self.at:%Y-%m-%d %H:%M}"
