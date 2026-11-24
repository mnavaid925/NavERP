from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DestructionCertificate(TenantNumbered):
    """Immutable proof-of-disposition and legal certificate of destruction surviving document deletion."""

    NUMBER_PREFIX = "DDST"

    DISPOSITION_TYPE_CHOICES = (
        ("destruction", "Permanent Secure Destruction"),
        ("archival_transfer", "Transfer to Permanent Archives"),
        ("deaccession", "Deaccession & Removal"),
    )

    DESTRUCTION_METHOD_CHOICES = (
        ("database_purge", "Cryptographic Deletion & DB Purge"),
        ("dod_5220_22m", "DoD 5220.22-M Electronic Sanitization"),
        ("nist_800_88", "NIST SP 800-88 Media Sanitization"),
        ("cryptographic_erase", "Cryptographic Key Erasure (Zeroize)"),
        ("physical_crosscut", "Physical Cross-Cut Shredding (Paper)"),
        ("nara_transfer", "NARA / Electronic Records Archives Transfer"),
    )

    CERTIFICATE_STATUS_CHOICES = (
        ("pending_approval", "Pending Disposition Approval"),
        ("authorized", "Authorized for Disposition"),
        ("executed", "Executed & Certified Complete"),
        ("rejected", "Rejected / Cancelled"),
    )

    DISPOSITION_TYPE_CSS = {
        "destruction": "badge-red",
        "archival_transfer": "badge-green",
        "deaccession": "badge-amber",
    }

    DESTRUCTION_METHOD_CSS = {
        "database_purge": "badge-slate",
        "dod_5220_22m": "badge-red",
        "nist_800_88": "badge-red",
        "cryptographic_erase": "badge-info",
        "physical_crosscut": "badge-amber",
        "nara_transfer": "badge-green",
    }

    STATUS_CSS = {
        "pending_approval": "badge-amber",
        "authorized": "badge-info",
        "executed": "badge-green",
        "rejected": "badge-muted",
    }

    record_declaration = models.ForeignKey(
        "documents.RecordDeclaration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="destruction_certificates",
    )
    document_title_snapshot = models.CharField(max_length=255)
    document_number_snapshot = models.CharField(max_length=50)
    schedule_name_snapshot = models.CharField(max_length=255)
    disposition_type = models.CharField(max_length=30, choices=DISPOSITION_TYPE_CHOICES, default="destruction")
    destruction_method = models.CharField(max_length=30, choices=DESTRUCTION_METHOD_CHOICES, default="database_purge")
    status = models.CharField(max_length=30, choices=CERTIFICATE_STATUS_CHOICES, default="pending_approval", db_index=True)
    content_verification_hash = models.CharField(max_length=64, blank=True)
    legal_hold_verified_clear = models.BooleanField(default=False)
    hold_verification_date = models.DateTimeField(null=True, blank=True)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authorized_destruction_certificates",
    )
    authorized_at = models.DateTimeField(null=True, blank=True)
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="executed_destruction_certificates",
    )
    executed_at = models.DateTimeField(null=True, blank=True)
    certificate_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Destruction Certificate"
        verbose_name_plural = "Destruction Certificates"
        indexes = [
            models.Index(fields=["tenant", "status"], name="doc_ddst_tnt_sts_idx"),
            models.Index(fields=["tenant", "created_at"], name="doc_ddst_tnt_crt_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.document_title_snapshot}"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def disposition_badge_class(self):
        return self.DISPOSITION_TYPE_CSS.get(self.disposition_type, "badge-slate")

    @property
    def method_badge_class(self):
        return self.DESTRUCTION_METHOD_CSS.get(self.destruction_method, "badge-slate")

    def verify_legal_holds(self):
        if self.record_declaration and self.record_declaration.document:
            has_active_holds = self.record_declaration.document.legal_holds.filter(is_active=True).exists()
            self.legal_hold_verified_clear = not has_active_holds
            self.hold_verification_date = timezone.now()
            if self.pk:
                self.save(update_fields=["legal_hold_verified_clear", "hold_verification_date", "updated_at"])
            return self.legal_hold_verified_clear
        self.legal_hold_verified_clear = True
        self.hold_verification_date = timezone.now()
        if self.pk:
            self.save(update_fields=["legal_hold_verified_clear", "hold_verification_date", "updated_at"])
        return True

    def authorize(self, user):
        if not self.verify_legal_holds():
            raise ValueError("Cannot authorize destruction: Document is currently subject to an active legal hold.")
        self.status = "authorized"
        self.authorized_by = user
        self.authorized_at = timezone.now()
        self.save(update_fields=["status", "authorized_by", "authorized_at", "updated_at"])

    def execute_destruction(self, user):
        if self.status == "executed":
            raise ValueError("Destruction certificate has already been executed.")
        if self.status != "authorized":
            raise ValueError("Cannot execute destruction: Certificate must be authorized first.")
        if not self.verify_legal_holds():
            raise ValueError("Cannot execute destruction: Document has an active legal hold.")
        now = timezone.now()
        self.status = "executed"
        self.executed_by = user
        self.executed_at = now
        if self.record_declaration:
            self.record_declaration.record_status = "disposed"
            self.record_declaration.save(update_fields=["record_status", "updated_at"])
        self.save(update_fields=["status", "executed_by", "executed_at", "updated_at"])

    def save(self, *args, **kwargs):
        if self.record_declaration and not self.document_title_snapshot:
            self.document_title_snapshot = self.record_declaration.document.title
            self.document_number_snapshot = self.record_declaration.document.number
            self.schedule_name_snapshot = f"{self.record_declaration.retention_schedule.code} - {self.record_declaration.retention_schedule.name}"
            if not self.content_verification_hash:
                self.content_verification_hash = self.record_declaration.version_hash_snapshot

        if not self.legal_hold_verified_clear and self.record_declaration and self.record_declaration.document:
            has_active_holds = self.record_declaration.document.legal_holds.filter(is_active=True).exists()
            self.legal_hold_verified_clear = not has_active_holds
            if not self.hold_verification_date:
                self.hold_verification_date = timezone.now()

        super().save(*args, **kwargs)
