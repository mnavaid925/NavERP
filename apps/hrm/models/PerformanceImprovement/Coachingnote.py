"""HRM 3.21 Performance Improvement — Coachingnote models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class CoachingNote(TenantNumbered):
    """A manager's private coaching log (3.21) — the "manager journal". THE STRICTEST CONFIDENTIALITY IN
    THE CLUSTER: visible ONLY to the ``coach`` (author) + a tenant admin — NEVER to the coached
    ``employee`` at any stage (a whole-model clone of ``OneOnOneMeeting.manager_private_notes``'s
    read-gate). ``content`` is deliberately NOT added to ``core.crud._SENSITIVE_AUDIT_FIELDS`` — it's
    prose (not a bank/token-style secret), audit changes are already admin-only, and the coach/admin-only
    gate protects the read surface."""

    NUMBER_PREFIX = "CN"

    CATEGORY_CHOICES = [
        ("skill_development", "Skill Development"),
        ("behavior", "Behavior"),
        ("career_growth", "Career Growth"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="coaching_notes_about",
                                 help_text="The coached employee (who must NEVER see this note).")
    coach = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="coaching_notes_authored",
                              help_text="The author (manager/HRBP). Resolved server-side, not form-typed.")
    related_pip = models.ForeignKey("hrm.PerformanceImprovementPlan", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="coaching_notes")
    note_date = models.DateField(default=timezone.localdate, help_text="When the coaching moment happened.")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    content = models.TextField()

    class Meta:
        ordering = ["-note_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_cn_tenant_emp_idx"),
            models.Index(fields=["tenant", "coach"], name="hrm_cn_tenant_coach_idx"),
        ]

    def clean(self):
        if self.employee_id and self.coach_id and self.employee_id == self.coach_id:
            raise ValidationError({"employee": "You can't coach yourself."})

    def __str__(self):
        c = self.coach.party.name if self.coach_id else "?"
        e = self.employee.party.name if self.employee_id else "?"
        return f"{self.number} · {c} -> {e}"
