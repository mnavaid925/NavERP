"""Projects 7.3 Resource Management — ResourceTimeEntry [RTE-]: one day's project time.

One flat row per person-day — the *thinnest* projects-side time log that makes
actuals-to-plan joinable to ``projects.Project``. It is deliberately NOT a fourth timesheet:
the payroll-grade weekly header + approval workflow is ``hrm.Timesheet``/``TimesheetEntry``
(3.11), whose ``project`` FK points at the 2.9 ``accounting.Project`` stand-in and therefore
cannot join this module's projects; ``crm.Timesheet`` [TS-] is the 1.8 pre-spine stand-in.
Status moves only through the verbs (draft → submitted → approved/rejected) — approval stamps
are written exactly once by the verbs and never rewound: the form excludes them, and
approved/rejected rows refuse edit and delete at the view.

NO billable flag, NO rates, NO money columns (7.11/7.4/7.15, L29). No header model — the
weekly lens is a regroup over the flat rows, and ``rte_approve_week`` is the bulk verb.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ResourceTimeEntry(TenantNumbered):
    """One day's logged hours against a project (and optionally a work package)."""

    NUMBER_PREFIX = "RTE"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    resource = models.ForeignKey(
        "projects.ResourceProfile", on_delete=models.CASCADE, related_name="time_entries",
        help_text="An entry dies with its person (mirrors hrm.Timesheet.employee).")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="time_entries",
        help_text="Non-project time (training, internal) is loggable.")
    project_task = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="time_entries",
        help_text="Optional work package — 7.8 extends the task in place with execution fields.")
    entry_date = models.DateField()
    hours = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Positive — 0.01 is the smallest loggable unit.")
    task_description = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default="draft",
        help_text="Verb-driven — submit/approve/reject are the only writers.")
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="approved_time_entries")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True, help_text="The rejection reason, when rejected.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["resource_id", "-entry_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "resource", "entry_date"], name="rte_tnt_res_date_idx"),
            models.Index(fields=["tenant", "project", "entry_date"], name="rte_tnt_prj_date_idx"),
            models.Index(fields=["tenant", "status"], name="rte_tnt_status_idx"),
        ]

    def __str__(self):
        # No FK dereference — the admin changelist calls str() once per row.
        return f"{self.number} · {self.hours}h on {self.entry_date:%Y-%m-%d}"

    @property
    def iso_year(self):
        return self.entry_date.isocalendar()[0]

    @property
    def iso_week(self):
        return self.entry_date.isocalendar()[1]

    @property
    def week_key(self):
        """One key = one person-week — the regroup key for the weekly lens.

        resource_id (not the object) so entries of two people in the same week never share a
        group, and the person-week blocks stay contiguous under Meta.ordering.
        """
        return f"{self.resource_id}:{self.iso_year}-W{self.iso_week:02d}"
