import uuid
from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.documents.models._base import TenantNumbered


class DocumentSignature(TenantNumbered):
    NUMBER_PREFIX = "DSIG"

    SIGNATURE_TYPE_CHOICES = [
        ("click_to_sign", "Click-to-Sign (Standard Electronic)"),
        ("digital_cert", "Digital Certificate (X.509 / PKI)"),
        ("biometric_pin", "Biometric / Cryptographic PIN"),
    ]

    SIGNATURE_MEANING_CHOICES = [
        ("approval", "I approve this document in full (Approval)"),
        ("authorship", "I am the author and confirm its contents (Authorship)"),
        ("review", "I have reviewed and verified technical accuracy (Review)"),
        ("technical_verification", "Technical & Quality Assurance Verification"),
        ("legal_signoff", "Legal & Regulatory Compliance Sign-Off"),
        ("witness", "I witness the execution of this document (Witness)"),
    ]

    SIGNATURE_TYPE_CSS = {
        "click_to_sign": "badge-info",
        "digital_cert": "badge-green",
        "biometric_pin": "badge-amber",
    }

    SIGNATURE_MEANING_CSS = {
        "approval": "badge-green",
        "authorship": "badge-info",
        "review": "badge-slate",
        "technical_verification": "badge-amber",
        "legal_signoff": "badge-red",
        "witness": "badge-muted",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="signatures",
        db_index=True,
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signatures",
    )
    approval_request = models.ForeignKey(
        "documents.DocumentApprovalRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signatures",
    )
    signer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_signatures",
    )
    signer_name = models.CharField(max_length=150)
    signer_title = models.CharField(max_length=120, blank=True)
    signer_email = models.EmailField(blank=True)
    signature_type = models.CharField(
        max_length=30,
        choices=SIGNATURE_TYPE_CHOICES,
        default="click_to_sign",
        db_index=True,
    )
    signature_meaning = models.CharField(
        max_length=40,
        choices=SIGNATURE_MEANING_CHOICES,
        default="approval",
        db_index=True,
    )
    document_checksum = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of document version at signing time",
    )
    signature_token = models.CharField(
        max_length=128,
        unique=True,
        help_text="Cryptographic signature verification token / UUID",
    )
    signature_glyph = models.TextField(
        blank=True,
        help_text="Drawn SVG signature data or seal stamp",
    )
    certificate_serial = models.CharField(
        max_length=100,
        blank=True,
        help_text="Digital X.509 or eIDAS certificate identifier",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    signed_at = models.DateTimeField(auto_now_add=True)
    is_valid = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-signed_at", "-created_at"]
        verbose_name = "Document Signature"
        verbose_name_plural = "Document Signatures"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dsig_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "document", "is_valid"], name="doc_dsig_tnt_doc_val_idx"),
            models.Index(fields=["tenant", "signer", "signed_at"], name="doc_dsig_tnt_sgn_date_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.signature_token:
            self.signature_token = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} — {self.signer_name} [{self.get_signature_meaning_display()}]"

    def get_absolute_url(self):
        return reverse("documents:signature_detail", kwargs={"pk": self.pk})

    @property
    def signature_type_css_class(self):
        return self.SIGNATURE_TYPE_CSS.get(self.signature_type, "badge-slate")

    @property
    def signature_meaning_css_class(self):
        return self.SIGNATURE_MEANING_CSS.get(self.signature_meaning, "badge-slate")
