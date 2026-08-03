"""SCM 4.13 Asset Management — ``MaintenancePlan`` [PM-] + ``MaintenancePlanTask``, the PM programme.

**What this is.** One row per recurring job an asset owes: the greasing round, the quarterly
inspection, the 500-hour service, the vibration threshold that says "look at it now". The plan is a
*definition* — it never executes anything. Pressing **generate** on it snapshots a
``MaintenanceWorkOrder``, and that job is what gets scheduled, worked and costed. Keeping the two
apart is what makes "the plan changed last month" and "this is what the job actually said in March"
both answerable.

**Four triggers, taken verbatim from Oracle's four forecast methods** — calendar, meter, combined
calendar+meter, condition event. A boolean ``is_meter_based`` would have covered the first two and
lost the other two, and the fourth is the seam 11.7 / IoT condition monitoring lands on: a sensor
feed becomes a ``MeterReading`` row, and a ``condition`` plan already knows what to do with one.
``combined`` is not a convenience: on a plan that is due every 90 days **or** every 500 hours,
whichever arrives first, the two axes must be evaluated together or half the trigger is silently
dead. :meth:`due_status` is where "whichever comes first" is decided, once.

**``schedule_basis`` is SAP's cycle/offset/shift-factor machinery reduced to the one bit that
changes an answer.** ``floating`` measures the next due date from the LAST COMPLETION — a service
done a fortnight late pushes the whole future schedule a fortnight out, which is right for
wear-driven work. ``fixed`` measures from the calendar the plan already published, so a late job
does not drag every future cycle late with it, which is right for a statutory inspection that is due
in January whatever happened in December. Both readings are defensible and the difference is not
guessable from the data, so it is a stored choice rather than a hard-coded rule.

**Why ``next_due_on`` / ``next_due_reading`` are COLUMNS when everything else derived here is not.**
They are not derivations, they are *the schedule* — an input a planner may deliberately shift, and
one whose historical anchor (the completion that produced it) is gone the moment the job closes.
Recomputing them on read would need a fact the database no longer has. Everything genuinely derived
from them — :meth:`days_until_due`, :meth:`meter_gap`, :meth:`is_due`, :meth:`due_status` — is a
method that recomputes on every read, because a stored "is overdue" flag is a second copy of a fact
the clock changes overnight without asking anyone.

**:meth:`advance` is the ONLY place the floating-vs-fixed arithmetic lives.** The generate action and
the work-order complete verb both call it; neither does date maths of its own. It rolls forward
**exactly one cycle even when several were missed**, the ``ComplianceRequirement.record_check``
precedent: skipping the gap would erase the fact that cycles *were* missed, and the next
:meth:`due_status` read correctly re-flags the plan as overdue.

**``last_completed_on`` and ``last_generated_on`` are ``editable=False`` (L22).** Both record that
something happened; a system timestamp is never a form field, or a planner can type a service that
was never performed and the PM-compliance report believes it.

**``asset`` is ``CASCADE`` — deliberately unlike ``MaintenanceWorkOrder.asset``, which is
``PROTECT``.** A plan is a standing instruction about a machine: once the machine is gone the
instruction is not a record worth keeping, it is a rule that can never fire. A completed *job* is
the opposite — it is history, and history must not be one click from deletion.

**Every day-count column is capped.** ``interval_days`` is fed straight to ``timedelta(days=…)`` and
``PositiveIntegerField`` accepts 4294967295 on MariaDB, which is an uncaught ``OverflowError`` — a
500, not a validation error (the 4.10 DoS finding).

**``MaintenancePlanTask`` carries no tenant.** It is a pure child of one plan, never listed on its
own — the ``ComplianceCheck`` / ``TradeDocumentLine`` / ``InspectionResult`` precedent. Its tenant is
``plan.tenant``, and every view MUST resolve it as
``get_object_or_404(MaintenancePlanTask, pk=pk, plan__tenant=request.tenant)``. A bare ``pk`` lookup
is a cross-tenant read.
"""
from datetime import timedelta

