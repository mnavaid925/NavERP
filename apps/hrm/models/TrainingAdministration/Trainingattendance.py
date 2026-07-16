"""HRM 3.24 Training Administration — Trainingattendance models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class TrainingAttendance(TenantOwned):
    """Per-session-per-employee attendance + completion (3.24 Attendance Tracking). A ``walk_in``
    status with ``nomination=None`` captures day-of walk-ins; ``completion_status`` is independent of
    presence (an admin can mark completion). Unique per (tenant, session, employee)."""

    ATTENDANCE_STATUS_CHOICES = [
        ("registered", "Registered"),
        ("present", "Present"),
        ("absent", "Absent"),
        ("partial", "Partial"),
        ("walk_in", "Walk-in"),
    ]
    COMPLETION_STATUS_CHOICES = [
        ("not_completed", "Not Completed"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    session = models.ForeignKey("hrm.TrainingSession", on_delete=models.PROTECT, related_name="attendance_records")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="training_attendance")
    nomination = models.ForeignKey("hrm.TrainingNomination", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="attendance_records", help_text="Links back when nominated.")
    attendance_status = models.CharField(max_length=10, choices=ATTENDANCE_STATUS_CHOICES, default="registered")
    completion_status = models.CharField(max_length=15, choices=COMPLETION_STATUS_CHOICES, default="not_completed")
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-session__start_datetime", "employee__party__name"]
        unique_together = ("tenant", "session", "employee")
        indexes = [
            models.Index(fields=["tenant", "session"], name="hrm_tatt_tenant_session_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_tatt_tenant_emp_idx"),
            models.Index(fields=["tenant", "attendance_status"], name="hrm_tatt_tenant_status_idx"),
            models.Index(fields=["tenant", "completion_status"], name="hrm_tatt_tenant_comp_idx"),
        ]

    def clean(self):
        if self.check_in_at and self.check_out_at and self.check_out_at < self.check_in_at:
            raise ValidationError({"check_out_at": "Check-out can't be before check-in."})
        if self.nomination_id and (self.nomination.session_id != self.session_id
                                   or self.nomination.employee_id != self.employee_id):
            raise ValidationError({"nomination": "This nomination is for a different session/employee."})

    def __str__(self):
        return f"{self.employee} · {self.session} ({self.get_attendance_status_display()})"
