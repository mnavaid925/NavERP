"""HRM 3.38 Talent Management & Succession — Successionplan models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class SuccessionPlan(TenantNumbered):
    """A succession bench for one critical role (``SPL-#####``) — the incumbent, the vacancy risk, and a
    ranked list of SuccessionCandidates. ``bench_strength`` is COMPUTED from the candidates' readiness."""

    NUMBER_PREFIX = "SPL"

    VACANCY_RISK_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed"),
    ]

    critical_role = models.ForeignKey("hrm.Designation", on_delete=models.PROTECT,
                                      related_name="succession_plans")
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="hrm_succession_plans")
    incumbent = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="succession_plans_held")
    vacancy_risk = models.CharField(max_length=10, choices=VACANCY_RISK_CHOICES, default="medium")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    review_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_spl_tnt_status_idx"),
            models.Index(fields=["tenant", "vacancy_risk"], name="hrm_spl_tnt_risk_idx"),
            models.Index(fields=["tenant", "critical_role"], name="hrm_spl_tnt_role_idx"),
        ]

    def __str__(self):
        role = self.critical_role.name if self.critical_role_id else "role"
        return f"{self.number} - {role}" if self.number else f"Succession: {role}"

    @property
    def ready_now_count(self):
        """Uses the ``_ready_now_count`` annotation when present (the list view annotates it — otherwise
        rendering bench strength for N rows would fire 2N COUNT queries)."""
        annotated = getattr(self, "_ready_now_count", None)
        if annotated is not None:
            return annotated
        return self.candidates.filter(readiness="ready_now").count()

    @property
    def candidate_count(self):
        annotated = getattr(self, "_candidate_count", None)
        if annotated is not None:
            return annotated
        return self.candidates.count()

    @property
    def bench_strength(self):
        """strong (2+ ready now) / moderate (1 ready now) / weak (candidates but none ready) / none."""
        if not self.candidate_count:
            return "none"
        ready = self.ready_now_count
        if ready >= 2:
            return "strong"
        if ready == 1:
            return "moderate"
        return "weak"
