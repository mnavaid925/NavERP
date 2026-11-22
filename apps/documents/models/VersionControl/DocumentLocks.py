from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentLock(TenantNumbered):
    """Exclusive check-in/check-out lock governing reservation, editing exclusivity, and forced override."""

    NUMBER_PREFIX = "DLOCK"

    LOCK_TYPE_CHOICES = (
        ("exclusive", "Exclusive Editing Lock"),
        ("reservation", "Intent / Reservation Hold"),
    )

    STATUS_CHOICES = (
        ("active", "Active Lock"),
        ("checked_in", "Checked In (Resolved)"),
        ("discarded", "Discarded / Cancelled"),
        ("force_unlocked", "Forcibly Broken by Admin"),
    )

    STATUS_CSS = {
        "active": "badge-red",
        "checked_in": "badge-green",
        "discarded": "badge-slate",
        "force_unlocked": "badge-amber",
    }

    LOCK_TYPE_CSS = {
        "exclusive": "badge-red",
        "reservation": "badge-amber",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="locks",
    )
    base_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="checked_out_locks",
    )
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_locks",
    )
    checked_out_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    lock_type = models.CharField(
        max_length=20,
        choices=LOCK_TYPE_CHOICES,
        default="exclusive",
    )
    checkout_note = models.CharField(max_length=500, blank=True)
    working_copy_file = models.FileField(
        upload_to="documents/working_copies/%Y/%m/",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )
    unlocked_at = models.DateTimeField(null=True, blank=True)
    unlocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unlocked_document_locks",
    )
    override_reason = models.TextField(
        blank=True,
        help_text="Mandatory justification for administrative override",
    )

    class Meta:
        ordering = ["-checked_out_at"]
        verbose_name = "Document Lock"
        verbose_name_plural = "Document Locks"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dlock_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "document", "status"], name="idx_dlock_ten_doc_stat"),
        ]

    def __str__(self):
        return f"{self.number} — {self.document.number} ({self.get_status_display()})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def lock_type_badge_class(self):
        return self.LOCK_TYPE_CSS.get(self.lock_type, "badge-slate")

    @property
    def is_stale_lock(self):
        if self.status == "active" and self.expires_at:
            return timezone.now() > self.expires_at
        return False
