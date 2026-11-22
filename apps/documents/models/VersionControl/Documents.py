from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.documents.models._base import TenantNumbered


class Document(TenantNumbered):
    """Root document entity in the DMS repository representing the logical document container."""

    NUMBER_PREFIX = "DOC"

    DOCUMENT_TYPE_CHOICES = (
        ("general", "General Document"),
        ("contract", "Legal Contract & Agreement"),
        ("policy", "Corporate Policy & Governance"),
        ("sop", "Standard Operating Procedure (SOP)"),
        ("report", "Business & Operational Report"),
        ("specification", "Technical Specification"),
        ("proposal", "Commercial Proposal / Pitch"),
        ("template", "Document Template"),
        ("technical", "Technical & Engineering Doc"),
    )

    CLASSIFICATION_CHOICES = (
        ("public", "Public"),
        ("internal", "Internal Use Only"),
        ("confidential", "Confidential"),
        ("restricted", "Strictly Restricted"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("in_review", "In Review"),
        ("approved", "Approved"),
        ("published", "Published / Official"),
        ("archived", "Archived"),
        ("superseded", "Superseded"),
        ("deprecated", "Deprecated"),
    )

    VERSIONING_SCHEME_CHOICES = (
        ("major_minor", "Major.Minor (e.g. 1.0, 1.1, 2.0)"),
        ("semantic", "Semantic (e.g. 1.0.0, 1.1.0)"),
        ("sequential", "Sequential (e.g. v1, v2, v3)"),
        ("alphanumeric", "Alphanumeric (e.g. Rev A, Rev B)"),
    )

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_review": "badge-amber",
        "approved": "badge-info",
        "published": "badge-green",
        "archived": "badge-muted",
        "superseded": "badge-red",
        "deprecated": "badge-red",
    }

    CLASSIFICATION_CSS = {
        "public": "badge-green",
        "internal": "badge-info",
        "confidential": "badge-amber",
        "restricted": "badge-red",
    }

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    document_type = models.CharField(
        max_length=40,
        choices=DOCUMENT_TYPE_CHOICES,
        default="general",
        db_index=True,
    )
    classification = models.CharField(
        max_length=20,
        choices=CLASSIFICATION_CHOICES,
        default="internal",
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    versioning_scheme = models.CharField(
        max_length=20,
        choices=VERSIONING_SCHEME_CHOICES,
        default="major_minor",
    )
    current_version_label = models.CharField(max_length=32, default="1.0")
    current_version_no = models.PositiveIntegerField(default=1)

    is_locked = models.BooleanField(default=False, db_index=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locked_documents",
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_documents",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    max_versions_retained = models.PositiveIntegerField(
        default=0,
        help_text="0 for unlimited, or max versions kept",
    )
    tags = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dms_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_doc_ten_stat"),
            models.Index(fields=["tenant", "document_type"], name="idx_doc_ten_type"),
            models.Index(fields=["tenant", "is_locked"], name="idx_doc_ten_lock"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} (v{self.current_version_label})"

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            self.slug = slugify(self.title)[:255]
        super().save(*args, **kwargs)

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def classification_badge_class(self):
        return self.CLASSIFICATION_CSS.get(self.classification, "badge-slate")

    @property
    def lock_badge_class(self):
        return "badge-red" if self.is_locked else "badge-slate"

    @property
    def is_checked_out(self):
        return self.is_locked

    @property
    def active_lock(self):
        return self.locks.filter(status="active").first()

    @property
    def version_count(self):
        return self.versions.count()

    @property
    def branch_count(self):
        return self.branches.count()
