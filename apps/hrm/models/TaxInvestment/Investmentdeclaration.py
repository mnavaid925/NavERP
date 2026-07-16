"""HRM 3.16 Tax & Investment — Investmentdeclaration models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.TaxInvestment.Taxregimeconfig import TaxRegimeConfig
from apps.hrm.models.TaxInvestment.Taxregimeconfig import TaxRegimeConfig


class InvestmentDeclaration(TenantNumbered):
    """A per-employee-per-FY income-tax declaration header (3.16) — ``ITD-#####``. Regime election +
    declaration/proof windows + the previous-employer figures; its ``lines`` carry the section-wise
    declared amounts. ``draft→submitted→locked`` gates editability (``is_editable``)."""

    NUMBER_PREFIX = "ITD"

    REGIME_CHOICES = TaxRegimeConfig.REGIME_CHOICES
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("locked", "Locked"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="tax_declarations")
    financial_year = models.CharField(max_length=10, help_text='Indian FY, e.g. "2025-26".')
    regime_elected = models.CharField(max_length=10, choices=REGIME_CHOICES, default="new")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    declaration_window_open = models.DateField(null=True, blank=True)
    declaration_window_close = models.DateField(null=True, blank=True)
    proof_window_open = models.DateField(null=True, blank=True)
    proof_window_close = models.DateField(null=True, blank=True)
    previous_employer_income = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        help_text="Salary earned with a previous employer this FY (mid-year joiner projection input).")
    previous_employer_tds = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-financial_year", "employee__party__name"]
        unique_together = ("tenant", "employee", "financial_year")
        indexes = [
            models.Index(fields=["tenant", "financial_year"], name="hrm_itd_tenant_fy_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_itd_tenant_status_idx"),
        ]

    @property
    def is_editable(self):
        """A draft declaration's regime + lines are editable; submitted/locked are read-only."""
        return self.status == "draft"

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.financial_year}"


class InvestmentDeclarationLine(TenantOwned):
    """One section row of an ``InvestmentDeclaration`` (3.16). ``declared_amount`` is the employee's
    claim; ``verified_amount`` is set from approved ``InvestmentProof``s (or hand-set by HR) and is what
    the FINAL computation uses. Statutory per-section caps are applied in ``TaxComputation`` (surfaced,
    not truncated), never here."""

    SECTION_CODE_CHOICES = [
        ("80c", "Section 80C"),
        ("80d", "Section 80D — Self & Family"),
        ("80d_parents", "Section 80D — Parents"),
        ("hra", "HRA Exemption"),
        ("24b_home_loan_interest", "Section 24(b) — Home Loan Interest"),
        ("80ccd_1b_nps", "Section 80CCD(1B) — NPS"),
        ("lta", "Leave Travel Allowance"),
        ("80e_education_loan", "Section 80E — Education Loan Interest"),
        ("other_chapter_via", "Other Chapter VI-A"),
    ]

    declaration = models.ForeignKey("hrm.InvestmentDeclaration", on_delete=models.CASCADE, related_name="lines")
    section_code = models.CharField(max_length=25, choices=SECTION_CODE_CHOICES)
    declared_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    verified_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, editable=False,
        help_text="Final amount used once proofs are checked — set by proof verification, never form-typed.")
    # HRA-only sub-fields (blank unless section_code="hra").
    monthly_rent_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_metro_city = models.BooleanField(default=False,
        help_text="HRA: metro cities exempt up to 50% of basic, non-metro 40%.")
    landlord_pan = models.CharField(max_length=10, blank=True,
        help_text="HRA: landlord PAN (mandatory when annual rent exceeds ₹1,00,000).")
    # 24(b)-only sub-field.
    lender_name = models.CharField(max_length=255, blank=True, help_text="Home-loan lender (Section 24b).")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["declaration", "section_code"]
        unique_together = ("tenant", "declaration", "section_code")
        indexes = [
            models.Index(fields=["tenant", "declaration"], name="hrm_idl_tenant_decl_idx"),
        ]

    @property
    def effective_amount(self):
        """The amount the computation uses — verified when set, else the declared claim."""
        return self.verified_amount if self.verified_amount is not None else self.declared_amount

    def recompute_verified(self):
        """Roll ``verified_amount`` up from this line's ``verified`` proofs' amounts — the sum of their
        ``amount``s (``None`` when no verified proof carries an amount, so the computation falls back to
        the declared amount via ``effective_amount``)."""
        total = self.proofs.filter(verification_status="verified").aggregate(s=Sum("amount"))["s"]
        self.verified_amount = total
        self.save(update_fields=["verified_amount", "updated_at"])

    def __str__(self):
        return f"{self.declaration} · {self.get_section_code_display()}"
