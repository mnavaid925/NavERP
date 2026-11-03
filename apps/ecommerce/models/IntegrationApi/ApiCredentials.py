from django.conf import settings
from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class ApiCredential(TenantNumbered):
    NUMBER_PREFIX = "EAPC"

    TIER_CHOICES = [
        ("storefront_public", "Headless Storefront API (Public Access Token)"),
        ("admin_server", "Back-Office Admin API (Server-to-Server Private Key)"),
        ("partner_read", "Partner / Analytics Integration (Read-Only)"),
        ("webhook_receiver", "Inbound Webhook Signature Key"),
    ]

    STATUS_CHOICES = [
        ("active", "Active & Authorized"),
        ("revoked", "Revoked / Disabled"),
        ("expired", "Expired"),
        ("rate_limited", "Temporarily Rate-Limited"),
    ]

    name = models.CharField(
        max_length=255,
        help_text="Application or integration client name e.g. Next.js Headless Web Storefront",
    )
    tier = models.CharField(
        max_length=30,
        choices=TIER_CHOICES,
        default="storefront_public",
        help_text="Security authorization tier and exposure scope",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Authorization lifecycle state",
    )
    client_id = models.CharField(
        max_length=64,
        unique=True,
        help_text="Public API client ID identifier key",
    )
    client_secret_hash = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="SHA-256 hashed secret for server authentication (raw secret never persisted)",
    )
    secret_prefix = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Masked cleartext secret prefix for UI display e.g. nep_live_...",
    )
    scopes = models.CharField(
        max_length=500,
        default="read_catalog,read_orders",
        help_text="Comma-separated permission scopes (e.g. read_catalog,read_orders,write_orders)",
    )
    allowed_origins = models.TextField(
        blank=True,
        default="*",
        help_text="CORS allowed web origins (comma-separated URLs or * for public storefront)",
    )
    allowed_ips = models.TextField(
        blank=True,
        default="",
        help_text="IP CIDR whitelist restriction (one per line, blank for unrestricted)",
    )
    rate_limit_rpm = models.IntegerField(
        default=120,
        help_text="Maximum allowed API requests per minute (RPM)",
    )
    total_requests_count = models.IntegerField(
        default=0,
        help_text="Cumulative number of authenticated API requests processed",
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of most recent authenticated API call",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiration date after which key is rejected",
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when key was explicitly revoked",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Administrative notes regarding consumer app or partner team",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_api_credentials",
        help_text="Administrator who provisioned this API key",
    )

    class Meta:
        db_table = "ecommerce_api_credential"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_eapc_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_eapc_ten_status"),
            models.Index(fields=["tenant", "tier"], name="idx_eapc_ten_tier"),
            models.Index(fields=["client_id"], name="idx_eapc_client_id"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.client_id[:16]}...)"
