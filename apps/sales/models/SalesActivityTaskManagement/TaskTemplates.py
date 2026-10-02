"""Sales 8.8 — `TaskTemplate` (`TTPL-`) and its `TaskTemplateStep` playbook children.

**WHAT IS NEW HERE, PRECISELY.** `crm.CrmTask` (CRM 1.5) already does *single-task recurrence*: its
`save()` watches for the open→done transition and calls `_spawn_next_occurrence()`, clamping monthly
dates with `calendar.monthrange` and refusing to spawn a duplicate occurrence at the same next due
date. That is one task moving forward. It is **not** a template.

A template is a **named playbook that fans one definition out to many tasks against many targets** —
"every fortnight, call every account in EMEA under £50k ARR; two days before each call, email the
economic buyer; day of the call, log the meeting". Nothing in `apps/crm` does that, so `TaskTemplate`
is genuinely un-owned and 8.8 adds it rather than forking anything.

**IT GENERATES `crm.CrmTask` ROWS. IT NEVER DECLARES ONE.** `task_type` and `priority` are re-used
through the **imported** `CrmTask.TYPE_CHOICES` / `CrmTask.PRIORITY_CHOICES` lists (the `ROUTING_
OPERATORS` rule 8.7 followed against 8.1) so a generated task ranks identically to a hand-typed one.
`TaskTemplateStep` is a plain child row (no auto-number), the same shape as `crm.EventAttendee` and
`crm.CaseComment`.

**THE RECEIPT IS FROZEN (L22).** `last_generated_on` and `generated_count` are `editable=False`, so
they are auto-excluded from every form; the `task_template_generate` POST view is their only writer.
A template's own page then states plainly how many tasks its last run produced and on what date —
which is also what makes the idempotency guard (research §8 G16) observable rather than merely claimed.

**THE THREE GUARDS ARE THE L39 TRAPS.**
* G6 — `cadence="once"` with `cadence_interval=7` is two individually valid fields describing a
  contradiction ("one-off" and "every seven").
* G8/G9 — `target_type` must agree with `territory`, in **both** directions. "Every account in a
  territory" is unreachable without the territory, and "every open opportunity" plus a territory is
  ambiguous about which of the two narrows the set.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.crm.models import CrmTask
from apps.sales.models._base import TenantEventOwned, TenantNumbered

#: The cadences a playbook can repeat on. `biweekly` is spelled out rather than left as an
#: `interval=2` special case because "every two weeks" and "twice a week" are different instructions
#: and an author picking `weekly`/`interval=2` is usually asking for the first of those.
CADENCE_CHOICES = [
    ("once", "One-Off"),
    ("daily", "Daily"),
    ("weekly", "Weekly"),
    ("biweekly", "Every Two Weeks"),
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
]

#: What the fan-out iterates over. `territory` is the reason G9 exists: it is the only one of the
#: three that NEEDS a territory, and needing it is exactly what makes the other two ambiguous with it.
TARGET_TYPE_CHOICES = [
    ("opportunity", "Opportunity"),
    ("account", "Account"),
    ("territory", "Territory"),
]

#: Interval bounds. 12 covers quarterly×4 and monthly×12; beyond that an author almost certainly
#: meant a yearly or ad-hoc cycle, which is what `once` + a manual run is for.
MAX_CADENCE_INTERVAL = 12
#: A playbook step more than a year either side of its anchor is a typo, not a plan.
MAX_STEP_OFFSET_DAYS = 365


class TaskTemplate(TenantNumbered):
    """A named, repeating playbook that materialises ``crm.CrmTask`` rows when generated."""

    NUMBER_PREFIX = "TTPL"

    #: IMPORTED from CRM 1.5 — a generated task ranks exactly like a hand-typed one.
    TASK_TYPE_CHOICES = CrmTask.TYPE_CHOICES
    PRIORITY_CHOICES = CrmTask.PRIORITY_CHOICES
    CADENCE_CHOICES = CADENCE_CHOICES
    TARGET_TYPE_CHOICES = TARGET_TYPE_CHOICES
    #: Re-used by `SalesPlanCycle`'s sibling planning views — one cadence vocabulary in the app.
    CADENCE_INTERVAL_MAX = MAX_CADENCE_INTERVAL

    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, default="todo")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    cadence = models.CharField(max_length=10, choices=CADENCE_CHOICES, default="weekly")
    cadence_interval = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_CADENCE_INTERVAL)],
        help_text="Repeat every N cadences — 2 on 'Every Two Weeks' is 2.",
    )
    default_offset_days = models.SmallIntegerField(
        default=0,
        validators=[MinValueValidator(-MAX_STEP_OFFSET_DAYS), MaxValueValidator(MAX_STEP_OFFSET_DAYS)],
        help_text="Days from the cycle anchor to each generated task's due date.",
    )
    target_type = models.CharField(
        max_length=20, choices=TARGET_TYPE_CHOICES, default="opportunity"
    )
    activity_type = models.ForeignKey(
        "sales.ActivityType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="task_templates",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_task_templates",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_task_templates",
    )
    is_active = models.BooleanField(default=True)
    # ---- FROZEN RECEIPT (L22) — written only by the `task_template_generate` POST view ---------
    last_generated_on = models.DateField(null=True, blank=True, editable=False)
    generated_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="sales_ttpl_tenant_name_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="sales_ttpl_tnt_active_idx"),
            models.Index(fields=["tenant", "target_type"], name="sales_ttpl_tnt_target_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        # G6 — a one-off with an interval is a contradiction between two valid fields.
        if self.cadence == "once" and self.cadence_interval != 1:
            errors["cadence_interval"] = (
                "A one-off template runs once, so its interval must be 1. "
                "Pick a repeating cadence if you want it to come back."
            )
        # G7 — re-checked at the model level as well as by the field validator.
        if self.cadence_interval is not None and not 1 <= self.cadence_interval <= MAX_CADENCE_INTERVAL:
            errors["cadence_interval"] = (
                f"The interval must be between 1 and {MAX_CADENCE_INTERVAL}."
            )
        # G8 / G9 — the agreement guard, enforced in BOTH directions.
        if self.target_type == "territory" and not self.territory_id:
            errors["territory"] = (
                "A territory-targeted template needs the territory to fan out over. "
                "Choose one, or change the target type."
            )
        elif self.target_type != "territory" and self.territory_id:
            errors["territory"] = (
                f"This template targets {self.get_target_type_display().lower()}s, so naming a "
                "territory as well would say which of the two narrows the set. "
                "Clear the territory, or change the target type to Territory."
            )
        if errors:
            raise ValidationError(errors)

    @property
    def is_generatable(self):
        """Can this template actually produce tasks today? Used by the detail page's caveat list."""
        if not self.is_active:
            return False, "This template is inactive, so a run would refuse it."
        if not self.steps.exists():
            return False, "This template has no steps, so a run would produce nothing."
        return True, ""

    @property
    def cadence_display(self):
        """A readable repeat instruction — 'Every Two Weeks' / 'Weekly' / 'One-Off'.

        Derived rather than a column: a stored cadence label would need re-writing every time the
        interval changed, which is the same drift L37 forbids for stored balances.
        """
        if self.cadence == "once" or self.cadence_interval == 1:
            return self.get_cadence_display()
        unit = self.get_cadence_display().rstrip("ly") if self.cadence != "biweekly" else "weeks"
        return f"Every {self.cadence_interval} {unit}"

    def __str__(self):
        return f"{self.number or '—'} · {self.name}"


