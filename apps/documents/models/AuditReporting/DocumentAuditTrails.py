import hashlib
import json
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentAuditTrail(TenantNumbered):
    """Immutable, append-only document activity audit ledger with SHA-256 cryptographic chain hashing."""

    NUMBER_PREFIX = "DAUD"

    ACTION_TYPE_CHOICES = (
        ("created", "Document Created"),
        ("viewed", "Document Viewed"),
        ("previewed", "Document Previewed"),
        ("edited", "Document Edited"),
        ("version_uploaded", "New Version Uploaded"),
        ("downloaded", "Document Downloaded"),
        ("printed", "Document Printed"),
        ("checked_out", "Checked Out"),
        ("checked_in", "Checked In"),
        ("permission_changed", "Permission Modified"),
        ("watermark_applied", "Watermark Applied"),
        ("shared_externally", "Shared Externally"),
        ("share_revoked", "Share Revoked"),
        ("workflow_approved", "Workflow Approved"),
        ("workflow_rejected", "Workflow Rejected"),
        ("signed", "Document Signed"),
        ("moved", "Document Moved"),
        ("deleted", "Document Deleted"),
        ("restored", "Document Restored"),
        ("purged", "Document Purged"),
        ("dlp_violation", "DLP Violation Blocked"),
        ("auditor_portal_accessed", "Auditor Portal Inspection"),
    )

    ACTION_TYPE_CSS = {
        "created": "badge-info",
        "viewed": "badge-slate",
        "previewed": "badge-slate",
        "edited": "badge-info",
        "version_uploaded": "badge-info",
        "downloaded": "badge-green",
        "printed": "badge-slate",
        "checked_out": "badge-amber",
        "checked_in": "badge-green",
        "permission_changed": "badge-amber",
        "watermark_applied": "badge-slate",
        "shared_externally": "badge-amber",
        "share_revoked": "badge-red",
        "workflow_approved": "badge-green",
        "workflow_rejected": "badge-red",
        "signed": "badge-green",
        "moved": "badge-slate",
        "deleted": "badge-red",
        "restored": "badge-green",
        "purged": "badge-red",
        "dlp_violation": "badge-red",
        "auditor_portal_accessed": "badge-info",
    }

    RESULT_CSS = {
        True: "badge-green",
        False: "badge-red",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
        db_index=True,
        help_text="Associated logical document, nullable for tenant-wide or purged actions",
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
        help_text="Target version snapshot if applicable",
    )
    document_number_snapshot = models.CharField(
        max_length=64,
        blank=True,
        help_text="Immutable document number snapshot at time of event",
    )
    document_title_snapshot = models.CharField(
        max_length=255,
        blank=True,
        help_text="Immutable document title snapshot at time of event",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_audit_entries",
        db_index=True,
        help_text="Authenticated system user performing action",
    )
    actor_email_snapshot = models.EmailField(
        blank=True,
        help_text="Immutable user email snapshot at time of event",
    )
    action_type = models.CharField(
        max_length=40,
        choices=ACTION_TYPE_CHOICES,
        db_index=True,
    )
    event_timestamp = models.DateTimeField(
        default=timezone.now,
        editable=False,
        db_index=True,
    )
    is_success = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether action succeeded or was blocked/denied",
    )
    failure_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reason for failure or security block if unsuccessful",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address",
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        help_text="Browser/client user agent string",
    )
    session_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="Session identifier for correlation",
    )
    details_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured event parameters, change diffs, or metadata",
    )
    prev_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 chain hash of the preceding tenant audit entry",
    )
    chain_hash = models.CharField(
        max_length=64,
        editable=False,
        db_index=True,
        help_text="Cryptographic SHA-256 hash ensuring mathematical tamper evidence",
    )

    class Meta:
        ordering = ["-event_timestamp", "-id"]
        verbose_name = "Document Audit Trail"
        verbose_name_plural = "Document Audit Trails"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="doc_daud_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "event_timestamp"], name="doc_daud_tnt_evt_idx"),
            models.Index(fields=["tenant", "action_type"], name="doc_daud_tnt_act_idx"),
            models.Index(fields=["tenant", "document"], name="doc_daud_tnt_doc_idx"),
            models.Index(fields=["tenant", "actor"], name="doc_daud_tnt_usr_idx"),
            models.Index(fields=["tenant", "is_success"], name="doc_daud_tnt_suc_idx"),
            models.Index(fields=["tenant", "chain_hash"], name="doc_daud_chn_hsh_idx"),
        ]

    def __str__(self):
        doc = self.document_number_snapshot or (self.document.number if self.document else "General")
        actor = self.actor_email_snapshot or (self.actor.email if self.actor else "System/Guest")
        return f"[{self.number}] {self.get_action_type_display()} on {doc} by {actor}"

    def compute_chain_hash(self, previous_hash=None):
        """Compute SHA-256 cryptographic chain hash for tamper evidence."""
        p_hash = previous_hash if previous_hash is not None else (self.prev_hash or "")
        t_id = str(self.tenant_id or "")
        ts = self.event_timestamp.isoformat() if self.event_timestamp else timezone.now().isoformat()
        act = str(self.action_type or "")
        actor_em = str(self.actor_email_snapshot or (self.actor.email if self.actor else ""))
        doc_num = str(self.document_number_snapshot or (self.document.number if self.document else ""))
        try:
            details_str = json.dumps(self.details_json or {}, sort_keys=True)
        except Exception:
            details_str = "{}"

        raw_payload = f"{p_hash}|{t_id}|{act}|{ts}|{actor_em}|{doc_num}|{details_str}"
        return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    def verify_hash(self):
        """Verify whether chain_hash matches computed hash from record data."""
        expected = self.compute_chain_hash(self.prev_hash)
        return self.chain_hash == expected

    def get_action_type_badge(self):
        return self.ACTION_TYPE_CSS.get(self.action_type, "badge-slate")

    def get_result_badge(self):
        return self.RESULT_CSS.get(self.is_success, "badge-slate")

    def save(self, *args, **kwargs):
        # Enforce immutability for existing records
        if self.pk:
            # Check if this is an actual database update
            existing = DocumentAuditTrail.objects.filter(pk=self.pk).exists()
            if existing:
                raise ValidationError("Audit records are strictly immutable and cannot be updated.")

        # Populate snapshots before computing chain hash
        if self.document and not self.document_number_snapshot:
            self.document_number_snapshot = getattr(self.document, "number", "")
        if self.document and not self.document_title_snapshot:
            self.document_title_snapshot = getattr(self.document, "title", "")
        if self.actor and not self.actor_email_snapshot:
            self.actor_email_snapshot = getattr(self.actor, "email", "")

        # Compute chain hash if missing
        if not self.chain_hash:
            if not self.prev_hash and self.tenant_id:
                last_entry = (
                    DocumentAuditTrail.objects.filter(tenant=self.tenant)
                    .exclude(pk=self.pk if self.pk else 0)
                    .order_by("-id")
                    .first()
                )
                self.prev_hash = (
                    last_entry.chain_hash
                    if last_entry and last_entry.chain_hash
                    else "GENESIS_BLOCK_000000000000000000000000000000000000000000000000000000"
                )
            self.chain_hash = self.compute_chain_hash(self.prev_hash)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit records cannot be deleted.")
