"""SCM 4.2 Supplier Relationship Management — SupplierProfile model.

The SRM extension on a supplier ``core.Party``: onboarding lifecycle, qualification tier, and the
due-diligence checklist. Deliberately SEPARATE from ``accounting.VendorProfile`` (OneToOne on the same
Party) which is the AP-side extension (payment terms, 1099, default expense account). A supplier can
have both — its buying/relationship data here, its pay-to data in accounting — and neither owns the
other. One SupplierProfile per Party per tenant.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class SupplierProfile(TenantOwned):
    """SRM master record for a supplier Party — onboarding + qualification + due diligence."""

    ONBOARDING_CHOICES = [
        ("draft", "Draft"),
        ("qualification", "Qualification"),
        ("due_diligence", "Due Diligence"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("suspended", "Suspended"),
    ]
    # Stages that let this supplier be used on new procurement documents.
    ACTIVE_STATUSES = ("approved",)

    TIER_CHOICES = [
        ("strategic", "Strategic"),
        ("preferred", "Preferred"),
        ("approved", "Approved"),
        ("transactional", "Transactional"),
    ]

    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="scm_supplier_profile")
    onboarding_status = models.CharField(max_length=16, choices=ONBOARDING_CHOICES, default="draft")
    tier = models.CharField(max_length=16, choices=TIER_CHOICES, default="transactional")
    category = models.CharField(max_length=120, blank=True, help_text="What this supplier provides")
    # Registration / qualification questionnaire (kept flat — one supplier, a handful of fields).
    legal_name = models.CharField(max_length=255, blank=True)
    tax_registration = models.CharField(max_length=64, blank=True)
    website = models.CharField(max_length=255, blank=True)
    primary_contact_name = models.CharField(max_length=255, blank=True)
    primary_contact_email = models.EmailField(blank=True)
    primary_contact_phone = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=80, blank=True)
    year_established = models.PositiveIntegerField(null=True, blank=True)
    # Due-diligence checklist — each a deliberate sign-off, not a free-text note.
    dd_financials_verified = models.BooleanField(default=False, verbose_name="Financials verified")
    dd_compliance_verified = models.BooleanField(default=False, verbose_name="Compliance / sanctions checked")
    dd_insurance_verified = models.BooleanField(default=False, verbose_name="Insurance verified")
    dd_quality_cert_verified = models.BooleanField(default=False, verbose_name="Quality certification verified")
    dd_references_checked = models.BooleanField(default=False, verbose_name="References checked")
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_supplier_approvals", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True, editable=False)

    class Meta:
        ordering = ["party__name"]
        indexes = [
            models.Index(fields=["tenant", "onboarding_status"], name="scm_supp_tnt_status_idx"),
            models.Index(fields=["tenant", "tier"], name="scm_supp_tnt_tier_idx"),
        ]

    DD_FIELDS = (
        "dd_financials_verified", "dd_compliance_verified", "dd_insurance_verified",
        "dd_quality_cert_verified", "dd_references_checked",
    )

    @property
    def is_active(self):
        return self.onboarding_status in self.ACTIVE_STATUSES

    @property
    def is_editable(self):
        return self.onboarding_status in ("draft", "qualification", "due_diligence")

    def due_diligence_progress(self):
        """How much of the due-diligence checklist is signed off, as a 0-100 percentage."""
        done = sum(1 for f in self.DD_FIELDS if getattr(self, f))
        return round(done * 100 / len(self.DD_FIELDS)) if self.DD_FIELDS else 0

    @property
    def due_diligence_complete(self):
        return all(getattr(self, f) for f in self.DD_FIELDS)

    def __str__(self):
        return f"{self.party_id and self.party.name} ({self.get_tier_display()})"
