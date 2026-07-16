"""HRM 3.37 Compensation & Benefits — Benefitplan models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class BenefitPlan(TenantOwned):
    """A benefit offering in the org's catalog (medical/dental/life/retirement/…) with an employer/employee
    monthly cost split and optional flex-credit eligibility. Reused by EmployeeBenefitEnrollment as the
    election target. Small per-tenant catalog (not auto-numbered). coverage_tier_options is a comma-separated
    list (e.g. 'employee_only,employee_spouse,family') — a full tier-pricing sub-table is deferred."""

    PLAN_TYPE_CHOICES = [
        ("medical", "Medical"),
        ("dental", "Dental"),
        ("vision", "Vision"),
        ("life", "Life Insurance"),
        ("disability", "Disability"),
        ("retirement", "Retirement / Pension"),
        ("wellness", "Wellness"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=150)
    plan_type = models.CharField(max_length=15, choices=PLAN_TYPE_CHOICES, default="medical")
    provider = models.CharField(max_length=150, blank=True)
    is_flex_credit_eligible = models.BooleanField(default=False)
    flex_credit_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Flex-credit value this plan carries when flex-eligible.")
    employer_cost_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    employee_cost_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_benefit_plans")
    coverage_tier_options = models.CharField(max_length=255, blank=True,
        default="employee_only", help_text="Comma-separated coverage tiers.")
    enrollment_window_start = models.DateField(null=True, blank=True)
    enrollment_window_end = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plan_type", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_bplan_tnt_active_idx"),
            models.Index(fields=["tenant", "plan_type"], name="hrm_bplan_tnt_type_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"

    @property
    def tier_list(self):
        """The coverage_tier_options CSV parsed into a clean list (for the enrollment form dropdown)."""
        return [t.strip() for t in (self.coverage_tier_options or "").split(",") if t.strip()]
