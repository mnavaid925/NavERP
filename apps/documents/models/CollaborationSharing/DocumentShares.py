import secrets
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentShare(TenantNumbered):
    """External and internal link-based or recipient-based document sharing control record."""

    NUMBER_PREFIX = "DSHR"

    SHARE_TYPE_CHOICES = (
        ("internal_user", "Specific Internal User"),
        ("internal_dept", "Internal Department / OrgUnit"),
        ("external_email", "Named External Guest"),
        ("public_link", "Public Unguessable Link"),
    )

    ACCESS_LEVEL_CHOICES = (
        ("view_only", "View Only (Preview)"),
        ("comment", "View & Comment / Annotate"),
        ("edit", "Full Co-Authoring & Edit"),
    )

    SHARE_TYPE_CSS = {
        "internal_user": "badge-info",
        "internal_dept": "badge-slate",
        "external_email": "badge-amber",
        "public_link": "badge-green",
    }

    ACCESS_LEVEL_CSS = {
        "view_only": "badge-slate",
        "comment": "badge-info",
        "edit": "badge-green",
    }

    STATUS_CSS = {
        "active": "badge-green",
        "expired": "badge-amber",
        "revoked": "badge-red",
        "exhausted": "badge-muted",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="shares",
        db_index=True,
    )
    folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="shares",
        help_text="Optional repository folder if sharing entire folder structure",
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shares",
        help_text="Optional specific version lock for the shared link",
    )
    share_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Cryptographically secure URL token",
    )
    share_type = models.CharField(
        max_length=20,
        choices=SHARE_TYPE_CHOICES,
        default="public_link",
        db_index=True,
    )
    access_level = models.CharField(
        max_length=20,
        choices=ACCESS_LEVEL_CHOICES,
        default="view_only",
        db_index=True,
    )
    allow_download = models.BooleanField(
        default=True,
        help_text="Allow recipients to download binary file",
    )
    allow_print = models.BooleanField(
        default=True,
        help_text="Allow recipients to print document from browser preview",
    )
    include_annotations = models.BooleanField(
        default=False,
        help_text="Expose internal review annotations and highlights to share recipients",
    )
    password_hash = models.CharField(
        max_length=128,
        blank=True,
        help_text="Cryptographically hashed password protection",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Automatic expiration timestamp",
    )
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum allowed access clicks or downloads before expiry",
    )
    access_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of times this share was accessed",
    )
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_document_shares",
    )
    shared_with_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_document_shares",
    )
    shared_with_email = models.EmailField(
        blank=True,
        help_text="Recipient email for external shares",
    )
    shared_with_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_shares",
    )
    share_message = models.TextField(
        blank=True,
        help_text="Optional message or instructions for recipients",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_document_shares",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document Share"
        verbose_name_plural = "Document Shares"
        indexes = [
            models.Index(fields=["tenant", "share_token"], name="doc_dshr_tnt_tok_idx"),
            models.Index(fields=["tenant", "expires_at"], name="doc_dshr_tnt_exp_idx"),
            models.Index(fields=["tenant", "shared_by"], name="doc_dshr_tnt_usr_idx"),
        ]

    def __str__(self):
        doc_title = self.document.title if self.document_id else "Folder"
        return f"{self.number} ({doc_title} - {self.get_share_type_display()})"

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.share_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def is_exhausted(self):
        return bool(self.max_uses and self.access_count >= self.max_uses)

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired and not self.is_exhausted

    @property
    def has_password(self):
        return bool(self.password_hash)

    @property
    def status_label(self):
        if not self.is_active:
            return "revoked"
        if self.is_expired:
            return "expired"
        if self.is_exhausted:
            return "exhausted"
        return "active"

    def get_status_badge(self):
        return self.STATUS_CSS.get(self.status_label, "badge-slate")

    def get_share_type_badge(self):
        return self.SHARE_TYPE_CSS.get(self.share_type, "badge-slate")

    def get_access_level_badge(self):
        return self.ACCESS_LEVEL_CSS.get(self.access_level, "badge-slate")

    def set_password(self, raw_password):
        if raw_password:
            self.password_hash = make_password(raw_password)
        else:
            self.password_hash = ""

    def check_password(self, raw_password):
        if not self.password_hash:
            return True
        if not raw_password:
            return False
        return check_password(raw_password, self.password_hash)

    def revoke(self, user=None):
        self.is_active = False
        self.revoked_at = timezone.now()
        if user and user.is_authenticated:
            self.revoked_by = user
        self.save(update_fields=["is_active", "revoked_at", "revoked_by", "updated_at"])

    def record_access(self):
        self.access_count += 1
        self.last_accessed_at = timezone.now()
        self.save(update_fields=["access_count", "last_accessed_at", "updated_at"])
