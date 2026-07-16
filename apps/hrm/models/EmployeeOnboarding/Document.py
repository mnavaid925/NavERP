"""HRM 3.3 Employee Onboarding — Document models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class OnboardingDocument(TenantOwned):
    """A document to collect / e-sign for a program (3.3). ``esign_status`` tracks the signing
    lifecycle without a live e-sign integration; ``external_ref`` stubs a future envelope id.
    ``signed_at`` is system-set by the mark-signed action."""

    DOCUMENT_TYPE_CHOICES = [
        ("employment_contract", "Employment Contract"),
        ("nda", "NDA"),
        ("offer_letter", "Offer Letter"),
        ("id_proof", "ID Proof"),
        ("tax_form", "Tax Form"),
        ("bank_details", "Bank Details"),
        ("policy_acknowledgment", "Policy Acknowledgment"),
        ("background_check", "Background Check"),
        ("custom", "Custom"),
    ]
    ESIGN_STATUS_CHOICES = [
        ("not_required", "Not Required"),
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("signed", "Signed"),
        ("declined", "Declined"),
    ]

    program = models.ForeignKey("hrm.OnboardingProgram", on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default="custom")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="hrm/onboarding/docs/%Y/%m/", null=True, blank=True)
    esign_required = models.BooleanField(default=False)
    esign_status = models.CharField(max_length=20, choices=ESIGN_STATUS_CHOICES, default="not_required")
    due_date = models.DateField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True, editable=False)
    external_ref = models.CharField(max_length=255, blank=True, help_text="External e-sign envelope/reference id (future integration).")

    class Meta:
        ordering = ["program", "document_type", "title"]
        indexes = [
            models.Index(fields=["tenant", "program"], name="hrm_ond_tenant_prog_idx"),
            models.Index(fields=["tenant", "program", "esign_status"], name="hrm_ond_tenant_prog_esign_idx"),
        ]

    def save(self, *args, **kwargs):
        # ``esign_status`` is workflow-owned (not a form field) — derive its open value from the
        # ``esign_required`` toggle so it can't be hand-advanced via a crafted POST. A required doc
        # enters the signing flow at ``pending``; an unrequired one is ``not_required``. The
        # terminal ``signed`` (set by mark-signed) / ``declined`` states are never overwritten, and
        # the e-sign-provider integration states (``sent``/``viewed``) are left untouched.
        if self.esign_status not in ("signed", "declined", "sent", "viewed"):
            self.esign_status = "pending" if self.esign_required else "not_required"
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.program} → {self.title}"
