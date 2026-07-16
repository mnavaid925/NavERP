"""HRM 3.39 Compliance & Legal — Employmentcontract models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.39 Compliance & Legal — employment contracts (+ renewal chain), the versioned
# HR-policy library with per-employee acknowledgments, the grievance register, and
# the statutory/labour-law compliance register.
#
# **Disciplinary Actions needs NO new table** — it is already fully built as the 3.21
# ``WarningLetter`` (progressive discipline + issue/acknowledge + printable letter);
# the 3.39 bullet simply points at it. ``ComplianceRegister`` is deliberately SEPARATE
# from 3.15's ``StatutoryReturn`` (that one is payroll-tax remittance; this one is
# labour-law registers, muster rolls, wage registers and inspection reports).
#
# CONFIDENTIAL: ``Grievance`` is own-vs-admin (a complainant sees only what they filed;
# HR sees all) and ``is_anonymous`` masks the complainant from non-admins — mirroring
# the 3.20 Feedback anonymous-giver pattern.
# ---------------------------------------------------------------------------
class EmploymentContract(TenantNumbered):
    """An employment contract (``CTR-#####``) for an employee — type, dates, notice period, and an
    optional signed document. ``renewed_from`` chains a renewal back to the contract it replaces (the
    lifecycle history itself is recorded via the existing ``EmployeeLifecycleEvent(contract_renewal)``).
    Expiry is COMPUTED from ``end_date``, never stored."""

    NUMBER_PREFIX = "CTR"

    CONTRACT_TYPE_CHOICES = [
        ("permanent", "Permanent"),
        ("fixed_term", "Fixed Term"),
        ("probation", "Probation"),
        ("consultant", "Consultant"),
        ("intern", "Intern"),
        ("part_time", "Part Time"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("terminated", "Terminated"),
        ("renewed", "Renewed"),
    ]
    EXPIRING_SOON_DAYS = 60

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="contracts")
    contract_type = models.CharField(max_length=15, choices=CONTRACT_TYPE_CHOICES, default="permanent")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Blank for an open-ended contract.")
    probation_end_date = models.DateField(null=True, blank=True)
    notice_period_days = models.PositiveSmallIntegerField(default=30)
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="contracts")
    salary_structure = models.ForeignKey("hrm.EmployeeSalaryStructure", on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name="contracts")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    renewed_from = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="renewals")
    # WARNING: extension allowlist + size cap enforced in the form's clean (shared _validate_upload).
    # Keep MEDIA_ROOT outside the web root and serve with Content-Disposition: attachment in production.
    document = models.FileField(upload_to="hrm/contracts/%Y/%m/", null=True, blank=True)
    signed_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_ctr_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ctr_tnt_status_idx"),
            models.Index(fields=["tenant", "end_date"], name="hrm_ctr_tnt_end_idx"),
            models.Index(fields=["tenant", "-created_at"], name="hrm_ctr_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_contract_type_display()}" if self.number else self.get_contract_type_display()

    @property
    def days_to_expiry(self):
        """Days until end_date (negative once past). None for an open-ended contract."""
        if not self.end_date:
            return None
        return (self.end_date - timezone.localdate()).days

    @property
    def is_expiring_soon(self):
        """Active and within EXPIRING_SOON_DAYS of its end date (and not already past)."""
        days = self.days_to_expiry
        return bool(self.status == "active" and days is not None and 0 <= days <= self.EXPIRING_SOON_DAYS)

    @property
    def is_expired(self):
        days = self.days_to_expiry
        return bool(days is not None and days < 0)
