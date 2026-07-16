"""HRM 3.41 Employee Engagement & Wellbeing — Wellbeingparticipation models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class WellbeingParticipation(TenantOwned):
    """An employee's RSVP / attendance / volunteering-log for a ``WellbeingProgram`` — the nested child
    (form-only, no standalone list), added from the program's detail page. ``notes`` is SCHEDULING/status
    text ONLY, never clinical content (enforced by help_text + review, not an ML filter)."""

    PARTICIPATION_STATUS_CHOICES = [
        ("registered", "Registered"),
        ("attended", "Attended"),
        ("completed", "Completed"),
        ("no_show", "No Show"),
        ("withdrawn", "Withdrawn"),
    ]
    _CLOSED_STATUSES = ("completed",)

    program = models.ForeignKey("hrm.WellbeingProgram", on_delete=models.CASCADE,
                                related_name="participations")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
                                 related_name="wellbeing_participations")
    status = models.CharField(max_length=12, choices=PARTICIPATION_STATUS_CHOICES, default="registered")
    points_earned = models.PositiveIntegerField(null=True, blank=True,
                                                help_text="Admin-awarded — not self-settable by employees.")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True,
                             help_text="Scheduling/status notes only — never clinical or counseling content.")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "program", "employee")
        indexes = [
            # (tenant, program) is already the leftmost prefix of the unique_together index above — no
            # separate index for it. Only (tenant, employee) needs its own.
            models.Index(fields=["tenant", "employee"], name="hrm_wbpart_tnt_employee_idx"),
        ]

    def __str__(self):
        # WARNING (security): str(obj) becomes AuditLog.target verbatim (apps/core/utils.write_audit_log),
        # and any tenant admin can browse /core/audit-logs/. For a CONFIDENTIAL program that would re-expose
        # exactly the per-employee EAP participation the module keeps aggregate-only — so never name the
        # employee here when the program is confidential.
        if self.program_id and self.program.is_confidential:
            return f"Confidential participation #{self.pk or '?'}"
        return f"{self.employee} @ {self.program_id} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if self.status in self._CLOSED_STATUSES:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        return super().save(*args, **kwargs)
