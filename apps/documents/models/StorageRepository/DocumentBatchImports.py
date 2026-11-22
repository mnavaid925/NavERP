from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class DocumentBatchImport(TenantNumbered):
    """High-volume bulk ingestion, ZIP archive unpacking, and legacy migration session manager."""

    NUMBER_PREFIX = "DBLK"

    SOURCE_TYPE_CHOICES = (
        ("zip_archive", "ZIP Archive Package"),
        ("file_manifest", "Manifest CSV + Files"),
        ("multi_file", "Direct Multi-File Staging"),
        ("legacy_migration", "Legacy ECM Migration Export"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft Definition"),
        ("queued", "Queued for Ingestion"),
        ("extracting", "Extracting Archive"),
        ("validating", "Validating Files & Formats"),
        ("processing", "Ingesting into Repository"),
        ("completed", "Successfully Ingested"),
        ("partially_completed", "Completed with Warnings / Failures"),
        ("failed", "Ingestion Failed"),
    )

    SOURCE_TYPE_CSS = {
        "zip_archive": "badge-info",
        "file_manifest": "badge-amber",
        "multi_file": "badge-slate",
        "legacy_migration": "badge-green",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "queued": "badge-slate",
        "extracting": "badge-amber",
        "validating": "badge-amber",
        "processing": "badge-info",
        "completed": "badge-green",
        "partially_completed": "badge-amber",
        "failed": "badge-red",
    }

    batch_name = models.CharField(max_length=150)
    source_type = models.CharField(
        max_length=25,
        choices=SOURCE_TYPE_CHOICES,
        default="zip_archive",
        db_index=True,
    )
    target_folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_imports",
    )
    storage_volume = models.ForeignKey(
        "documents.StorageVolume",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_imports",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    archive_file = models.FileField(
        upload_to="documents/bulk_imports/%Y/%m/",
        null=True,
        blank=True,
    )
    total_files_detected = models.PositiveIntegerField(default=0)
    processed_files_count = models.PositiveIntegerField(default=0)
    success_files_count = models.PositiveIntegerField(default=0)
    failed_files_count = models.PositiveIntegerField(default=0)
    total_bytes_processed = models.BigIntegerField(default=0)
    log_summary = models.TextField(blank=True)
    error_details = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_document_batch_imports",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document Batch Import"
        verbose_name_plural = "Document Batch Imports"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dblk_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "created_at"], name="doc_dblk_tnt_stat_date_idx"),
            models.Index(fields=["tenant", "target_folder", "status"], name="doc_dblk_tnt_fld_stat_idx"),
        ]

    def __str__(self):
        return f"{self.batch_name} ({self.number}) — {self.get_status_display()}"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def source_type_badge_class(self):
        return self.SOURCE_TYPE_CSS.get(self.source_type, "badge-slate")

    @property
    def progress_percentage(self):
        if self.total_files_detected > 0:
            return round((self.processed_files_count / self.total_files_detected) * 100, 1)
        if self.status == "completed":
            return 100.0
        return 0.0

    @property
    def success_rate_percentage(self):
        if self.processed_files_count > 0:
            return round((self.success_files_count / self.processed_files_count) * 100, 1)
        return 0.0

    @property
    def total_mb_processed(self):
        return round(self.total_bytes_processed / (1024**2), 2)
