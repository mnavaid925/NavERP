import hashlib
import secrets

from django.conf import settings
from django.db import models

from apps.bi.models._base import TenantNumbered


class EmbedApiToken(TenantNumbered):
    NUMBER_PREFIX = "EAPI"

    STATUS_CHOICES = [
        ("active", "Active Token"),
        ("expired", "Expired"),
        ("revoked", "Revoked by Administrator"),
    ]

    name = models.CharField(max_length=200)
    token_prefix = models.CharField(
        max_length=16,
        default="eapi_live_",
        help_text="Visible key identifier prefix (e.g. eapi_live_abc1)",
    )
    token_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of the generated plaintext secret token",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")

    scopes = models.JSONField(
        default=list,
        blank=True,
        help_text="List of granted permission scopes: read:dashboard, read:report, embed:view, query:data",
    )
    embedded_config = models.ForeignKey(
        "bi.EmbeddedAnalyticsConfig",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="api_tokens",
    )
    injected_rls_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Row-Level Security context dictionary: {'department': 'Sales', 'region': 'West'}",
    )
    allowed_ip_ranges = models.TextField(
        blank=True,
        help_text="Optional IP CIDR whitelist or comma-separated IP list",
    )
    rate_limit_rpm = models.PositiveIntegerField(
        default=120,
        help_text="Rate limit in requests per minute",
    )
    expires_at = models.DateTimeField(null=True, blank=True)

    total_requests_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_api_tokens",
    )

    class Meta:
        db_table = "bi_embed_api_token"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_eapi_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "token_prefix"], name="idx_eapi_ten_pfx"),
            models.Index(fields=["tenant", "status"], name="idx_eapi_ten_stat"),
            models.Index(fields=["tenant", "expires_at"], name="idx_eapi_ten_exp"),
            models.Index(fields=["tenant", "created_at"], name="idx_eapi_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.token_prefix}...)"

    @classmethod
    def generate_secret(cls):
        random_bytes = secrets.token_hex(24)
        raw_token = f"eapi_live_{random_bytes}"
        prefix = raw_token[:14]
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        return raw_token, prefix, token_hash

    def verify_token(self, raw_token):
        computed_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        return secrets.compare_digest(self.token_hash, computed_hash)
