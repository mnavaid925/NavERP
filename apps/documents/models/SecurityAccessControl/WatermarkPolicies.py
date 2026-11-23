from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.documents.models._base import TenantNumbered


class WatermarkPolicy(TenantNumbered):
    """
    Dynamic watermarking rules and visual overlay configurations mapped by classification or document type.
    Supports token interpolation: {{user_name}}, {{user_email}}, {{ip_address}}, {{timestamp}}, {{classification}}, {{tenant_name}}.
    """

    NUMBER_PREFIX = "DWTR"

    CLASSIFICATION_CHOICES = (
        ("all", "All Classifications"),
        ("public", "Public"),
        ("internal", "Internal Use Only"),
        ("confidential", "Confidential"),
        ("restricted", "Strictly Restricted"),
    )

    POSITION_CHOICES = (
        ("diagonal_center", "Diagonal Center (-45°)"),
        ("center", "Horizontal Center"),
        ("header_banner", "Top Header Banner"),
        ("footer_banner", "Bottom Footer Banner"),
        ("tiled_grid", "Tiled Watermark Grid"),
    )

    BANNER_POSITION_CHOICES = (
        ("top", "Top Only"),
        ("bottom", "Bottom Only"),
        ("both", "Top and Bottom"),
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
    classification = models.CharField(
        max_length=20,
        choices=CLASSIFICATION_CHOICES,
        default="all",
    )
    document_type = models.CharField(max_length=40, default="all")
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="watermark_policies",
    )
    apply_to_all = models.BooleanField(default=False)

    # Watermark text & styling
    watermark_text = models.CharField(
        max_length=255,
        default="{{classification}} | {{user_name}} | {{timestamp}}",
    )
    secondary_text = models.CharField(max_length=255, blank=True)
    position = models.CharField(
        max_length=20,
        choices=POSITION_CHOICES,
        default="diagonal_center",
    )
    opacity_percent = models.PositiveIntegerField(default=25)
    font_size = models.PositiveIntegerField(default=32)
    font_color = models.CharField(max_length=20, default="#94a3b8")
    rotation_angle = models.IntegerField(default=-45)

    # Banner controls
    show_classification_banner = models.BooleanField(default=True)
    banner_position = models.CharField(
        max_length=20,
        choices=BANNER_POSITION_CHOICES,
        default="top",
    )

    # Enforcement points
    enforce_on_view = models.BooleanField(default=True)
    enforce_on_download = models.BooleanField(default=True)
    enforce_on_print = models.BooleanField(default=True)

    # Priority & Lifecycle
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_watermark_policies",
    )

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "Watermark Policy"
        verbose_name_plural = "Watermark Policies"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dwtr_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="doc_dwtr_tnt_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="doc_dwtr_tnt_act_prio_idx"),
            models.Index(fields=["tenant", "classification", "is_active"], name="doc_dwtr_tnt_cls_act_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.get_classification_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:140] or "watermark-policy"
            slug = base_slug
            counter = 1
            while WatermarkPolicy.objects.filter(tenant=self.tenant, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def classification_badge(self):
        return self.CLASSIFICATION_CSS.get(self.classification, "badge-slate")

    def render_watermark(self, user=None, document=None, ip_address=""):
        """Interpolates dynamic tokens in the watermark text template."""
        text = self.watermark_text
        user_name = (user.get_full_name() or user.username) if user else "Confidential"
        user_email = (user.email or user.username) if user else "user@local"
        classification = (document.get_classification_display().upper() if document and hasattr(document, "get_classification_display") else self.get_classification_display().upper())
        doc_num = document.number if document else "DOC-XXXXX"
        tenant_name = self.tenant.name if self.tenant else "NavERP"
        ts = timezone.now().strftime("%Y-%m-%d %H:%M UTC")

        text = text.replace("{{user_name}}", user_name)
        text = text.replace("{{user_email}}", user_email)
        text = text.replace("{{classification}}", classification)
        text = text.replace("{{document_number}}", doc_num)
        text = text.replace("{{tenant_name}}", tenant_name)
        text = text.replace("{{ip_address}}", ip_address or "127.0.0.1")
        text = text.replace("{{timestamp}}", ts)
        return text
