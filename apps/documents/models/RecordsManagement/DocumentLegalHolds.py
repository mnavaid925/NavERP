from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentLegalHold(TenantNumbered):
    """Litigation or regulatory preservation hold overriding retention and halting disposition."""

    NUMBER_PREFIX = "DHLD"

    HOLD_REASON_CHOICES = (
        ("litigation", "Pending or Threatened Litigation"),
        ("regulatory_audit", "Government / Regulatory Audit"),
        ("tax_investigation", "Tax / Financial Investigation"),
        ("internal_inquiry", "Internal Compliance Inquiry"),
        ("ediscovery_matter", "Formal eDiscovery Preservation"),
    )

    HOLD_REASON_CSS = {
        "litigation": "badge-red",
        "regulatory_audit": "badge-amber",
        "tax_investigation": "badge-slate",
        "internal_inquiry": "badge-info",
        "ediscovery_matter": "badge-red",
    }

    HOLD_STATUS_CSS = {
        True: "badge-red",
        False: "badge-muted",
    }

    matter_name = models.CharField(max_length=255)
    matter_number = models.CharField(max_length=100, db_index=True)
    hold_reason = models.CharField(max_length=30, choices=HOLD_REASON_CHOICES, default="litigation")
    description = models.TextField(blank=True)
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="legal_holds",
    )
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="placed_document_legal_holds",
    )
    placed_at = models.DateTimeField(default=timezone.now, db_index=True)
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodian_document_legal_holds",
    )
    custodian_notified = models.BooleanField(default=False)
    custodian_acknowledged_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="released_document_legal_holds",
    )
    released_at = models.DateTimeField(null=True, blank=True)
    release_justification = models.TextField(blank=True)
    core_legal_hold = models.ForeignKey(
        "core.LegalHold",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_holds",
    )

    class Meta:
        ordering = ["-placed_at"]
        verbose_name = "Document Legal Hold"
        verbose_name_plural = "Document Legal Holds"
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="doc_dhld_tnt_act_idx"),
            models.Index(fields=["tenant", "matter_number"], name="doc_dhld_tnt_mat_idx"),
            models.Index(fields=["tenant", "document"], name="doc_dhld_tnt_doc_idx"),
        ]

    def __str__(self):
        return f"{self.number} ({self.matter_number}) - {self.document.title}"

    @property
    def reason_badge_class(self):
        return self.HOLD_REASON_CSS.get(self.hold_reason, "badge-slate")

    @property
    def status_badge_class(self):
        return "badge-red" if self.is_active else "badge-muted"

    def release_hold(self, user, justification):
        now = timezone.now()
        self.is_active = False
        self.released_by = user
        self.released_at = now
        self.release_justification = justification
        self.save(update_fields=["is_active", "released_by", "released_at", "release_justification", "updated_at"])

    def acknowledge_hold(self, user):
        self.custodian_acknowledged_at = timezone.now()
        self.custodian_notified = True
        self.save(update_fields=["custodian_acknowledged_at", "custodian_notified", "updated_at"])
