"""Sales 8.8 — `SalesPlanCycle` (`SPC-`) and its `ActivityGoal` children. Bullet 5's store.

**WHAT IS NEW HERE, PRECISELY.** Nothing in the project stores a *day* or a *week* with activity
**targets** on it. `crm.CrmTask` (CRM 1.5) stores individual to-dos; `sales.ForecastPeriod` (8.4)
frames revenue by quarter. Neither is a rep's day, and neither carries a goal count. `SalesPlanCycle`
is a named window with an owner, and `ActivityGoal` is one target metric inside it.

**ACTUALS ARE DERIVED, NEVER STORED (L37).** `ActivityGoal` holds `target_count` and nothing else.
"Calls made" is a `COUNT()` over `ActivityLog` in the cycle window filtered to the right channel;
"tasks completed" is a `COUNT()` over `crm.CrmTask`. Storing an `actual_count` would be a sixth
number to keep in step with the rows it summarises — and the first hand-edit, deleted task or clock
change would make it disagree with the ledger it claims to summarise. The board computes it on read.

**G12 IS THE L39 TRAP THIS MODEL EXISTS TO DEMONSTRATE.** `period_start` and `period_end` are both
individually valid on every single call — the form renders, the field validators pass, `save()`
succeeds. What is invalid is a **daily** cycle whose end is seven days after its start: "daily"
answers "what is one day?", and a seven-day span answers "what is a week?". Both fields pass; the
*pair* is a category error. This is the textbook L39 case and it is why the guard lives in
`clean()` and not only in the form.

**`closed_at` IS FROZEN AND SYSTEM-SET (L22),** following `crm.CrmTask.completed_at`'s exact shape:
stamped on the transition INTO closed, and **cleared** when a cycle is re-opened, with a pre-save
status probe so an ordinary re-save never re-stamps a closure that already happened.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantEventOwned, TenantNumbered

#: A day or a week. Bullet 5 names exactly these two; a monthly plan is 8.4's `ForecastPeriod`, and
#: shipping a third cadence here would put the two modules' period definitions in competition.
CADENCE_CHOICES = [
    ("daily", "Daily"),
    ("weekly", "Weekly"),
]

STATUS_CHOICES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("closed", "Closed"),
]

#: `suggestion_mode` records WHO decided the next-best-actions on this plan are trustworthy — not
#: whether a model produced them. 8.8 ships deterministic rules (see `views/…/Boards.py`); nothing here
#: pretends to be a language model, and `manual` is the honest default for a workspace that has not
#: opted in.
SUGGESTION_MODE_CHOICES = [
    ("manual", "Manual"),
    ("assisted", "Assisted"),
    ("automatic", "Automatic"),
]

#: The metrics a goal can be set against. Every one is COUNT-able over a table that already exists —
#: four of the five over `sales.ActivityLog` (filtered by the CRM 1.5 channel it attributes) and one
#: over `crm.CrmTask`. `logged_total` is the catch-all rollup of all four.
ACTIVITY_METRIC_CHOICES = [
    ("call", "Calls Made"),
    ("email", "Emails Sent"),
    ("meeting", "Meetings Held"),
    ("task", "Tasks Completed"),
    ("logged_total", "All Activities"),
]

#: `logged_total` has no single channel, so it is excluded from the per-channel `actual_for` mapping
#: and summed instead. A goal on it is the honest "log at least N things" target.
PER_CHANNEL_METRICS = ["call", "email", "meeting", "task"]

#: A goal above this is a data-entry slip. Every product in the research catalog tops a daily activity
#: goal in the low hundreds; 1000 is generous but still refuses a stray zero-stripped integer.
MAX_TARGET_COUNT = 1000


class SalesPlanCycle(TenantNumbered):
    """One rep's (or one territory's) day or week, with activity goals and a closed period."""

    NUMBER_PREFIX = "SPC"

    CADENCE_CHOICES = CADENCE_CHOICES
    STATUS_CHOICES = STATUS_CHOICES
    SUGGESTION_MODE_CHOICES = SUGGESTION_MODE_CHOICES

    name = models.CharField(max_length=160)
    cadence = models.CharField(max_length=10, choices=CADENCE_CHOICES, default="weekly")
    period_start = models.DateField()
    period_end = models.DateField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_plan_cycles",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_plan_cycles",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    suggestion_mode = models.CharField(
        max_length=10, choices=SUGGESTION_MODE_CHOICES, default="manual"
    )
    notes = models.TextField(blank=True)
    # ---- FROZEN, SYSTEM-SET (L22) — never on a form, written only by save()/the close verb ------
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-period_start", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "owner", "period_start", "cadence"],
                name="sales_spc_tnt_owner_start_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_spc_tnt_status_idx"),
            models.Index(fields=["tenant", "period_start"], name="sales_spc_tnt_start_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        # G11 — an end before the start is a plain inverted range.
        if self.period_start and self.period_end and self.period_end < self.period_start:
            errors["period_end"] = (
                f"The period ends {self.period_start - self.period_end} day(s) before it starts."
            )
        # G12 — the L39 pair guard. Individually valid, jointly a category error.
        if (
            self.cadence == "daily"
            and self.period_start
            and self.period_end
            and self.period_end != self.period_start
        ):
            errors["period_end"] = (
                "A daily plan covers one day, so its end date must be its start date "
                f"({self.period_start:%d %b %Y}). Use a weekly plan to span several days."
            )
        if self.weekly_period_is_not_a_week:
            errors["period_start"] = (
                "A weekly plan covers seven days, so its end date must be six days after its start."
            )
        if errors:
            raise ValidationError(errors)

    @property
    def weekly_period_is_not_a_week(self):
        """True when a ``weekly`` cycle spans something other than seven days.

        The mirror of G12, and deliberately a *property* rather than a duplicated inline comparison:
        the form, the detail page and the board all ask the same question and must get one answer.
        """
        if self.cadence != "weekly" or not self.period_start or not self.period_end:
            return False
        return (self.period_end - self.period_start).days != 6

    def actual_for(self, metric, as_of=None):
        """The ACTUAL count for one metric over this cycle's window. DERIVED, never stored (L37).

        Reads `sales.ActivityLog` for the four per-channel metrics (attribution carries the CRM 1.5
        channel, so no second channel vocabulary is needed) and `crm.CrmTask` for tasks. `as_of`
        narrows the window's upper bound, which is what lets a *closed* cycle report the same numbers
        forever while an open one grows.
        """
        from apps.crm.models import CrmTask
        from apps.sales.models.SalesActivityTaskManagement.ActivityLogs import ActivityLog

        start, end = self.period_start, self.period_end
        if as_of is not None:
            end = min(end, as_of) if end else as_of
        if not start or not end:
            return 0
        if metric == "task":
            return CrmTask.objects.filter(
                tenant=self.tenant,
                status="done",
                due_date__gte=start,
                due_date__lte=end,
            ).count()
        if metric == "logged_total":
            return ActivityLog.objects.filter(
                tenant=self.tenant, occurred_on__gte=start, occurred_on__lte=end
            ).count()
        if metric not in PER_CHANNEL_METRICS:
            return 0
        # The channel lives on the CRM 1.5 log, so this is a JOIN — `communication_log__channel` —
        # not a column on 8.8's own model. That join is the visible cost of the L36 ruling, and it
        # is exactly why `occurred_on` is denormalised onto ActivityLog: the date half of the filter
        # stays on an index even though the channel half has to cross the table.
        return ActivityLog.objects.filter(
            tenant=self.tenant,
            occurred_on__gte=start,
            occurred_on__lte=end,
            communication_log__channel=metric,
        ).count()

    def progress_for(self, goal, as_of=None):
        """``(actual, target, percent_complete)`` for one goal. Returns ``(0, 0, None)`` for an
        unset goal so a template can render a row without special-casing."""
        actual = self.actual_for(goal.metric, as_of=as_of)
        target = goal.target_count or 0
        if not target:
            return actual, target, None
        return actual, target, min(100, round((actual / target) * 100))

    def save(self, *args, **kwargs):
        # L22, in the exact shape `crm.CrmTask.completed_at` uses. The probe runs BEFORE the write so
        # the stamp reflects the TRANSITION, not the current value of `self.status` — without it a
        # plain re-save of an already-closed cycle would silently restamp `closed_at` forever.
        previous_status = (
            type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if self.pk
            else None
        )
        if self.status == "closed":
            if self.closed_at is None:
                self.closed_at = timezone.now()
        else:
            self.closed_at = None
        if self.pk and previous_status is not None:
            fields = kwargs.get("update_fields")
            extra = {"closed_at", "updated_at"}
            if fields is not None:
                kwargs["update_fields"] = set(fields) | extra
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number or '—'} · {self.name}"


class ActivityGoal(TenantEventOwned):
    """One activity target inside a plan cycle.

    Holds ``target_count`` and nothing else — no ``actual_count``, no ``attainment_percent``. Both
    are derived by ``SalesPlanCycle.progress_for`` / ``actual_for`` on read (L37).
    """

    METRIC_CHOICES = ACTIVITY_METRIC_CHOICES
    MAX_TARGET_COUNT = MAX_TARGET_COUNT

    cycle = models.ForeignKey(
        "sales.SalesPlanCycle",
        on_delete=models.CASCADE,
        related_name="goals",
    )
    metric = models.CharField(max_length=16, choices=ACTIVITY_METRIC_CHOICES)
    target_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(MAX_TARGET_COUNT)],
        help_text="How many of these to aim for in the cycle's window.",
    )

    class Meta:
        ordering = ["cycle_id", "metric"]
        constraints = [
            models.UniqueConstraint(fields=["cycle", "metric"], name="sales_agoal_cycle_metric_uniq"),
        ]

    def clean(self):
        super().clean()
        if (
            self.target_count is not None
            and not 0 <= self.target_count <= MAX_TARGET_COUNT
        ):
            raise ValidationError(
                {"target_count": (
                    f"A goal must be between 0 and {MAX_TARGET_COUNT}."
                )}
            )

    def __str__(self):
        return f"{self.get_metric_display()}: {self.target_count}"