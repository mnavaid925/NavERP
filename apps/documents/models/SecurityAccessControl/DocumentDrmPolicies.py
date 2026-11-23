from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.documents.models._base import TenantNumbered


class DocumentDrmPolicy(TenantNumbered):
    """
    Digital Rights Management (DRM) anti-exfiltration policy, secure viewer controls,
    and emergency document revocation kill-switch.
    """

    NUMBER_PREFIX = "DDRM"

    CLASSIFICATION_CHOICES = (
        ("all", "All Classifications"),
        ("public", "Public"),
        ("internal", "Internal Use Only"),
        ("confidential", "Confidential"),
        ("restricted", "Strictly Restricted"),
    )

    ENCRYPTION_CHOICES = (
        ("AES_256_GCM", "AES-256-GCM (Authenticated)"),
        ("AES_256_CBC", "AES-256-CBC (Standard)"),
        ("CHACHA20_POLY1305", "ChaCha20-Poly1305 (Stream)"),
    )

    CLASSIFICATION_CSS = {
        "all": "badge-slate",
        "public": "badge-green",
        "internal": "badge-info",
        "confidential": "badge-amber",
        "restricted": "badge-red",
    }

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, blank=True)
    description = models.TextField(blank=True)

    # Targeting
    classification = models.CharField(
        max_length=20,
        choices=CLASSIFICATION_CHOICES,
        default="confidential",
    )
    document_type = models.CharField(max_length=40, default="all")
    target_document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="drm_policies",
    )
    target_folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="drm_policies",
    )

    # Exfiltration Prevention Controls
    allow_download = models.BooleanField(default=False)
    allow_print = models.BooleanField(default=False)
    allow_copy_paste = models.BooleanField(default=False)
    screen_shield_enabled = models.BooleanField(default=True)
    secure_viewer_required = models.BooleanField(default=True)
    require_watermark = models.BooleanField(default=True)

    # Perimeter & Temporal Constraints
    max_offline_hours = models.PositiveIntegerField(default=0)
    expiry_days = models.PositiveIntegerField(default=30)
    ip_allowlist = models.TextField(blank=True)
    geo_fencing_countries = models.CharField(max_length=255, blank=True)

    # Kill-Switch Emergency Revocation
    is_revoked = models.BooleanField(default=False, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True)

    # Cryptography
    encryption_standard = models.CharField(
        max_length=30,
        choices=ENCRYPTION_CHOICES,
        default="AES_256_GCM",
    )

    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_drm_policies",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Document DRM Policy"
        verbose_name_plural = "Document DRM Policies"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_ddrm_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="doc_ddrm_tnt_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "is_revoked"], name="doc_ddrm_tnt_act_rvk_idx"),
            models.Index(fields=["tenant", "classification", "is_active"], name="doc_ddrm_tnt_cls_act_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:140] or "drm-policy"
            slug = base_slug
            counter = 1
            while DocumentDrmPolicy.objects.filter(tenant=self.tenant, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def classification_badge(self):
        return self.CLASSIFICATION_CSS.get(self.classification, "badge-slate")

    def revoke(self, user=None, reason=""):
        """Triggers emergency revocation kill switch."""
        self.is_revoked = True
        self.revoked_at = timezone.now()
        self.revocation_reason = reason or "Emergency administrative revocation"
        self.is_active = False
        self.save(update_fields=["is_revoked", "revoked_at", "revocation_reason", "is_active", "updated_at"])
