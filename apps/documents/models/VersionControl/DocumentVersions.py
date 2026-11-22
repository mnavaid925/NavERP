import hashlib

from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class DocumentVersion(TenantNumbered):
    """Immutable snapshot of a document at a specific revision step."""

    NUMBER_PREFIX = "DVER"

    VERSION_TYPE_CHOICES = (
        ("major", "Major Release / Milestone"),
        ("minor", "Minor Revision / Working Draft"),
        ("patch", "Patch / Typo Fix"),
        ("branch_merge", "Branch Merge"),
        ("rollback", "Historical Rollback Restoration"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft Revision"),
        ("pending_review", "Pending Review"),
        ("approved", "Approved"),
        ("superseded", "Superseded"),
        ("archived", "Archived"),
    )

    STATUS_CSS = {
        "draft": "badge-slate",
        "pending_review": "badge-amber",
        "approved": "badge-green",
        "superseded": "badge-red",
        "archived": "badge-muted",
    }

    VERSION_TYPE_CSS = {
        "major": "badge-green",
        "minor": "badge-info",
        "patch": "badge-slate",
        "branch_merge": "badge-info",
        "rollback": "badge-amber",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_label = models.CharField(max_length=32)
    major_number = models.PositiveIntegerField(default=1)
    minor_number = models.PositiveIntegerField(default=0)
    patch_number = models.PositiveIntegerField(default=0)
    version_type = models.CharField(
        max_length=20,
        choices=VERSION_TYPE_CHOICES,
        default="minor",
    )
    file = models.FileField(
        upload_to="documents/versions/%Y/%m/",
        null=True,
        blank=True,
    )
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(default=0)
    file_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 checksum",
    )
    mime_type = models.CharField(max_length=100, blank=True)
    change_summary = models.CharField(max_length=500, blank=True)
    extracted_text = models.TextField(
        blank=True,
        help_text="Text content layer for search and redline diffing",
    )
    is_official = models.BooleanField(default=False, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="approved",
        db_index=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_document_versions",
    )
    branch = models.ForeignKey(
        "documents.DocumentBranch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="versions",
    )
    restored_from_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restorations",
    )

    class Meta:
        ordering = ["-created_at", "-major_number", "-minor_number", "-patch_number"]
        verbose_name = "Document Version"
        verbose_name_plural = "Document Versions"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dver_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "document", "version_label"], name="doc_dver_doc_vlabel_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "document", "is_official"], name="idx_dver_ten_doc_off"),
            models.Index(fields=["tenant", "status"], name="idx_dver_ten_stat"),
        ]

    def __str__(self):
        return f"{self.document.number} v{self.version_label} ({self.number})"

    def save(self, *args, **kwargs):
        if self.file and not self.file_name:
            self.file_name = self.file.name.split("/")[-1]
        if self.file and hasattr(self.file, "size") and not self.file_size:
            self.file_size = self.file.size
        if self.file and not self.file_hash:
            try:
                hasher = hashlib.sha256()
                self.file.seek(0)
                for chunk in self.file.chunks():
                    hasher.update(chunk)
                self.file_hash = hasher.hexdigest()
                self.file.seek(0)
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def version_type_badge_class(self):
        return self.VERSION_TYPE_CSS.get(self.version_type, "badge-slate")
