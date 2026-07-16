"""HRM 3.41 Employee Engagement & Wellbeing — Flexibleworkarrangement models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class FlexibleWorkArrangement(TenantNumbered):
    """A Work-Life-Balance request (remote/hybrid/compressed/flextime/part-time) — a structural clone of
    3.35 TravelRequest that reuses _hr_request_submit/_cancel/_approve/_reject/_edit/_delete VERBATIM."""

    NUMBER_PREFIX = "FWA"

    ARRANGEMENT_TYPE_CHOICES = [
        ("remote", "Fully Remote"),
        ("hybrid", "Hybrid"),
        ("compressed_week", "Compressed Week"),
        ("flextime", "Flexible Hours"),
        ("part_time", "Part Time"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]
    OPEN_STATUSES = ("draft", "pending")  # required by _hr_request_edit/_delete/_cancel

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE,
                                 related_name="flexible_work_arrangements")
    arrangement_type = models.CharField(max_length=20, choices=ARRANGEMENT_TYPE_CHOICES, default="remote")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Blank = open-ended / permanent.")
    days_per_week_remote = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Only for Remote/Hybrid — days worked remotely per week (1–5).")
    reason = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_fwa_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_fwa_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_fwa_tnt_status_idx"),
            models.Index(fields=["tenant", "arrangement_type"], name="hrm_fwa_tnt_type_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_arrangement_type_display()}" if self.number \
            else self.get_arrangement_type_display()
