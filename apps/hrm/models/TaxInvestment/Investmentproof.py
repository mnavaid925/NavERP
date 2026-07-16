"""HRM 3.16 Tax & Investment — Investmentproof models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class InvestmentProof(TenantOwned):
    """An uploaded proof document for an ``InvestmentDeclarationLine`` (3.16) + its verification
    workflow. Mirrors ``EmployeeDocument``'s verified_by/verified_at/editable=False convention, one
    state richer (adds ``on_hold``). A line can have several proofs."""

    VERIFICATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
        ("on_hold", "On Hold"),
    ]

    declaration_line = models.ForeignKey(
        "hrm.InvestmentDeclarationLine", on_delete=models.CASCADE, related_name="proofs")
    # WARNING: extension allowlist + size cap enforced in InvestmentProofForm.clean_file (shared
    # _validate_upload). Keep MEDIA_ROOT outside the web root and serve with Content-Disposition:
    # attachment + X-Content-Type-Options: nosniff in production (mirrors EmployeeDocument).
    file = models.FileField(upload_to="hrm/investment_proofs/%Y/%m/")
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="The amount this proof substantiates (a line's verified_amount sums its verified proofs).")
    verification_status = models.CharField(max_length=15, choices=VERIFICATION_STATUS_CHOICES,
        default="pending", editable=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_verified_investment_proofs", editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "declaration_line"], name="hrm_ivp_tenant_line_idx"),
            models.Index(fields=["tenant", "verification_status"], name="hrm_ivp_tenant_vstat_idx"),
        ]

    def __str__(self):
        return f"{self.declaration_line} · {self.title}"
