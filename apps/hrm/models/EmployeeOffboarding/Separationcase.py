"""HRM 3.4 Employee Offboarding — Separationcase models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class SeparationCase(TenantNumbered):
    """The master offboarding record (3.4) — one per departure event. Drives the
    resignation → approval → clearance → settlement → completion lifecycle.
    ``expected_last_working_day`` is derived in ``save()`` (notice_start_date + notice_period_days);
    ``all_mandatory_cleared`` gates the F&F release. The relieving/experience letters are generated
    from this record's fields (no separate table) and only stamp the generated-at timestamp."""

    NUMBER_PREFIX = "SEP"

    SEPARATION_TYPE_CHOICES = [
        ("resignation", "Resignation"),
        ("termination", "Termination"),
        ("layoff", "Layoff"),
        ("retirement", "Retirement"),
        ("contract_end", "End of Contract"),
        ("deceased", "Deceased"),
    ]
    EXIT_REASON_CHOICES = [
        ("better_opportunity", "Better Opportunity"),
        ("compensation", "Compensation"),
        ("career_growth", "Career Growth"),
        ("relocation", "Relocation"),
        ("health", "Health"),
        ("personal", "Personal"),
        ("retirement", "Retirement"),
        ("performance", "Performance"),
        ("policy_violation", "Policy Violation"),
        ("other", "Other"),
    ]
    NOTICE_BUYOUT_CHOICES = [
        ("none", "None"),
        ("pay_in_lieu", "Pay in Lieu of Notice"),
        ("recover", "Recover Shortfall"),
    ]
    # Lifecycle: approving a case generates its clearance checklist and moves it straight to
    # ``in_clearance`` (there is no standalone "approved" holding state).
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("in_clearance", "In Clearance"),
        ("cleared", "Cleared"),
        ("settled", "Settled"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
    ]
    # Statuses at which the relieving/experience letters may be generated (clearance done).
    LETTER_READY_STATUSES = ("cleared", "settled", "completed")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="separation_cases")
    separation_type = models.CharField(max_length=20, choices=SEPARATION_TYPE_CHOICES, default="resignation")
    exit_reason = models.CharField(max_length=30, choices=EXIT_REASON_CHOICES, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    resignation_letter = models.FileField(upload_to="hrm/offboarding/letters/%Y/%m/", null=True, blank=True)
    notice_period_days = models.PositiveIntegerField(default=30)
    notice_start_date = models.DateField(null=True, blank=True, help_text="Day 1 of the notice period (usually the resignation date).")
    # Derived in save() — never hand-edited.
    expected_last_working_day = models.DateField(null=True, blank=True, editable=False)
    actual_last_working_day = models.DateField(null=True, blank=True, help_text="HR-confirmed last working day.")
    notice_buyout_type = models.CharField(max_length=20, choices=NOTICE_BUYOUT_CHOICES, default="none")
    requires_kt = models.BooleanField(default=True, help_text="Adds a Knowledge-Transfer clearance line on approval.")
    # Workflow-owned (set only by the audited workflow actions, never on the form).
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", editable=False)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_approved_separations", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejection_reason = models.TextField(blank=True)
    withdrawal_reason = models.TextField(blank=True)
    relieving_letter_generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    relieving_letter_generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_relieving_letters_generated", editable=False)
    experience_letter_generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    experience_letter_generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_experience_letters_generated", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_sep_tenant_status_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_sep_tenant_emp_idx"),
            models.Index(fields=["tenant", "separation_type"], name="hrm_sep_tenant_type_idx"),
            # actual_last_working_day is the primary date filter for the 3.28/3.32 attrition,
            # headcount-trend and turnover queries (hit on every analytics-dashboard render).
            models.Index(fields=["tenant", "actual_last_working_day"], name="hrm_sep_tenant_lwd_idx"),
        ]

    @property
    def all_mandatory_cleared(self):
        """True when every *mandatory* clearance line is cleared/NA — the gate for marking the case
        cleared and generating letters. A case with no mandatory lines reads as cleared (nothing
        blocks)."""
        return not (self.clearance_items.filter(is_mandatory=True)
                    .exclude(status__in=("cleared", "not_applicable")).exists())

    def save(self, *args, **kwargs):
        # Expected LWD is always derived from the notice window — never hand-edited. Workflow actions
        # save with an explicit ``update_fields`` list; make sure the recomputed value is persisted
        # (and not silently dropped) by adding the column to that list when it isn't already there.
        if self.notice_start_date and self.notice_period_days:
            self.expected_last_working_day = self.notice_start_date + timedelta(days=self.notice_period_days)
        else:
            self.expected_last_working_day = None
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "expected_last_working_day" not in update_fields:
            kwargs["update_fields"] = list(update_fields) + ["expected_last_working_day"]
        return super().save(*args, **kwargs)

    def __str__(self):
        name = self.employee.name if self.employee_id else "—"
        return f"{self.number} · {name} ({self.get_status_display()})"
