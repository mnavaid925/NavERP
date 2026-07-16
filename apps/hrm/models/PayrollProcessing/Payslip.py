"""HRM 3.14 Payroll Processing — Payslip models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.SalaryStructure.Paycomponent import PayComponent
from apps.hrm.models.SalaryStructure.Paycomponent import PayComponent


class Payslip(TenantNumbered):
    """One employee's payslip within a ``PayrollCycle`` (3.14) — ``PSL-#####``. ``gross_pay`` /
    ``total_deductions`` / ``net_pay`` are DERIVED by ``recompute()`` from the employee's
    ``EmployeeSalaryStructure`` (3.13), never hand-typed. Amounts are stored as POSITIVE magnitudes;
    ``PayslipLine.component_type`` distinguishes earning vs deduction (no signed amounts, matching the
    SalaryStructureLine convention). "Locked" is derived from the cycle — no second state machine."""

    NUMBER_PREFIX = "PSL"

    EARNING_TYPES = frozenset({"earning", "reimbursement", "variable"})
    DEDUCTION_TYPES = frozenset({"statutory_deduction", "voluntary_deduction"})

    cycle = models.ForeignKey("hrm.PayrollCycle", on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="payslips")
    salary_structure = models.ForeignKey(
        "hrm.EmployeeSalaryStructure", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payslips", help_text="The structure this payslip was computed from.")
    days_in_period = models.PositiveSmallIntegerField(default=30)
    days_worked = models.PositiveSmallIntegerField(default=30)
    lop_days = models.DecimalField(max_digits=5, decimal_places=2, default=0,
        help_text="Unpaid (loss-of-pay) days in the period.")
    lop_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    gross_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    net_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    arrears_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bonus_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    on_hold = models.BooleanField(default=False)
    hold_reason = models.TextField(blank=True)
    released_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["cycle", "employee__party__name"]
        unique_together = ("tenant", "cycle", "employee")
        indexes = [
            models.Index(fields=["tenant", "cycle"], name="hrm_psl_tenant_cycle_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_psl_tenant_emp_idx"),
        ]

    @property
    def is_locked(self):
        return self.cycle.is_locked

    def clean(self):
        super().clean()
        if self.days_in_period and self.days_worked is not None and self.days_worked > self.days_in_period:
            raise ValidationError({"days_worked": "Days worked cannot exceed the days in the period."})
        if self.days_in_period and self.lop_days is not None and self.lop_days > self.days_in_period:
            raise ValidationError({"lop_days": "LOP days cannot exceed the days in the period."})
        for field in ("arrears_amount", "bonus_amount", "lop_days"):
            value = getattr(self, field)
            if value is not None and value < 0:
                raise ValidationError({field: "This value cannot be negative."})

    def recompute(self):
        """Derive gross/deductions/net + LOP and rebuild the ``PayslipLine`` snapshot rows from the
        resolved salary structure. A locked cycle's payslips are immutable."""
        if self.cycle.is_locked:
            raise ValidationError("Cannot recompute a payslip in a locked cycle.")
        # Resolve the structure's lines → monthly amounts (annual / 12), split earning vs deduction.
        resolved = []
        if self.salary_structure_id and self.salary_structure and self.salary_structure.template_id:
            ctc = self.salary_structure.annual_ctc_amount  # employee's assigned CTC scales the pct lines
            for line in (self.salary_structure.template.lines
                         .select_related("pay_component").order_by("sequence", "id")):
                monthly = (line.resolved_amount(ctc) / Decimal("12")).quantize(Decimal("0.01"))
                resolved.append((line.pay_component, monthly))
        ratio = (Decimal(self.days_worked) / Decimal(self.days_in_period)
                 if self.days_in_period else Decimal("1"))
        period_gross = ZERO
        earning_lines, employee_ded_lines, employer_lines = [], [], []
        for pc, monthly in resolved:
            if pc.component_type in self.EARNING_TYPES:
                amt = (monthly * ratio).quantize(Decimal("0.01"))
                period_gross += amt
                earning_lines.append((pc, amt))
            elif pc.component_type in self.DEDUCTION_TYPES:
                # Employer-side statutory contributions (e.g. employer PF/ESI) are a company cost — they
                # are snapshotted for the GL roll-up but do NOT reduce the employee's net pay. Only
                # employee/both/unspecified-side deductions reduce net.
                if pc.contribution_side == "employer":
                    employer_lines.append((pc, monthly))
                else:
                    employee_ded_lines.append((pc, monthly))
        self.lop_amount = (((period_gross / Decimal(self.days_in_period)) * self.lop_days).quantize(Decimal("0.01"))
                           if self.days_in_period else ZERO)
        self.gross_pay = (period_gross - self.lop_amount + self.arrears_amount
                          + self.bonus_amount).quantize(Decimal("0.01"))
        self.total_deductions = sum((m for _, m in employee_ded_lines), ZERO).quantize(Decimal("0.01"))
        self.net_pay = (self.gross_pay - self.total_deductions).quantize(Decimal("0.01"))
        # Rebuild the snapshot lines (earnings, then arrears/bonus, then LOP, then employee deductions,
        # then employer contributions).
        self.lines.all().delete()
        out = []
        for pc, amt in earning_lines:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name=pc.name,
                component_type=pc.component_type, amount=amt,
                contribution_side=pc.contribution_side, sequence=pc.display_order or 1))
        if self.arrears_amount:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name="Arrears",
                component_type="arrears", amount=self.arrears_amount, sequence=90))
        if self.bonus_amount:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name="Bonus",
                component_type="bonus", amount=self.bonus_amount, sequence=91))
        if self.lop_amount:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name="Loss of Pay",
                component_type="lop", amount=self.lop_amount, sequence=95))
        for pc, m in employee_ded_lines:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name=pc.name,
                component_type=pc.component_type, amount=m,
                contribution_side=pc.contribution_side, sequence=100 + (pc.display_order or 0)))
        for pc, m in employer_lines:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name=pc.name,
                component_type=pc.component_type, amount=m,
                contribution_side=pc.contribution_side, sequence=200 + (pc.display_order or 0)))
        PayslipLine.objects.bulk_create(out)
        self.save(update_fields=["lop_amount", "gross_pay", "total_deductions", "net_pay", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.cycle.number}"


class PayslipLine(TenantOwned):
    """A snapshotted component line on a ``Payslip`` (3.14). name/type/amount/contribution_side are COPIED
    at generation time so a later ``PayComponent``/structure edit never rewrites historical payslips.
    ``amount`` is a positive magnitude; ``component_type`` says earning vs deduction (+ synthetic
    ``arrears``/``bonus``/``lop`` line types)."""

    COMPONENT_TYPE_CHOICES = PayComponent.COMPONENT_TYPE_CHOICES + [
        ("arrears", "Arrears"),
        ("bonus", "Bonus"),
        ("lop", "Loss of Pay"),
    ]

    payslip = models.ForeignKey("hrm.Payslip", on_delete=models.CASCADE, related_name="lines")
    component_name = models.CharField(max_length=150)
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    contribution_side = models.CharField(
        max_length=10, choices=PayComponent.CONTRIBUTION_SIDE_CHOICES, blank=True, default="",
        help_text="Snapshotted from the source component so the lock roll-up needn't re-join PayComponent.")
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sequence", "id"]
        indexes = [
            models.Index(fields=["tenant", "payslip"], name="hrm_psll_tenant_payslip_idx"),
        ]

    def __str__(self):
        return f"{self.payslip} · {self.component_name}"
