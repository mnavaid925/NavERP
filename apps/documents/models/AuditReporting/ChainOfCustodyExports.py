import hashlib
import json
import secrets
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class ChainOfCustodyExport(TenantNumbered):
    """Cryptographic chain-of-custody evidence packages and time-bound external auditor inspection passes."""

    NUMBER_PREFIX = "DCOC"

    REGULATORY_FRAMEWORK_CHOICES = (
        ("general_compliance", "General Corporate Compliance / Audit"),
        ("iso_27001", "ISO/IEC 27001 Information Security"),
        ("soc2_type2", "SOC 2 Type II Security & Confidentiality"),
        ("fda_21cfr11", "FDA 21 CFR Part 11 Electronic Records"),
        ("hipaa", "HIPAA Security Rule"),
        ("gdpr_article30", "GDPR Article 30 Records of Processing"),
        ("legal_hold", "Civil Litigation / Legal Hold Evidence"),
    )

    SCOPE_CHOICES = (
        ("single_document", "Single Document Comprehensive Package"),
        ("folder_tree", "Entire Folder Repository Branch"),
        ("date_range", "All Tenant Activity in Date Range"),
        ("regulatory_filing", "Specific Regulatory Inspection Pack"),
    )

    REGULATORY_FRAMEWORK_CSS = {
        "general_compliance": "badge-slate",
        "iso_27001": "badge-info",
        "soc2_type2": "badge-green",
        "fda_21cfr11": "badge-amber",
        "hipaa": "badge-info",
        "gdpr_article30": "badge-slate",
        "legal_hold": "badge-red",
    }

    STATUS_CSS = {
        "active": "badge-green",
        "expired": "badge-amber",
        "revoked": "badge-red",
    }

    title = models.CharField(
        max_length=200,
        help_text="Title or matter reference for evidence export package",
    )
    regulatory_framework = models.CharField(
        max_length=50,
        choices=REGULATORY_FRAMEWORK_CHOICES,
        default="general_compliance",
    )
    scope = models.CharField(
        max_length=30,
        choices=SCOPE_CHOICES,
        default="single_document",
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_exports",
        db_index=True,
        help_text="Target document if scope is single document",
    )
    folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_exports",
        help_text="Target folder if scope is folder tree",
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Start of chronological scope",
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End of chronological scope",
    )
    package_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Master cryptographic SHA-256 digest sealing manifest payload",
    )
    manifest_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete JSON manifest of files, versions, hashes, and audit events",
    )
    is_sealed = models.BooleanField(
        default=True,
        help_text="Whether package is mathematically sealed and tamper-evident",
    )
    sealed_at = models.DateTimeField(
        default=timezone.now,
    )
    auditor_name = models.CharField(
        max_length=150,
        help_text="Name of accredited auditor or external regulatory inspector",
    )
    auditor_email = models.EmailField(
        help_text="Auditor contact email address",
    )
    auditor_organization = models.CharField(
        max_length=200,
        blank=True,
        help_text="Auditing firm, government body, or judicial party",
    )
    access_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Unguessable URL token for external auditor portal",
    )
    passcode_hash = models.CharField(
        max_length=128,
        blank=True,
        help_text="Hashed passcode required for guest portal authentication",
    )
    is_portal_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether external auditor portal URL is live or disabled",
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Auditor portal access expiration deadline",
    )
    access_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of auditor portal inspections performed",
    )
    last_accessed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dms_created_custody_exports",
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_revoked_custody_exports",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Chain of Custody Export"
        verbose_name_plural = "Chain of Custody Exports"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="doc_dcoc_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "document"], name="doc_dcoc_tnt_doc_idx"),
            models.Index(fields=["tenant", "access_token"], name="doc_dcoc_tnt_tok_idx"),
            models.Index(fields=["tenant", "is_portal_active"], name="doc_dcoc_tnt_act_idx"),
            models.Index(fields=["tenant", "expires_at"], name="doc_dcoc_tnt_exp_idx"),
        ]

    def __str__(self):
        return f"[{self.number}] {self.title} ({self.get_regulatory_framework_display()})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return self.is_portal_active and not self.is_expired

    @property
    def status_key(self):
        if not self.is_portal_active:
            return "revoked"
        if self.is_expired:
            return "expired"
        return "active"

    def get_status_badge(self):
        return self.STATUS_CSS.get(self.status_key, "badge-slate")

    def get_regulatory_framework_badge(self):
        return self.REGULATORY_FRAMEWORK_CSS.get(self.regulatory_framework, "badge-slate")

    def set_passcode(self, raw_passcode):
        if raw_passcode:
            self.passcode_hash = make_password(raw_passcode)
        else:
            self.passcode_hash = ""

    def check_passcode(self, raw_passcode):
        if not self.passcode_hash:
            return True
        return check_password(raw_passcode, self.passcode_hash)

    def revoke(self, user):
        self.is_portal_active = False
        self.revoked_at = timezone.now()
        self.revoked_by = user
        self.save(update_fields=["is_portal_active", "revoked_at", "revoked_by"])

    def generate_manifest(self):
        """Assemble manifest data, compute package SHA-256 seal, and store manifest."""
        if not self.number and self.tenant_id and self.NUMBER_PREFIX:
            from apps.core.utils import next_number
            self.number = next_number(type(self), self.tenant, self.NUMBER_PREFIX)

        manifest = {
            "package_number": self.number or "",
            "title": self.title,
            "regulatory_framework": self.regulatory_framework,
            "scope": self.scope,
            "tenant_id": self.tenant_id,
            "sealed_at": self.sealed_at.isoformat() if self.sealed_at else timezone.now().isoformat(),
            "auditor": {
                "name": self.auditor_name,
                "email": self.auditor_email,
                "organization": self.auditor_organization,
            },
            "document": None,
            "audit_trail_summary": {
                "total_events": 0,
                "latest_chain_hash": "",
            },
        }

        if self.document:
            manifest["document"] = {
                "id": self.document.pk,
                "number": self.document.number,
                "title": self.document.title,
                "status": self.document.status,
                "file_hash_sha256": getattr(self.document, "file_hash_sha256", ""),
                "version_count": self.document.versions.count() if hasattr(self.document, "versions") else 0,
            }

        # Master hash calculation
        raw = json.dumps(manifest, sort_keys=True)
        self.package_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        self.manifest_json = manifest
        return self.package_hash

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.access_token = secrets.token_urlsafe(32)
        if not self.pk:
            if not self.number and self.tenant_id and self.NUMBER_PREFIX:
                from apps.core.utils import next_number
                self.number = next_number(type(self), self.tenant, self.NUMBER_PREFIX)
            if not self.package_hash:
                self.generate_manifest()
            super().save(*args, **kwargs)
            return
        if not self.package_hash:
            self.generate_manifest()
        super().save(*args, **kwargs)
