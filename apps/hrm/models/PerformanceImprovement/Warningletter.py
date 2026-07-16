"""HRM 3.21 Performance Improvement — Warningletter models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class WarningLetter(TenantNumbered):
    """A progressive-discipline warning letter (3.21) — verbal→written→final→suspension across
    attendance/conduct/performance/policy categories, with an issue→acknowledge workflow + an optional
    employee response. CONFIDENTIAL — visible only to the recipient, the issuer, or a tenant admin.
    Optionally linked to a PIP."""

    NUMBER_PREFIX = "WRN"

    LEVEL_CHOICES = [
        ("verbal", "Verbal Warning"),
        ("written", "Written Warning"),
        ("final", "Final Written Warning"),
        ("suspension", "Suspension"),
    ]
    CATEGORY_CHOICES = [
        ("attendance", "Attendance"),
        ("conduct", "Conduct"),
        ("performance", "Performance"),
        ("policy_violation", "Policy Violation"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("acknowledged", "Acknowledged"),
        ("expired", "Expired"),
    ]

    issued_to = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="warnings_received")
    issued_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="warnings_issued")
    level = models.CharField(max_length=15, choices=LEVEL_CHOICES, default="verbal")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="conduct")
    incident_date = models.DateField()
    description = models.TextField(help_text="Specific behaviours/actions (not vague criticism).")
    policy_reference = models.CharField(max_length=255, blank=True,
                                        help_text="Which policy/handbook section was violated.")
    related_pip = models.ForeignKey("hrm.PerformanceImprovementPlan", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="warning_letters")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledged_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="warnings_acknowledged", editable=False)
    employee_response = models.TextField(blank=True, help_text="The recipient's optional written response/rebuttal.")
    expiry_date = models.DateField(null=True, blank=True, help_text="When this warning goes stale (per company policy).")

    class Meta:
        ordering = ["-incident_date", "number"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "issued_to"], name="hrm_wrn_tenant_to_idx"),
            models.Index(fields=["tenant", "level"], name="hrm_wrn_tenant_level_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_wrn_tenant_status_idx"),
        ]

    def clean(self):
        if self.issued_to_id and self.issued_by_id and self.issued_to_id == self.issued_by_id:
            raise ValidationError({"issued_by": "The issuer can't be the recipient."})
        if self.expiry_date and self.incident_date and self.expiry_date <= self.incident_date:
            raise ValidationError({"expiry_date": "The expiry date must be after the incident date."})

    @property
    def is_expired(self):
        """Derived (never a stored flag) — mirrors ``MeetingActionItem.is_overdue``."""
        return bool(self.expiry_date and self.expiry_date < timezone.now().date())

    @property
    def prior_warnings(self):
        """Earlier warnings to the same employee (escalation context) — a DERIVED query, not a stored
        self-FK (per the research deferral)."""
        if not (self.issued_to_id and self.incident_date):
            return WarningLetter.objects.none()
        return (WarningLetter.objects.filter(
            tenant_id=self.tenant_id, issued_to_id=self.issued_to_id, incident_date__lt=self.incident_date)
            .exclude(pk=self.pk).order_by("-incident_date"))

    def __str__(self):
        who = self.issued_to.party.name if self.issued_to_id else "?"
        return f"{self.number} · {who} ({self.get_level_display()})"
