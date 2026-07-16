"""HRM 3.15 Statutory Compliance — Statutoryconfig models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.StatutoryCompliance.INDIAN_STATE_CHOICESs import INDIAN_STATE_CHOICES
from apps.hrm.models.StatutoryCompliance.INDIAN_STATE_CHOICESs import INDIAN_STATE_CHOICES


class StatutoryConfig(TenantOwned):
    """Tenant-wide statutory registration + default-rate master (3.15) — a settings
    singleton (one row per tenant), mirroring Zoho Payroll's single Statutory Components
    screen. Overrides ``TenantOwned``'s FK with a ``OneToOneField`` so there is exactly
    one config per tenant. Rates/ceilings are stored for documentation + the register
    aggregation; the actual per-payslip statutory computation stays in
    ``PayComponent``/``Payslip.recompute()`` (this model never re-derives contributions)."""

    tenant = models.OneToOneField(
        "core.Tenant", on_delete=models.CASCADE, related_name="hrm_statutory_config")

    # PF (Provident Fund) — Zoho: PF establishment code + ₹15,000 Basic+DA ceiling, 12%/12%.
    pf_establishment_code = models.CharField(max_length=50, blank=True)
    pf_wage_ceiling = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("15000.00"),
        help_text="Monthly Basic+DA ceiling for PF (documentation; enforcement stays in payroll).")
    pf_employee_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00"))
    pf_employer_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00"))
    # ESI (Employee State Insurance) — Zoho: ESI number + ₹21,000 gross ceiling, 0.75%/3.25%.
    esi_employer_code = models.CharField(max_length=50, blank=True)
    esi_wage_ceiling = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("21000.00"),
        help_text="Monthly gross ceiling below which an employee is ESI-eligible.")
    esi_employee_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.75"))
    esi_employer_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("3.25"))
    # PT (Professional Tax) — state-scoped; the fallback state when an employee's own can't resolve.
    pt_default_state = models.CharField(max_length=50, choices=INDIAN_STATE_CHOICES, blank=True)
    # TDS (Tax Deducted at Source) — employer TAN + Form 16 config (greytHR/ClearTax).
    tan_number = models.CharField(max_length=20, blank=True,
        help_text="Employer Tax Deduction Account Number — mandatory on Form 24Q/16 (distinct from PAN).")
    tds_circle_address = models.TextField(blank=True, help_text="TDS circle/ward address printed on Form 16.")
    pan_of_deductor = models.CharField(max_length=10, blank=True,
        help_text="The employer's own PAN (distinct from an employee's PAN in EmployeeProfile.national_id).")
    # LWF (Labour Welfare Fund) — org-wide master switch; per-state detail on StatutoryStateRule.
    is_lwf_applicable = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Statutory Configuration"
        verbose_name_plural = "Statutory Configuration"

    @classmethod
    def for_tenant(cls, tenant):
        """Get-or-create the single config row for ``tenant`` (consistent call-site helper)."""
        obj, _ = cls.objects.get_or_create(tenant=tenant)
        return obj

    def __str__(self):
        return f"Statutory Config · {self.tenant.name if self.tenant_id else ''}"
