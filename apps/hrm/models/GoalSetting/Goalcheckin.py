"""HRM 3.18 Goal Setting — Goalcheckin models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class GoalCheckIn(TenantNumbered):
    """A timestamped progress-update log entry against a ``KeyResult`` (3.18.5 Goal
    Tracking). An append-only history row (no edit view) — Betterworks/Viva Goals/
    Quantive/Perdoo/Weekdone/Profit.co all treat check-ins as history, not a mutable
    field. On create it advances the parent ``KeyResult.current_value``."""

    NUMBER_PREFIX = "GCI"

    CONFIDENCE_CHOICES = [
        ("on_track", "On Track"),
        ("at_risk", "At Risk"),
        ("off_track", "Off Track"),
    ]

    key_result = models.ForeignKey("hrm.KeyResult", on_delete=models.CASCADE, related_name="checkins")
    checkin_date = models.DateField(default=timezone.localdate)
    value_at_checkin = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True,
                                           help_text="The KR value reported at this check-in (advances current_value).")
    confidence = models.CharField(max_length=15, choices=CONFIDENCE_CHOICES, default="on_track",
                                  help_text="Self-reported at check-in time (distinct from the derived KR health_status).")
    is_milestone_event = models.BooleanField(default=False,
                                             help_text="Marks a discrete milestone-completion event (milestone-type KRs).")
    comment = models.TextField(blank=True, help_text="Blockers / wins note.")
    created_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="goal_checkins", editable=False,
                                   help_text="Resolved from request.user in the view (allows manager overrides).")

    class Meta:
        ordering = ["-checkin_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "key_result"], name="hrm_gci_tenant_kr_idx"),
            models.Index(fields=["tenant", "checkin_date"], name="hrm_gci_tenant_date_idx"),
        ]

    def save(self, *args, **kwargs):
        is_create = self.pk is None
        super().save(*args, **kwargs)
        # The check-in is the single write path that advances the KR's current value.
        if is_create and self.value_at_checkin is not None and self.key_result_id:
            kr = self.key_result
            if kr.current_value != self.value_at_checkin:
                kr.current_value = self.value_at_checkin
                kr.save(update_fields=["current_value", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.key_result.title} · {self.get_confidence_display()}"
