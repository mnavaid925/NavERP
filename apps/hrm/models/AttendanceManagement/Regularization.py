"""HRM 3.9 Attendance Management — Regularization models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class AttendanceRegularization(TenantNumbered):
    """Employee-raised request to correct an attendance punch (3.9) — missed/forgotten/erroneous
    check-in-out. Approval workflow ``draft → pending → approved/rejected`` (+ ``cancelled``),
    mirroring ``LeaveRequest``. On approval the requested times are written back onto the linked
    ``AttendanceRecord`` and its status set to ``regularized`` (see ``views.attendanceregularization_approve``)."""

    NUMBER_PREFIX = "REG"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    REASON_TYPE_CHOICES = [
        ("missed_punch", "Missed Punch"),
        ("forgot_checkin", "Forgot Check-In"),
        ("forgot_checkout", "Forgot Check-Out"),
        ("wrong_time", "Wrong Time Recorded"),
        ("on_duty", "On Official Duty"),
        ("work_from_home", "Work From Home"),
        ("system_error", "System / Device Error"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="attendance_regularizations")
    # The record being corrected. SET_NULL (not CASCADE) keeps the regularization audit trail even if
    # the attendance row is later purged; optional so an employee can raise one before any row exists.
    attendance_record = models.ForeignKey("hrm.AttendanceRecord", on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name="regularizations")
    date = models.DateField()
    reason_type = models.CharField(max_length=20, choices=REASON_TYPE_CHOICES, default="missed_punch")
    requested_check_in = models.TimeField(null=True, blank=True)
    requested_check_out = models.TimeField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_regularization_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_reg_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_reg_tenant_status_idx"),
            models.Index(fields=["tenant", "date"], name="hrm_reg_tenant_date_idx"),
        ]

    def clean(self):
        super().clean()
        # A linked record must belong to the same employee — otherwise approval would rewrite
        # another person's punch.
        if self.attendance_record_id and self.employee_id and self.attendance_record.employee_id != self.employee_id:
            raise ValidationError({"attendance_record": "The linked attendance record belongs to a different employee."})
        if not (self.requested_check_in or self.requested_check_out):
            raise ValidationError({"requested_check_in": "Provide at least one of requested check-in / check-out."})

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.date} · {self.get_status_display()}"
