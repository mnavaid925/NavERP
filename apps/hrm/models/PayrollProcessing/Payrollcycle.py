"""HRM 3.14 Payroll Processing — Payrollcycle models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.14 Payroll Processing — PayrollCycle / Payslip / PayslipLine
#
# The OPERATIONAL payroll run: computes per-employee payslips from each employee's active
# ``EmployeeSalaryStructure`` (3.13), routes through an approval workflow, and on lock creates/links
# an ``accounting.PayrollRun`` carrying the rolled-up totals so accounting posts the GL journal
# (lesson L29 — HRM never builds a JournalEntry). Named distinctly from ``accounting.PayrollRun``
# (the financial aggregate) which it hands off to.
# ---------------------------------------------------------------------------
class PayrollCycle(TenantNumbered):
    """A pay-period operational payroll run header (3.14) — ``PRC-#####``. Derived ``total_*`` come from
    its ``Payslip``s; ``accounting_payroll_run`` is set on lock (the accounting GL post is separate)."""

    NUMBER_PREFIX = "PRC"

    CYCLE_TYPE_CHOICES = [
        ("regular", "Regular"),
        ("off_cycle", "Off-Cycle"),
        ("bonus", "Bonus"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("locked", "Locked"),
    ]

    period_start = models.DateField()
    period_end = models.DateField()
    pay_date = models.DateField()
    cycle_type = models.CharField(max_length=20, choices=CYCLE_TYPE_CHOICES, default="regular")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payroll_cycle_submissions", editable=False)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payroll_cycle_approvals", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    accounting_payroll_run = models.ForeignKey(
        "accounting.PayrollRun", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="hrm_cycles")

    class Meta:
        ordering = ["-pay_date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_prc_tenant_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.period_end and self.period_start and self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period-end cannot be before period-start."})

    @property
    def is_locked(self):
        return self.status == "locked"

    def _totals(self):
        """One aggregate query for the three payslip totals, cached per instance so a detail render that
        shows total_gross/deductions/net issues one query, not three."""
        if not hasattr(self, "_totals_cache"):
            self._totals_cache = self.payslips.aggregate(
                g=Sum("gross_pay"), d=Sum("total_deductions"), n=Sum("net_pay"))
        return self._totals_cache

    @property
    def headcount(self):
        return self.payslips.count()

    @property
    def total_gross(self):
        return self._totals()["g"] or ZERO

    @property
    def total_deductions(self):
        return self._totals()["d"] or ZERO

    @property
    def total_net(self):
        return self._totals()["n"] or ZERO

    def __str__(self):
        return f"{self.number} · {self.get_cycle_type_display()} · {self.period_start}–{self.period_end}"
