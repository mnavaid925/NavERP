from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class EmbeddedAnalyticsConfig(TenantNumbered):
    NUMBER_PREFIX = "EMB"

    TARGET_TYPE_CHOICES = [
        ("dashboard", "Interactive Dashboard"),
        ("report", "Operational Report"),
        ("semantic_model", "Semantic Data Model"),
    ]

    EMBEDDING_MODE_CHOICES = [
        ("iframe", "Sandboxed Iframe"),
        ("web_component", "Web Component SDK (<nav-bi-embed>)"),
        ("headless_api", "Headless JSON Data API"),
    ]

    AUTH_MODE_CHOICES = [
        ("public_token", "Public Kiosk / Embed Token"),
        ("signed_jwt", "Signed HMAC-SHA256 Token"),
        ("sso_passthrough", "Enterprise SSO Passthrough"),
    ]

    THEME_MODE_CHOICES = [
        ("light", "Light Theme"),
        ("dark", "Dark Theme"),
        ("auto", "Inherit Host Application"),
        ("custom", "Custom CSS Styling"),
    ]

    STATUS_CHOICES = [
        ("active", "Active & Serving"),
        ("paused", "Temporarily Paused"),
        ("revoked", "Revoked / Disabled"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    description = models.TextField(blank=True)
    target_type = models.CharField(max_length=24, choices=TARGET_TYPE_CHOICES, default="dashboard")

    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="embedded_configs",
    )
    report = models.ForeignKey(
        "bi.ReportDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="embedded_configs",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="embedded_configs",
    )

    embedding_mode = models.CharField(max_length=24, choices=EMBEDDING_MODE_CHOICES, default="iframe")
    auth_mode = models.CharField(max_length=24, choices=AUTH_MODE_CHOICES, default="signed_jwt")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")

    allowed_origins = models.TextField(
        blank=True,
        default="*",
        help_text="Allowed domains for CORS/frame-ancestors (* or comma-separated origins)",
    )
    theme_mode = models.CharField(max_length=16, choices=THEME_MODE_CHOICES, default="light")
    primary_color = models.CharField(max_length=20, default="#1e40af")
    accent_color = models.CharField(max_length=20, default="#3b82f6")
    custom_css = models.TextField(blank=True, help_text="Custom CSS injected into white-labeled container")

    enable_rls_filter = models.BooleanField(
        default=True,
        help_text="Enforce Row-Level Security attribute filtering on queries",
    )
    default_rls_attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Default dimension/attribute filters in JSON format",
    )

    view_count = models.PositiveIntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_embedded_configs",
    )

    class Meta:
        db_table = "bi_embedded_analytics_config"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_emb_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_emb_tenant_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_emb_ten_stat"),
            models.Index(fields=["tenant", "target_type"], name="idx_emb_ten_target"),
            models.Index(fields=["tenant", "embedding_mode"], name="idx_emb_ten_mode"),
            models.Index(fields=["tenant", "created_at"], name="idx_emb_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_target_type_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "embed-config"
            slug = base_slug
            counter = 1
            while EmbeddedAnalyticsConfig.objects.filter(tenant=self.tenant, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
