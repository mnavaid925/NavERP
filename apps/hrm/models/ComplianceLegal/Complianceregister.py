"""HRM 3.39 Compliance & Legal — Complianceregister models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class ComplianceRegister(TenantNumbered):
    """A statutory / labour-law compliance record (``CMP-#####``) — a labour-law requirement, a muster roll,
    a wage register, an inspection report, or a licence/permit. Deliberately SEPARATE from 3.15's
    ``StatutoryReturn`` (payroll-tax remittance). ``is_overdue`` is COMPUTED from ``due_date`` + status."""

    NUMBER_PREFIX = "CMP"

    REGISTER_TYPE_CHOICES = [
        ("labor_law_requirement", "Labour Law Requirement"),
        ("muster_roll", "Muster Roll"),
        ("wage_register", "Wage Register"),
        ("inspection_report", "Inspection Report"),
        ("license_permit", "Licence / Permit"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("filed", "Filed"),
        ("not_applicable", "Not Applicable"),
    ]

    register_type = models.CharField(max_length=25, choices=REGISTER_TYPE_CHOICES,
                                     default="labor_law_requirement")
    title = models.CharField(max_length=255)
    jurisdiction = models.CharField(max_length=150, blank=True, help_text="e.g. Karnataka, India / Federal.")
    authority = models.CharField(max_length=150, blank=True, help_text="The issuing/inspecting authority.")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    filed_on = models.DateField(null=True, blank=True)
    inspector_name = models.CharField(max_length=150, blank=True)
    findings = models.TextField(blank=True)
    document = models.FileField(upload_to="hrm/compliance/%Y/%m/", null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "register_type"], name="hrm_cmp_tnt_type_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_cmp_tnt_status_idx"),
            models.Index(fields=["tenant", "due_date"], name="hrm_cmp_tnt_due_idx"),
            models.Index(fields=["tenant", "-created_at"], name="hrm_cmp_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}" if self.number else self.title

    @property
    def is_overdue(self):
        """Past its due date and not yet filed / marked not-applicable."""
        if not self.due_date or self.status in ("filed", "not_applicable"):
            return False
        return self.due_date < timezone.localdate()
