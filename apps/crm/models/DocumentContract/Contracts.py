"""CRM 1.9 Document & Contract Management — Contracts models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class ContractDocument(TenantNumbered):
    """A rendered document instance with e-signature tracking + versioning (1.9)."""

    NUMBER_PREFIX = "CTR"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("signed", "Signed"),
        ("declined", "Declined"),
        ("expired", "Expired"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    template = models.ForeignKey("crm.DocTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="contracts")
    opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="contracts")
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contracts")
    current_version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    body_snapshot = models.TextField(blank=True)  # merge-resolved HTML captured at send time
    signed_at = models.DateTimeField(null=True, blank=True)  # system-set when all signers sign
    expires_at = models.DateTimeField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contracts")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_ctr_tnt_status_idx"),
            models.Index(fields=["tenant", "opportunity"], name="crm_ctr_tnt_opp_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_ctr_tnt_created_idx"),
            # The File Repository filters contracts by account (performance-review).
            models.Index(fields=["tenant", "account"], name="crm_ctr_tnt_account_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class SignerRecord(models.Model):
    """One signer per contract (1.9). Accessed only through its parent ContractDocument."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    contract = models.ForeignKey("crm.ContractDocument", on_delete=models.CASCADE, related_name="signers")
    signer_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_signer_records")
    signer_name = models.CharField(max_length=255)
    signer_email = models.EmailField()
    token = models.CharField(max_length=64, unique=True)  # URL-safe random token for the signing link
    order = models.PositiveSmallIntegerField(default=1)
    viewed_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.signer_name} <{self.signer_email}>"
