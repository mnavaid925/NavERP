"""HRM 3.37 Compensation & Benefits — Employeebenefitenrollment models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class EmployeeBenefitEnrollment(TenantNumbered):
    """A per-employee benefit election (``BEN-#####``) — opt-in/opt-out/waived against a BenefitPlan, tiered
    by coverage, effective-dated. Employee-owned (the ``employee`` FK reuses _ss_scope/_can_manage_own_child);
    an admin runs the enroll/waive/terminate lifecycle. Contributions default from the plan but are overridable.
    unique_together allows re-enrollment across periods but blocks duplicates for one effective_from."""

    NUMBER_PREFIX = "BEN"

    ELECTION_CHOICES = [
        ("opt_in", "Opt In"),
        ("opt_out", "Opt Out"),
        ("waived", "Waived"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("enrolled", "Enrolled"),
        ("waived", "Waived"),
        ("terminated", "Terminated"),
    ]
    OPEN_STATUSES = ("pending",)  # editable/deletable by the employee only while pending

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE,
                                 related_name="benefit_enrollments")
    plan = models.ForeignKey("hrm.BenefitPlan", on_delete=models.PROTECT, related_name="enrollments")
    election_choice = models.CharField(max_length=10, choices=ELECTION_CHOICES, default="opt_in")
    coverage_tier = models.CharField(max_length=50, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    employee_contribution = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    employer_contribution = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    enrolled_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="hrm_benefit_decisions")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"), ("tenant", "employee", "plan", "effective_from"))
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_ben_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ben_tnt_status_idx"),
            models.Index(fields=["tenant", "plan"], name="hrm_ben_tnt_plan_idx"),
            models.Index(fields=["tenant", "-created_at"], name="hrm_ben_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.plan.name}" if self.number else f"Enrollment ({self.plan_id})"

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES
