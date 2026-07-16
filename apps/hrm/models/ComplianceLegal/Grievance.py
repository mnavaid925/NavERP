"""HRM 3.39 Compliance & Legal — Grievance models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class Grievance(TenantNumbered):
    """An employee grievance / complaint (``GRV-#####``) with an investigation workflow.

    CONFIDENTIAL: own-vs-admin — a complainant sees only what they filed, HR sees everything. When
    ``is_anonymous`` is set the complainant is MASKED in the UI for non-admins (the identity is still stored
    so HR can investigate; mirrors the 3.20 Feedback anonymous-giver pattern). ``related_warning`` links to
    the existing 3.21 ``WarningLetter`` when a grievance results in disciplinary action."""

    NUMBER_PREFIX = "GRV"

    CATEGORY_CHOICES = [
        ("harassment", "Harassment"),
        ("discrimination", "Discrimination"),
        ("safety", "Workplace Safety"),
        ("compensation", "Compensation"),
        ("management", "Management / Supervision"),
        ("other", "Other"),
    ]
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("investigating", "Investigating"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("withdrawn", "Withdrawn"),
    ]
    OPEN_STATUSES = ("open",)  # editable/withdrawable by the complainant only while still open

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE,
                                 related_name="grievances_filed")  # the complainant
    is_anonymous = models.BooleanField(default=False,
                                       help_text="Mask the complainant from everyone except HR admins.")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="medium")
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open")
    assigned_investigator = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL,
                                              null=True, blank=True, related_name="grievances_investigating")
    related_policy = models.ForeignKey("hrm.HRPolicy", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="grievances")
    related_warning = models.ForeignKey("hrm.WarningLetter", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="grievances")
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    filed_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_grv_tnt_status_idx"),
            models.Index(fields=["tenant", "employee", "status"], name="hrm_grv_emp_status_idx"),
            models.Index(fields=["tenant", "severity"], name="hrm_grv_tnt_severity_idx"),
            models.Index(fields=["tenant", "-created_at"], name="hrm_grv_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.subject}" if self.number else self.subject

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES
