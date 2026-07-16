"""HRM 3.10 Leave Management — Type models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.10 Leave Management — LeaveType / LeaveAllocation / LeaveRequest
# ---------------------------------------------------------------------------
class LeaveType(TenantOwned):
    """Configurable leave catalog (3.10) — accrual / carry-forward / encashment policy."""

    ACCRUAL_CHOICES = [
        ("none", "No Accrual"),
        ("monthly", "Monthly Accrual"),
        ("annual", "Annual Grant"),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    is_paid = models.BooleanField(default=True)
    accrual_rule = models.CharField(max_length=20, choices=ACCRUAL_CHOICES, default="annual")
    accrual_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_balance = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="0 = unlimited")
    max_carry_forward = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Days carriable to next year (0 = none)")
    encashable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "code")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_lvtype_tenant_active_idx"),
        ]

    def clean(self):
        super().clean()
        if self.accrual_rule != "none" and (self.accrual_days or ZERO) <= ZERO:
            raise ValidationError({"accrual_days": "Accrual days must be greater than zero for an accruing leave type."})

    def __str__(self):
        return f"{self.name} ({self.code})"
