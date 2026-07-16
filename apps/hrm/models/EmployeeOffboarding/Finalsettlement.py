"""HRM 3.4 Employee Offboarding — Finalsettlement models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class FinalSettlement(TenantNumbered):
    """The full-and-final settlement for a ``SeparationCase`` (3.4) — one per case (DB-enforced).
    Earnings minus deductions give the derived ``net_payable`` (never stored). ``status`` runs
    draft → computed → hr_approved → finance_approved → paid (+ cancelled). ``gl_posted`` is a stub:
    GL posting stays with ``accounting.PayrollRun`` (a later integration pass)."""

    NUMBER_PREFIX = "FNF"

    FNF_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("computed", "Computed"),
        ("hr_approved", "HR Approved"),
        ("finance_approved", "Finance Approved"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ]

    case = models.ForeignKey("hrm.SeparationCase", on_delete=models.CASCADE, related_name="final_settlements")
    settlement_date = models.DateField(null=True, blank=True, help_text="Target payment date.")
    # --- Earnings ---
    prorata_salary = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    leave_encashment_days = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    leave_encashment_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    gratuity_eligible = models.BooleanField(default=False)
    gratuity_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    bonus_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    reimbursement_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    other_income = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    # --- Deductions ---
    notice_recovery_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, help_text="Recovery for unserved notice (or a negative value for an employer buyout payout).")
    loan_recovery = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    asset_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    advance_recovery = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    professional_tax = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    other_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    # --- Workflow-owned ---
    status = models.CharField(max_length=20, choices=FNF_STATUS_CHOICES, default="draft", editable=False)
    hr_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_fnf_hr_approved", editable=False)
    hr_approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    finance_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_fnf_finance_approved", editable=False)
    finance_approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    paid_at = models.DateField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)
    gl_posted = models.BooleanField(default=False, editable=False, help_text="GL-posting stub — always False in v1 (posting deferred to accounting.PayrollRun).")

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("tenant", "number"), ("tenant", "case")]
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_fnf_tenant_status_idx"),
            models.Index(fields=["tenant", "case"], name="hrm_fnf_tenant_case_idx"),
        ]

    @property
    def total_earnings(self):
        return (self.prorata_salary + self.leave_encashment_amount + self.gratuity_amount
                + self.bonus_amount + self.reimbursement_amount + self.other_income)

    @property
    def total_deductions(self):
        return (self.notice_recovery_amount + self.loan_recovery + self.asset_deduction
                + self.advance_recovery + self.tax_deduction + self.professional_tax
                + self.other_deduction)

    @property
    def net_payable(self):
        """Derived — never stored. Total earnings minus total deductions."""
        return self.total_earnings - self.total_deductions

    def __str__(self):
        name = self.case.employee.name if self.case_id and self.case.employee_id else "—"
        return f"{self.number} · FnF for {name} [{self.get_status_display()}]"