from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.AssetManagement._choices import (
    PRIORITY_CHOICES,
    PRIORITY_CSS,
    WORK_TYPE_CHOICES,
    WORK_TYPE_CSS,
)


class MaintenancePlan(TenantNumbered):
    """A recurring maintenance obligation on one asset — its trigger, its cadence, its job plan [PM-]."""

    NUMBER_PREFIX = "PM"

    #: Oracle's four forecast methods, verbatim. See the module docstring for why this is not a
    #: boolean and why ``condition`` is declared now rather than when 11.7 arrives.
    TRIGGER_CHOICES = [
        ("calendar", "Calendar — every N days"),
        ("meter", "Meter — every N meter units"),
        ("combined", "Combined — calendar or meter, whichever comes first"),
        ("condition", "Condition — when a reading crosses a threshold"),
    ]
    SCHEDULE_BASIS_CHOICES = [
        ("floating", "Floating — next due measured from the last completion"),
        ("fixed", "Fixed — next due measured from the calendar regardless"),
    ]
    #: Only two operators, and no ``eq``: a continuous meter reading almost never lands exactly on a
    #: threshold, so an equality trigger would look configured and never fire.
    CONDITION_OPERATOR_CHOICES = [
        ("gte", "At or above"),
        ("lte", "At or below"),
    ]

    #: The five words :meth:`due_status` may answer. Declared as a dict of labels rather than left to
    #: the templates, so no page renders the raw token ``not_scheduled`` at a user.
    DUE_STATUS_LABELS = {
        "overdue": "Overdue",
        "due_today": "Due today",
        "due_soon": "Due soon",
        "scheduled": "Scheduled",
        "not_scheduled": "Not scheduled",
    }
    DUE_STATUS_CSS = {
        "overdue": "badge-red",
        "due_today": "badge-amber",
        "due_soon": "badge-info",
        "scheduled": "badge-green",
        "not_scheduled": "badge-muted",
    }
    #: Colour per trigger. This is TAXONOMY, not severity — nothing about a calendar plan is better
    #: or worse than a meter one — so the neutral classes carry three of the four and ``condition``
    #: takes the one remaining accent purely to keep four values distinguishable at a glance.
    #: ``badge-red`` is deliberately unused here: on this model red means *overdue*, and a trigger
    #: badge must never be mistaken for a state badge. theme.css ships colour-named badges ONLY —
    #: badge-green / red / amber / info / muted / slate; badge-success and friends do not exist and
    #: render as unstyled text (L33).
    TRIGGER_CSS = {
        "calendar": "badge-info",
        "meter": "badge-slate",
        "combined": "badge-green",
        "condition": "badge-amber",
    }

    #: Every outward FK whose target is tenant-scoped. ``clean()`` walks this list, so a pointer
    #: added later is covered by the cross-tenant guard the moment it is named here — the
    #: ``TradeLicense.TENANT_SCOPED_FKS`` idiom, rather than a third copy of the same if-block.
    TENANT_SCOPED_FKS = ("asset", "assigned_to", "parts_location")

    # --- what the plan IS -------------------------------------------------------------------------
    name = models.CharField(max_length=255)
    asset = models.ForeignKey(
        "scm.Asset", on_delete=models.CASCADE, related_name="maintenance_plans",
        help_text="The machine this obligation is attached to")
    instructions = models.TextField(
        blank=True, help_text="What the job is, in prose. Step-by-step checks belong in the tasks below")
    is_active = models.BooleanField(
        default=True, help_text="An inactive plan never comes due and cannot generate a job")

    # --- how it comes due -------------------------------------------------------------------------
    trigger_type = models.CharField(max_length=10, choices=TRIGGER_CHOICES, default="calendar")
    schedule_basis = models.CharField(
        max_length=8, choices=SCHEDULE_BASIS_CHOICES, default="floating",
        help_text="Floating suits wear-driven work; fixed suits a statutory date")
    # Capped at ten years — this number is fed straight to timedelta(days=...). See the module
    # docstring for why a bare PositiveIntegerField is a 500 waiting to happen.
    interval_days = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(3650)],
        help_text="Calendar cadence in days — required for a calendar or combined plan")
    # SAP calls this the call horizon and Oracle the forecast window: how far AHEAD of the due date a
    # job may be raised, so the storeroom and the technician have notice. One year is past any real
    # horizon and keeps the same OverflowError out of the due-soon arithmetic.
    lead_time_days = models.PositiveIntegerField(
        default=7, validators=[MaxValueValidator(365)],
        help_text="Raise the job this many days before it is due")
    meter_interval = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q4)],
        help_text="Usage cadence in meter units — required for a meter or combined plan")

    # --- where the schedule currently stands (see the module docstring: these are the SCHEDULE, ----
    # --- not a derivation, which is why they are the only forward-looking columns here) ------------
    next_due_on = models.DateField(
        null=True, blank=True, help_text="Date the next occurrence is owed")
    next_due_reading = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q4)],
        help_text="Meter value the next occurrence is owed at")
    # The condition axis. Both halves are required together or the trigger is an empty claim — a
    # threshold with no operator cannot be evaluated, and an operator with no threshold has nothing
    # to compare against (the 4.11 "an alert with no threshold" finding).
    condition_operator = models.CharField(
        max_length=4, choices=CONDITION_OPERATOR_CHOICES, blank=True,
        help_text="Only for a condition plan: which way the reading has to cross the threshold")
    condition_threshold = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q4)],
        help_text="Only for a condition plan: the reading that makes the work due")

    # --- system stamps (L22) — written by the verbs, never by a form -------------------------------
    last_completed_on = models.DateField(
        null=True, blank=True, editable=False,
        help_text="Stamped by the work-order complete verb")
    last_generated_on = models.DateField(
        null=True, blank=True, editable=False,
        help_text="Stamped by the generate action")

    # --- what the generated job inherits ----------------------------------------------------------
    # These live on the PLAN so the job it raises can be STAMPED with them. That is the whole reason
    # PRIORITY_CHOICES and WORK_TYPE_CHOICES are shared vocabularies in _choices.py rather than
    # declared on each model: two lists would let the generate action write a value the target
    # column silently will not accept.
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="medium")
    work_type = models.CharField(max_length=12, choices=WORK_TYPE_CHOICES, default="preventive")
    estimated_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("1"),
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("999.99"))],
        help_text="Planned labour for one occurrence")
    assigned_to = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_maintenance_plans",
        help_text="Default technician or crew for the jobs this plan raises")
    parts_location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="maintenance_plans",
        help_text="Storeroom a generated job draws its parts from")

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="scm_pm_tnt_active_idx"),
            # The forecast board and the due/overdue chips all range-scan this one.
            models.Index(fields=["tenant", "next_due_on"], name="scm_pm_tnt_due_idx"),
            models.Index(fields=["tenant", "asset"], name="scm_pm_tnt_asset_idx"),
            models.Index(fields=["tenant", "trigger_type"], name="scm_pm_tnt_trig_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'PM'} · {self.name}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """The trigger contract, plus the cross-tenant guard.

        The contract exists because a plan that cannot come due is worse than no plan: it sits on the
        register looking like the machine is covered and never raises a single job. Each trigger is
        therefore required to carry the inputs its own arithmetic reads, and nothing else validates
        that — :meth:`due_status` would simply answer ``not_scheduled`` forever.
        """
        super().clean()

        # THE GUARD. The form's querysets are tenant-scoped, but that is UX — a narrowed dropdown has
        # never held against a crafted POST (L39 §2). Skipped when the instance has no tenant yet: an
        # unsaved model has tenant_id None and ``self.tenant`` would raise RelatedObjectDoesNotExist
        # on a non-nullable FK rather than return None.
        if self.tenant_id is not None:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None here instead of 500-ing inside
                # validation.
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another workspace."})

        # (a) The calendar axis. Zero is caught along with None: an interval of 0 days is due every
        #     instant, which is not a schedule.
        if self.trigger_type in ("calendar", "combined") and not self.interval_days:
            raise ValidationError(
                {"interval_days": f"A '{self.get_trigger_type_display()}' plan needs an interval in "
                                  "days, or it can never come due."})

        # (b) The meter axis — the cadence AND a meter to measure it against. A meter plan on an
        #     asset with no meter defined is the same empty claim: readings would have nothing to
        #     attach to and meter_gap() would answer None forever.
        if self.trigger_type in ("meter", "combined"):
            if not self.meter_interval:
                raise ValidationError(
                    {"meter_interval": f"A '{self.get_trigger_type_display()}' plan needs a meter "
                                       "interval, or it can never come due."})
            asset = getattr(self, "asset", None) if self.asset_id else None
            if asset is not None and not (asset.meter_name or "").strip():
                raise ValidationError(
                    {"meter_interval": f"{asset} has no meter defined — name the asset's meter on "
                                       "the asset record before scheduling meter-based work."})

        # (c) The condition axis. Both halves or neither; see the field comments.
        if self.trigger_type == "condition":
            if not self.condition_operator:
                raise ValidationError(
                    {"condition_operator": "A condition plan needs to say which way the reading "
                                           "has to cross the threshold."})
            if self.condition_threshold is None:
                raise ValidationError(
                    {"condition_threshold": "A condition plan needs the reading that makes the "
                                            "work due."})

    # ---------------------------------------------------------------------------------------------
    # The meter the schedule reads
    # ---------------------------------------------------------------------------------------------
    def latest_reading(self):
        """The asset's most recent reading on its primary meter, or ``None``.

        Delegates to ``Asset.latest_reading()`` instead of querying ``MeterReading`` here. The asset
        owns that question — including the decision NOT to fall back to another meter's readings when
        a primary meter is named, which matters more to a schedule than to anything else that asks:
        an odometer reading handed to a plan whose interval is in running hours would schedule a
        service roughly never, silently. Two implementations of "what does the meter say now" would
        drift the first time one of them learned about a second meter.

        Cached on the instance: :meth:`due_status` consults both axes and :meth:`is_due` reads
        :meth:`due_status`, so an uncached lookup would be three or four identical queries per plan
        per render. A list page still wants ``select_related("asset")`` — this caches the *reading*
        query, not the asset fetch it needs first.
        """
        if self.asset_id is None:
            return None
        if not hasattr(self, "_latest_reading_cache"):
            self._latest_reading_cache = self.asset.latest_reading()
        return self._latest_reading_cache

    def meter_gap(self):
        """``next_due_reading`` minus the asset's latest reading — units still to run before due.

        Negative once the meter has passed the target, and that sign is what
        :meth:`_meter_axis_due` reads.

        ``None``, never ``0``, when this plan is not meter-driven, when no target reading is set, or
        when the asset has never been read. "No answer" and "due right now" are different facts and
        a confident zero states the second (the 4.11 ``projected_stockout_count`` lesson) — on a
        maintenance board that is the difference between a blank a planner investigates and a red
        chip they act on.
        """
        if self.trigger_type not in ("meter", "combined") or self.next_due_reading is None:
            return None
        latest = self.latest_reading()
        if latest is None:
            return None
        return q4(Decimal(self.next_due_reading) - Decimal(latest.reading or ZERO))

    # ---------------------------------------------------------------------------------------------
    # Due — one decision point. is_due() reads due_status() rather than reimplementing it, so the
    # two can never disagree about a plan that the board and the generate queue both look at.
    # ---------------------------------------------------------------------------------------------
    def days_until_due(self, today=None):
        """``next_due_on`` minus today, in days; negative once past. ``None`` when no date is set.

        ``timezone.localdate()``, not ``date.today()``: the project is TZ-aware and the server's date
        is not necessarily the workspace's — the idiom every module from 4.7 on uses.
        """
        if not self.next_due_on:
            return None
        return (self.next_due_on - (today or timezone.localdate())).days

    def _meter_axis_due(self):
        """True when a meter-driven plan has reached or passed its target reading (gap <= 0)."""
        gap = self.meter_gap()
        return gap is not None and gap <= ZERO

    def _condition_axis_due(self):
        """True when a condition plan's latest reading satisfies ``operator`` against ``threshold``.

        ``gte`` fires at or above the threshold, ``lte`` at or below. False with no reading at all:
        an unmeasured machine is unknown, not healthy and not failing, and raising a job off silence
        would train everyone to ignore the trigger.
        """
        if (self.trigger_type != "condition" or not self.condition_operator
                or self.condition_threshold is None):
            return False
        latest = self.latest_reading()
        if latest is None:
            return False
        value = Decimal(latest.reading or ZERO)
        threshold = Decimal(self.condition_threshold)
        if self.condition_operator == "gte":
            return value >= threshold
        return value <= threshold

    def due_status(self, today=None):
        """``overdue`` / ``due_today`` / ``due_soon`` / ``scheduled`` / ``not_scheduled``.

        The usage axes are consulted FIRST, and that ordering is the ``combined`` contract: due is
        whichever of the two arrives first, so a meter that has already run past its target outranks
        a date still in the future. A plan reading ``overdue`` on a future date is not a bug — the
        work was owed at 500 hours and the machine is at 540.

        ``due_soon`` is the call horizon (``lead_time_days``), the window in which the generate
        action may raise a job ahead of time. It is deliberately NOT part of :meth:`is_due`: raising
        work early and *owing* work are different states, and merging them would make the PM
        compliance figure count jobs that were never late.

        An inactive plan is not evaluated at all — it answers ``not_scheduled``, because a plan that
        cannot generate a job cannot be overdue for one.
        """
        if not self.is_active:
            return "not_scheduled"
        if self._meter_axis_due() or self._condition_axis_due():
            return "overdue"
        days = self.days_until_due(today)
        if days is None:
            return "not_scheduled"
        if days < 0:
            return "overdue"
        if days == 0:
            return "due_today"
        if days <= (self.lead_time_days or 0):
            return "due_soon"
        return "scheduled"

    def is_due(self, today=None):
        """Is the work owed NOW? For ``combined``, due = whichever axis comes first.

        A thin read of :meth:`due_status` on purpose — the alternative is a second implementation of
        the same rule that drifts the first time one of them learns about a new trigger.
        """
        return self.due_status(today) in ("overdue", "due_today")

    # ---------------------------------------------------------------------------------------------
    # The schedule roll
    # ---------------------------------------------------------------------------------------------
    def advance(self, from_date=None, save=False):
        """Roll the schedule forward by exactly ONE cycle. The only place this arithmetic lives.

        Arithmetic, per axis:

        * calendar (``calendar`` / ``combined``) — ``next_due_on = anchor + interval_days`` where
          ``anchor`` is ``from_date`` on a **floating** plan (measure from what actually happened)
          and the currently published ``next_due_on`` on a **fixed** one (measure from the calendar,
          so a job done late does not drag every future cycle late with it). A fixed plan with no
          published date yet falls back to ``from_date`` — there is nothing else to roll from.
        * meter (``meter`` / ``combined``) — ``next_due_reading = base + meter_interval``, with the
          same split: **floating** takes ``base`` from the meter as it actually reads now,
          **fixed** from the target already published. Written through ``q4()`` so an absurd
          interval clamps to what the column holds instead of raising ``DataError`` inside the
          caller's transaction.
        * ``condition`` — nothing. A condition plan's next occurrence is decided by the machine, not
          by a schedule, so there is no cycle to roll.

        **Exactly one cycle, even when several were missed** (the ``ComplianceRequirement`` posture):
        skipping the gap would erase the fact that cycles *were* missed, and the next
        :meth:`due_status` read correctly re-flags the plan as overdue.

        Returns the list of field names it wrote. ``save=False`` by default because both callers —
        the generate action and the work-order complete verb — write their own stamps
        (``last_generated_on`` / ``last_completed_on``) in the same round trip and fold this list
        into their own ``update_fields``. This method never writes those stamps itself: they record
        an event it did not observe.
        """
        from_date = from_date or timezone.localdate()
        written = []

        if self.interval_days and self.trigger_type in ("calendar", "combined"):
            anchor = from_date if self.schedule_basis == "floating" else (self.next_due_on or from_date)
            self.next_due_on = anchor + timedelta(days=self.interval_days)
            written.append("next_due_on")

        if self.meter_interval and self.trigger_type in ("meter", "combined"):
            published = self.next_due_reading
            if self.schedule_basis == "fixed" and published is not None:
                base = Decimal(published)
            else:
                latest = self.latest_reading()
                base = Decimal(latest.reading or ZERO) if latest is not None else Decimal(published or ZERO)
            self.next_due_reading = q4(base + Decimal(self.meter_interval))
            written.append("next_due_reading")

        if save and written:
            self.save(update_fields=written + ["updated_at"])
        return written

    # ---------------------------------------------------------------------------------------------
    # Badge lookups — Django templates cannot subscript a dict by a variable, so every colour and
    # label decision is resolved here and nowhere else.
    # ---------------------------------------------------------------------------------------------
    @property
    def due_status_label(self):
        return self.DUE_STATUS_LABELS.get(self.due_status(), "Not scheduled")

    @property
    def due_status_css(self):
        return self.DUE_STATUS_CSS.get(self.due_status(), "badge-muted")

    @property
    def trigger_css(self):
        return self.TRIGGER_CSS.get(self.trigger_type, "badge-muted")

    @property
    def priority_css(self):
        """``PRIORITY_CSS`` lives in ``_choices.py`` (two models read it); the lookup lives here."""
        return PRIORITY_CSS.get(self.priority, "badge-muted")

    @property
    def work_type_css(self):
        return WORK_TYPE_CSS.get(self.work_type, "badge-muted")


class MaintenancePlanTask(models.Model):
    """One step of the job plan — the checklist a generated work order snapshots. Tenant-less child.

    Maximo calls this a job plan, SAP a task list, MaintainX a procedure: the point in all three is
    that the *steps* are part of the plan, so a technician gets the same instructions every cycle and
    an auditor can see what the instructions were.

    **Safety rides here as a flag, not as a table.** Maximo embeds safety plans, permits and LOTO in
    the job plan itself. Module 11.11 is the eventual home of a real permit-to-work engine; until it
    exists a lock-out step is an ordinary task with ``is_safety_step`` set, which keeps it visible and
    printable on the job without inventing a permit register that nothing else in the app honours.

    No ``tenant`` column — it is reached through ``plan__tenant`` (the ``ComplianceCheck`` /
    ``TradeDocumentLine`` precedent), so views MUST resolve it as
    ``get_object_or_404(MaintenancePlanTask, pk=pk, plan__tenant=request.tenant)``. Edited as an
    inline formset on the plan form, so parent and lines commit in one ``transaction.atomic()``.
    """

    plan = models.ForeignKey("scm.MaintenancePlan", on_delete=models.CASCADE, related_name="tasks")
    # Tens, so a step can be inserted between two without renumbering the sheet — the
    # WorkOrderComponent.sequence convention. Capped because it is a display ordinal, not a counter.
    sequence = models.PositiveIntegerField(default=10, validators=[MaxValueValidator(9999)])
    description = models.CharField(max_length=255)
    expected_result = models.CharField(
        max_length=255, blank=True,
        help_text="What good looks like — 'oil level between the marks', 'under 70 dB'")
    # A mandatory step is one the job cannot be signed off without. Optional steps exist so a
    # technician is never forced to tick something that did not apply, which is what keeps the ticks
    # on the mandatory ones worth reading.
    is_mandatory = models.BooleanField(default=True)
    is_safety_step = models.BooleanField(
        default=False, help_text="Isolation, lock-out/tag-out, permit — flagged so it prints first")

    class Meta:
        ordering = ["sequence", "id"]
        indexes = [models.Index(fields=["plan", "sequence"], name="scm_pmt_plan_seq_idx")]

    def __str__(self):
        return f"{self.sequence}. {self.description}"
