import json
import secrets
from datetime import timedelta
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class CoauthorSession(TenantNumbered):
    """Active collaborative editing session and presence tracker for documents and drafts."""

    NUMBER_PREFIX = "DCOA"

    STATUS_CHOICES = (
        ("active", "Active Editing"),
        ("idle", "Idle / Inactive"),
        ("disconnected", "Disconnected / Closed"),
    )

    STATUS_CSS = {
        "active": "badge-green",
        "idle": "badge-amber",
        "disconnected": "badge-slate",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="coauthor_sessions",
        db_index=True,
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coauthor_sessions",
        help_text="Active physical document revision being viewed or co-edited",
    )
    draft = models.ForeignKey(
        "documents.DocumentDraft",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coauthor_sessions",
        help_text="Draft document being actively edited in authoring workspace",
    )
    session_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Unique client session identifier token",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coauthor_sessions",
        help_text="Null for external guest collaborator",
    )
    guest_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Display name for external collaborator accessing via link",
    )
    color_code = models.CharField(
        max_length=7,
        default="#3B82F6",
        validators=[RegexValidator(regex=r"^#[0-9A-Fa-f]{6}$", message="Color code must be a valid 6-digit hex color, e.g. #3B82F6")],
        help_text="Hex color code used for collaborator cursor and presence indicator",
    )
    cursor_position = models.TextField(
        blank=True,
        default="{}",
        help_text="JSON payload encoding current page, paragraph/section anchor, and cursor offset",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )
    is_editing = models.BooleanField(
        default=False,
        help_text="True if user is actively typing or holding a section lock",
    )
    current_section = models.CharField(
        max_length=100,
        blank=True,
        help_text="Current section header or block anchor actively occupied",
    )
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_heartbeat = models.DateTimeField(auto_now=True, db_index=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_heartbeat"]
        verbose_name = "Coauthor Session"
        verbose_name_plural = "Coauthor Sessions"
        indexes = [
            models.Index(fields=["tenant", "session_token"], name="doc_dcoa_tnt_tok_idx"),
            models.Index(fields=["tenant", "last_heartbeat"], name="doc_dcoa_tnt_hbt_idx"),
            models.Index(fields=["tenant", "status"], name="doc_dcoa_tnt_sts_idx"),
        ]

    def __str__(self):
        return f"{self.number} ({self.display_name} on {self.document.title})"

    def save(self, *args, **kwargs):
        if not self.session_token:
            self.session_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.guest_name or "Guest Collaborator"

    @property
    def is_timed_out(self):
        if self.status == "disconnected":
            return True
        return (timezone.now() - self.last_heartbeat).total_seconds() > 90

    def get_status_badge(self):
        if self.status != "disconnected" and self.is_timed_out:
            return "badge-amber"
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def heartbeat(self, cursor_data=None, section=None, is_editing=None):
        update_fields = ["last_heartbeat", "updated_at"]
        if self.status != "active":
            self.status = "active"
            update_fields.append("status")
        if cursor_data is not None:
            if isinstance(cursor_data, (dict, list)):
                self.cursor_position = json.dumps(cursor_data)
            else:
                self.cursor_position = str(cursor_data)
            update_fields.append("cursor_position")
        if section is not None:
            self.current_section = section
            update_fields.append("current_section")
        if is_editing is not None:
            self.is_editing = bool(is_editing)
            update_fields.append("is_editing")
        self.save(update_fields=update_fields)

    def disconnect(self):
        self.status = "disconnected"
        self.disconnected_at = timezone.now()
        self.is_editing = False
        self.save(update_fields=["status", "disconnected_at", "is_editing", "updated_at"])
