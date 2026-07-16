"""HRM 3.13 Salary Structure — SalaryStructureLines models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.SalaryStructure.Paycomponent import PayComponent
from apps.hrm.models.SalaryStructure.Paycomponent import PayComponent


class SalaryStructureLine(TenantOwned):
    """One component row in a ``SalaryStructureTemplate``'s CTC breakdown (3.13). May override the
    component's default amount / percentage / calc-type for this template.

    NOTE (v1 simplification): all percentage calc types (``pct_of_basic``/``pct_of_ctc``/
    ``pct_of_gross``) resolve against the template's ``annual_ctc_amount`` because no separate stored
    basic/gross subtotal exists yet — a true multi-base resolver is deferred to a later pass."""

    template = models.ForeignKey("hrm.SalaryStructureTemplate", on_delete=models.CASCADE, related_name="lines")
    pay_component = models.ForeignKey("hrm.PayComponent", on_delete=models.PROTECT)
    calculation_type = models.CharField(max_length=20, choices=PayComponent.CALCULATION_TYPE_CHOICES, blank=True,
        help_text="Overrides the component's calculation type on this template; blank = use the component's.")
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sequence", "id"]
        unique_together = ("tenant", "template", "pay_component")
        indexes = [
            models.Index(fields=["tenant", "template"], name="hrm_ssl_tenant_template_idx"),
        ]

    def resolved_amount(self, ctc=None):
        """The annual amount this line contributes to the CTC total. ``ctc`` overrides the base for
        percentage lines (e.g. an employee's actual assigned CTC at payroll time so two employees on
        the same template but different CTCs get different pay); defaults to the template's
        ``annual_ctc_amount``. (v1: all pct types resolve off this single base.)"""
        effective_calc = self.calculation_type or self.pay_component.calculation_type
        if effective_calc == "fixed_amount":
            amount = self.amount if self.amount is not None else self.pay_component.default_amount
            return amount if amount is not None else Decimal("0")
        pct = self.percentage if self.percentage is not None else self.pay_component.default_percentage
        pct = pct if pct is not None else Decimal("0")
        base = ctc if ctc is not None else (self.template.annual_ctc_amount or Decimal("0"))
        return (base * pct / Decimal("100")).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.template} · {self.pay_component}"
