"""HRM 3.39 Compliance & Legal — Policyacknowledgment models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class PolicyAcknowledgment(TenantOwned):
    """One employee's acknowledgment of one policy version. Raised in bulk when a policy that requires
    acknowledgment is published; the employee flips it to ``acknowledged`` themselves."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("acknowledged", "Acknowledged"),
    ]

    policy = models.ForeignKey("hrm.HRPolicy", on_delete=models.CASCADE, related_name="acknowledgments")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE,
                                 related_name="policy_acknowledgments")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "policy", "employee")
        indexes = [
            models.Index(fields=["tenant", "policy"], name="hrm_pack_tnt_policy_idx"),
            models.Index(fields=["tenant", "employee", "status"], name="hrm_pack_emp_status_idx"),
            # Backs the default -created_at ordering on the unfiltered list. This is the fastest-growing
            # table of the five (one row per employee x per ack-required policy), so it needs it most.
            models.Index(fields=["tenant", "-created_at"], name="hrm_pack_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.employee} — {self.policy}" if self.employee_id and self.policy_id else "Acknowledgment"
