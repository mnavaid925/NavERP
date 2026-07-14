"""Accounting 2.8 Payroll Integration — PayrollRuns models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ============================================================= 2.8 Payroll Integration
class PayrollRun(TenantNumbered):
    """A pay-period payroll accrual. ``net_pay`` is DERIVED (gross − employee_tax − deductions) so
    the posted JE always balances. Post → Dr Wages/Tax/Benefits Expense / Cr Cash + Taxes Payable
    + Deductions Payable."""

    NUMBER_PREFIX = "PRUN"
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    period_start = models.DateField()
    period_end = models.DateField()
    pay_date = models.DateField()
    headcount = models.PositiveIntegerField(default=0)
    gross_wages = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    employee_tax = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="Withheld from employees")
    employer_tax = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="Employer-paid payroll tax")
    benefits = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="Employer benefit cost")
    deductions = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="Other employee deductions")
    net_pay = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="payroll_runs", editable=False)

    class Meta:
        ordering = ["-pay_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_prun_tenant_status_idx")]

    @property
    def is_locked(self):
        return self.status == "posted"

    def save(self, *args, **kwargs):
        # Net pay is always derived so the payroll JE balances by construction.
        self.net_pay = (self.gross_wages or ZERO) - (self.employee_tax or ZERO) - (self.deductions or ZERO)
        super().save(*args, **kwargs)

    def total_expense(self):
        return (self.gross_wages or ZERO) + (self.employer_tax or ZERO) + (self.benefits or ZERO)

    def __str__(self):
        return f"{self.number} · {self.pay_date}"
