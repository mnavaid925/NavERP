"""Projects 7.14 Client & External Collaboration — ClientPortalAccess [CPA-].

Manages external client access tokens, permission flags, and visibility toggles
(milestones, deliverables, financials, feedback submission).
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.projects.models._base import TenantNumbered


class ClientPortalAccess(TenantNumbered):
    NUMBER_PREFIX = "CPA"

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="client_portal_accesses",
    )
    client_contact = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="project_portal_accesses",
    )
    portal_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_portal_accesses",
    )
    access_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    can_view_progress = models.BooleanField(default=True)
    can_view_milestones = models.BooleanField(default=True)
    can_view_deliverables = models.BooleanField(default=True)
    can_view_financials = models.BooleanField(default=False)
    can_submit_feedback = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"), ("tenant", "project", "client_contact"))
        indexes = [
            models.Index(fields=["tenant", "project"], name="cpa_tnt_project_idx"),
            models.Index(fields=["tenant", "is_active"], name="cpa_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.client_contact.name} ({self.project.name})"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
