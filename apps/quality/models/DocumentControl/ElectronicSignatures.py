import hashlib
import hmac
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ElectronicSignatureRecord(TenantNumbered):
    NUMBER_PREFIX = "QSIG"

    MEANING_CHOICES = [
        ("authored", "Author / Originator Sign-Off"),
        ("reviewed", "Technical Verification / Peer Review"),
        ("quality_approval", "Quality Assurance Approval"),
        ("management_approval", "Management / Executive Authorization"),
        ("ccb_approval", "Change Control Board Approval"),
        ("acknowledgment", "Read, Understood & Compliance Agreement"),
    ]

    MEANING_CSS = {
        "authored": "badge-slate",
        "reviewed": "badge-info",
        "quality_approval": "badge-green",
        "management_approval": "badge-amber",
        "ccb_approval": "badge-info",
        "acknowledgment": "badge-green",
    }

    document = models.ForeignKey(
        "quality.ControlledDocument", on_delete=models.CASCADE, related_name="signature_manifests"
    )
    change_order = models.ForeignKey(
        "quality.DocumentChangeOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="signatures"
    )
    signer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quality_signatures"
    )
    signer_name = models.CharField(
        max_length=150, help_text="Printed legal name of the signer per 21 CFR § 11.50(a)(1)."
    )
    signer_title = models.CharField(max_length=100, blank=True)
    signature_meaning = models.CharField(max_length=32, choices=MEANING_CHOICES)
    signature_timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    document_revision = models.CharField(max_length=20)
    signature_hash = models.CharField(
        max_length=64, editable=False, help_text="Cryptographic SHA-256 hash binding signer, document, and intent."
    )
    comments = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-signature_timestamp"]
        verbose_name = "Electronic Signature Record"
        verbose_name_plural = "Electronic Signature Records"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qsig_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "document", "-signature_timestamp"], name="idx_qsig_ten_doc_time"),
            models.Index(fields=["tenant", "signer", "-signature_timestamp"], name="idx_qsig_ten_sig_time"),
            models.Index(fields=["tenant", "signature_hash"], name="idx_qsig_ten_hash"),
            models.Index(fields=["tenant", "signature_meaning"], name="idx_qsig_ten_meaning"),
        ]

    def __str__(self):
        return f"{self.number} - {self.signer_name} ({self.get_signature_meaning_display()})"

    def generate_hash(self):
        secret = getattr(settings, "SECRET_KEY", "nav_erp_qms_sig_secret")
        payload = f"{self.tenant_id}:{self.document_id}:{self.document_revision}:{self.signer_id}:{self.signature_meaning}"
        return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def save(self, *args, **kwargs):
        if not self.signature_hash:
            self.signature_hash = self.generate_hash()
        super().save(*args, **kwargs)
