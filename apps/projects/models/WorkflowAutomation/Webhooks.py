"""Projects 7.17 — ProjectWebhookEndpoint and ProjectWebhookDelivery models.

Integration Automation (iPaaS): outbound event-driven webhooks with HMAC-SHA256 signing and delivery logs.
"""
import hmac
import hashlib
import json
import secrets
from django.db import models

from apps.core.crypto import decrypt, encrypt
from apps.projects.models._base import *


class ProjectWebhookEndpoint(TenantNumbered):
    """Outbound webhook configuration and iPaaS dispatcher for Make, Zapier, and external systems."""

    NUMBER_PREFIX = "PWH"

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="webhook_endpoints",
        help_text="Null implies tenant-wide webhook",
    )
    name = models.CharField(max_length=255)
    target_url = models.URLField(max_length=500)
    secret = models.CharField(
        max_length=512,
        blank=True,
        help_text="Encrypted HMAC signing key via apps.core.crypto",
    )
    is_active = models.BooleanField(default=True)
    event_types = models.JSONField(
        default=list,
        help_text="e.g. ['task.created', 'task.completed', 'milestone.reached', 'gate.approved']",
    )
    custom_headers = models.JSONField(default=dict, blank=True)
    last_status_code = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    last_fired_at = models.DateTimeField(null=True, blank=True, editable=False)
    failure_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = [("tenant", "number")]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="pwh_tnt_act_idx"),
            models.Index(fields=["tenant", "project", "is_active"], name="pwh_tnt_prj_act_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.target_url})"

    def get_secret(self) -> str:
        """Return decrypted HMAC secret or empty string."""
        if not self.secret:
            return ""
        try:
            return decrypt(self.secret)
        except Exception:
            return ""

    def set_secret(self, raw_secret: str):
        """Encrypt and store HMAC secret."""
        if raw_secret:
            self.secret = encrypt(raw_secret)
        else:
            self.secret = ""

    def generate_secret(self) -> str:
        """Generate, encrypt, store, and return a new random 32-byte hex secret."""
        raw = secrets.token_hex(32)
        self.set_secret(raw)
        return raw

    def compute_signature(self, payload_bytes: bytes) -> str:
        """Compute HMAC-SHA256 signature for payload."""
        sec = self.get_secret()
        if not sec:
            return ""
        return hmac.new(sec.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    @property
    def is_active_badge(self):
        return "badge-green" if self.is_active else "badge-slate"

    @property
    def health_badge(self):
        if not self.last_status_code:
            return "badge-slate"
        if 200 <= self.last_status_code < 300:
            return "badge-green"
        if 300 <= self.last_status_code < 400:
            return "badge-info"
        return "badge-red"


class ProjectWebhookDelivery(TenantOwned):
    """Delivery attempt log for an outbound webhook event."""

    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("simulated", "Simulated Ping"),
    ]

    webhook = models.ForeignKey(
        ProjectWebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    signature = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="success")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-attempted_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "webhook", "status"], name="pwh_del_tnt_wh_stat_idx"),
            models.Index(fields=["tenant", "-attempted_at"], name="pwh_del_tnt_att_idx"),
            models.Index(fields=["tenant", "status", "-attempted_at"], name="pwh_del_tnt_stat_att_idx"),
        ]

    def __str__(self):
        return f"Delivery for {self.webhook.number} ({self.status}) at {self.attempted_at}"

    @property
    def status_badge(self):
        badges = {
            "success": "badge-green",
            "failed": "badge-red",
            "simulated": "badge-info",
        }
        return badges.get(self.status, "badge-slate")
