"""HRM 3.11 Time Tracking — Timesheetentry models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class TimesheetEntry(TenantOwned):
    """A single time-log line on a ``Timesheet`` (3.11) — a day's hours against an optional
    ``accounting.Project`` (2.9 job-costing spine) + a free-text task. Billable value
    (``hours × billable_rate``) and utilization are **derived report aggregates**, never stored.
    ``task_description`` is free text until Project Management (Module 7) ships a Task/WBS model."""

    timesheet = models.ForeignKey("hrm.Timesheet", on_delete=models.CASCADE, related_name="entries")
    date = models.DateField()
    # Optional so admin / non-project time is loggable; SET_NULL keeps the line if the project is purged.
    project = models.ForeignKey("accounting.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_timesheet_entries")
    task_description = models.CharField(max_length=255, blank=True)
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    is_billable = models.BooleanField(default=True)
    billable_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["date"]
        indexes = [
            models.Index(fields=["tenant", "timesheet"], name="hrm_tse_tenant_ts_idx"),
            models.Index(fields=["tenant", "project"], name="hrm_tse_tenant_proj_idx"),
            models.Index(fields=["tenant", "date"], name="hrm_tse_tenant_date_idx"),
        ]

    def clean(self):
        super().clean()
        if (self.hours or ZERO) <= ZERO:
            raise ValidationError({"hours": "Hours must be greater than zero."})
        if self.timesheet_id and self.timesheet and self.date:
            ts = self.timesheet
            if ts.period_start and ts.period_end and not (ts.period_start <= self.date <= ts.period_end):
                raise ValidationError({"date": "Date must fall within the timesheet's period."})

    @property
    def billable_value(self):
        """Derived line value — only counts when the line is flagged billable."""
        return (self.hours or ZERO) * (self.billable_rate or ZERO) if self.is_billable else ZERO

    def __str__(self):
        return f"{self.timesheet.number if self.timesheet_id else '—'} · {self.date} · {self.hours}h"
