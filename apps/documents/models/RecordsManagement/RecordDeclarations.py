import datetime
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class RecordDeclaration(TenantNumbered):
    """Formal enterprise record declaration binding a document to a retention schedule with WORM lock."""

    NUMBER_PREFIX = "DRCD"

    DECLARATION_MODE_CHOICES = (
        ("manual", "Manual User Declaration"),
        ("automatic_rule", "Automatic Metadata/Rule Trigger"),
        ("workflow_trigger", "Workflow Approval Finalization"),
    )

    RECORD_STATUS_CHOICES = (
        ("active", "Active Record (Pre-Cutoff)"),
        ("cutoff", "Cutoff Triggered (In Retention)"),
        ("pending_disposition", "Pending Disposition Review"),
        ("under_legal_hold", "Frozen Under Legal Hold"),
        ("disposed", "Disposed / Destroyed"),
    )

    DECLARATION_MODE_CSS = {
        "manual": "badge-info",
        "automatic_rule": "badge-slate",
        "workflow_trigger": "badge-green",
    }

    RECORD_STATUS_CSS = {
        "active": "badge-green",
        "cutoff": "badge-info",
        "pending_disposition": "badge-amber",
        "under_legal_hold": "badge-red",
        "disposed": "badge-muted",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="record_declarations",
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="record_declarations",
    )
    retention_schedule = models.ForeignKey(
        "documents.RetentionSchedule",
        on_delete=models.PROTECT,
        related_name="declared_records",
    )
    declared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="declared_records",
    )
    declaration_date = models.DateTimeField(default=timezone.now, db_index=True)
    declaration_mode = models.CharField(max_length=30, choices=DECLARATION_MODE_CHOICES, default="manual")
    record_status = models.CharField(max_length=30, choices=RECORD_STATUS_CHOICES, default="active", db_index=True)
    is_vital_record = models.BooleanField(default=False, db_index=True)
    vital_review_frequency_months = models.PositiveIntegerField(default=12)
    last_vital_review_date = models.DateField(null=True, blank=True)
    is_locked = models.BooleanField(default=True)
    cutoff_date = models.DateField(null=True, blank=True, db_index=True)
    cutoff_triggered_at = models.DateTimeField(null=True, blank=True)
    disposition_due_date = models.DateField(null=True, blank=True, db_index=True)
    version_hash_snapshot = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-declaration_date"]
        verbose_name = "Record Declaration"
        verbose_name_plural = "Record Declarations"
        indexes = [
            models.Index(fields=["tenant", "-declaration_date"], name="doc_drcd_tnt_dec_idx"),
            models.Index(fields=["tenant", "record_status"], name="doc_drcd_tnt_sts_idx"),
            models.Index(fields=["tenant", "is_vital_record"], name="doc_drcd_tnt_vtl_idx"),
            models.Index(fields=["tenant", "disposition_due_date"], name="doc_drcd_tnt_due_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.document.title}"

    @property
    def declaration_mode_badge_class(self):
        return self.DECLARATION_MODE_CSS.get(self.declaration_mode, "badge-slate")

    @property
    def status_badge_class(self):
        if self.is_under_legal_hold:
            return "badge-red"
        return self.RECORD_STATUS_CSS.get(self.record_status, "badge-slate")

    @property
    def is_under_legal_hold(self):
        if hasattr(self, "has_active_hold"):
            return bool(self.has_active_hold)
        return self.document.legal_holds.filter(is_active=True).exists()

    def calculate_disposition_due_date(self, from_date=None):
        if self.retention_schedule.is_permanent:
            return None
        start_date = from_date or self.cutoff_date or self.declaration_date.date()
        years = self.retention_schedule.retention_period_years
        months = self.retention_schedule.retention_period_months
        total_months = (years * 12) + months
        
        # Calculate new year and month
        new_year = start_date.year + (start_date.month + total_months - 1) // 12
        new_month = (start_date.month + total_months - 1) % 12 + 1
        # Handle end of month boundary
        day = min(start_date.day, 28)
        return datetime.date(new_year, new_month, day)

    def trigger_cutoff(self):
        now = timezone.now()
        self.cutoff_triggered_at = now
        self.cutoff_date = now.date()
        if self.record_status == "active":
            self.record_status = "cutoff"
        self.disposition_due_date = self.calculate_disposition_due_date(from_date=self.cutoff_date)
        self.save(update_fields=["cutoff_triggered_at", "cutoff_date", "record_status", "disposition_due_date", "updated_at"])

    def save(self, *args, **kwargs):
        if not self.version_hash_snapshot:
            if self.version and getattr(self.version, "file_hash", None):
                self.version_hash_snapshot = self.version.file_hash
            elif hasattr(self.document, "current_version") and self.document.current_version and getattr(self.document.current_version, "file_hash", None):
                self.version_hash_snapshot = self.document.current_version.file_hash

        if not self.disposition_due_date and not self.retention_schedule.is_permanent:
            ref_date = self.cutoff_date or (self.declaration_date.date() if self.declaration_date else timezone.now().date())
            self.disposition_due_date = self.calculate_disposition_due_date(from_date=ref_date)

        super().save(*args, **kwargs)
