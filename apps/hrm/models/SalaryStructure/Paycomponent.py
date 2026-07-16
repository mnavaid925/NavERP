"""HRM 3.13 Salary Structure — Paycomponent models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.13 Salary Structure — PayComponent / SalaryStructureTemplate /
# SalaryStructureLine / EmployeeSalaryStructure
#
# The compensation DEFINITION layer (pay components + grade-wise CTC templates +
# per-employee assignments). It does NOT run payroll or post to the GL — that is owned by
# ``accounting.PayrollRun`` (3.14 / Accounting, per lesson L29); 3.13 only DEFINES the
# structures a payroll run later consumes.
# ---------------------------------------------------------------------------
class PayComponent(TenantOwned):
    """A reusable pay / deduction / statutory / reimbursement / variable component (3.13). This one
    catalog table covers four of the five NavERP.md 3.13 bullets (Pay Components, Tax Components,
    Reimbursements, Variable Pay) via ``component_type``; a ``SalaryStructureLine`` references a
    component and may override its default amount/percentage per template."""

    COMPONENT_TYPE_CHOICES = [
        ("earning", "Earning"),
        ("statutory_deduction", "Statutory Deduction"),
        ("voluntary_deduction", "Voluntary Deduction"),
        ("reimbursement", "Reimbursement"),
        ("variable", "Variable"),
    ]
    CALCULATION_TYPE_CHOICES = [
        ("fixed_amount", "Fixed Amount"),
        ("pct_of_basic", "% of Basic"),
        ("pct_of_ctc", "% of CTC"),
        ("pct_of_gross", "% of Gross"),
    ]
    FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("annual", "Annual"),
        ("one_time", "One-Time"),
    ]
    CONTRIBUTION_SIDE_CHOICES = [
        ("employee", "Employee"),
        ("employer", "Employer"),
        ("both", "Both"),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, blank=True, help_text="Optional short code, e.g. HRA, PF-EE.")
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPE_CHOICES, default="earning")
    variable_subtype = models.CharField(max_length=30, blank=True,
        help_text="Only for variable components — e.g. bonus, incentive, commission.")
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPE_CHOICES, default="fixed_amount")
    default_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Org-wide default when the calculation is a fixed amount (a structure line can override).")
    default_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Org-wide default when the calculation is a percentage (a structure line can override).")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="monthly")
    is_taxable = models.BooleanField(default=True)
    include_in_ctc = models.BooleanField(default=True)
    contribution_side = models.CharField(max_length=10, choices=CONTRIBUTION_SIDE_CHOICES, default="employee",
        help_text="Which side pays this — mainly for statutory components (PF/ESI).")
    annual_cap_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Annual cap, e.g. for a reimbursement like LTA/medical.")
    requires_bill = models.BooleanField(default=False,
        help_text="Reimbursement requires a submitted bill/receipt before payout.")
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["display_order", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "component_type"], name="hrm_paycomp_tenant_type_idx"),
        ]

    def clean(self):
        super().clean()
        # Soft consistency: a default may be left blank (a line overrides it), but if one IS provided
        # it must match the calculation type.
        if self.calculation_type == "fixed_amount" and self.default_percentage is not None:
            raise ValidationError({"default_percentage": "Fixed-amount components should not set a default percentage."})
        if self.calculation_type.startswith("pct_") and self.default_amount is not None:
            raise ValidationError({"default_amount": "Percentage-based components should not set a default amount."})

    def __str__(self):
        return self.name