class TaskTemplateStep(TenantEventOwned):
    """One ordered step in a playbook — the unit that becomes one ``crm.CrmTask``.

    A plain child row with no auto-number, mirroring ``crm.EventAttendee`` and ``crm.CaseComment``.
    ``offset_days`` is signed on purpose: -2 means "two days BEFORE the anchor" (the prep email),
    +0 the anchor day itself. A playbook is a timeline, and forbidding negative offsets would make
    every real playbook impossible to express.
    """

    #: IMPORTED — the same lists the parent uses, so a step's task ranks like the template's.
    TASK_TYPE_CHOICES = CrmTask.TYPE_CHOICES
    PRIORITY_CHOICES = CrmTask.PRIORITY_CHOICES

    template = models.ForeignKey(
        "sales.TaskTemplate",
        on_delete=models.CASCADE,
        related_name="steps",
    )
    order = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, default="todo")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    offset_days = models.SmallIntegerField(
        default=0,
        validators=[MinValueValidator(-MAX_STEP_OFFSET_DAYS), MaxValueValidator(MAX_STEP_OFFSET_DAYS)],
        help_text="Days from the cycle anchor. Negative means before it.",
    )

    class Meta:
        ordering = ["order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["template", "order"], name="sales_ttstep_tpl_order_uniq"),
        ]

    def clean(self):
        super().clean()
        if self.offset_days is not None and not -MAX_STEP_OFFSET_DAYS <= self.offset_days <= MAX_STEP_OFFSET_DAYS:
            raise ValidationError(
                {"offset_days": (
                    f"A step offset must be between -{MAX_STEP_OFFSET_DAYS} and "
                    f"{MAX_STEP_OFFSET_DAYS} days."
                )}
            )

    def __str__(self):
        return f"{self.order}. {self.title}"