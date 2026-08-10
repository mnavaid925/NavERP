"""SCM 4.14 Labor Management — ``LaborActivity`` [LAB-], the booked interval.

**What this is.** SAP EWM calls it the *executed workload document*: one row per stretch of a shift,
saying what the worker was doing, for how long, how many units came out of it and how many of those
were wrong. A ``LaborSession`` says a person was on site between two clock times; the activities
underneath it say what those minutes went on. Everything the module claims about productivity is an
aggregate over this table, which is why the row is small and the rules on it are not.

**Direct vs indirect is the line the whole module is built on.** ``DIRECT_ACTIVITIES`` /
``INDIRECT_ACTIVITIES`` in ``_choices.py`` are the single source of truth for which side a row falls
on — present in all ten surveyed products (SAP EWM's indirect labor task, Infios' "direct, indirect
and lost time", Easy Metrics' Indirect Time Insights, TZA's delay coding, Softeon's idle time).
Performance is earned minutes over *direct* minutes, so an activity on the wrong side of that line
moves every number on the scorecard. It also drives the paired validation below: productive work
carries units and no reason, non-productive work carries a reason and no units. That pairing is
exactly ``ProductionTimeLog.downtime_reason``'s shape, for exactly its reason — a category with no
required companion field is a category nobody can total afterwards.

**The standard snapshot is the correctness feature of this file.** ``standard`` is a pointer kept for
traceability only. The numbers that decide what this row EARNED are copied onto the row when it is
filed: the fixed time, the per-unit rate and the allowance, plus the earned minutes they produce.
*Editing a standard next month must not silently rewrite last month's measured performance* — a
supervisor who tightens a picking standard in March would otherwise retroactively turn February's
passing shifts into failing ones, and nobody could reproduce the number they were shown at the time.
The three input snapshots are stored alongside the derived one so the arithmetic can be **replayed
from the row alone**; a single stored total would be a number with no visible working.

The FK is ``SET_NULL``, so the snapshots — not ``standard_id`` — are what "this activity was
measured" means. A standard that is deleted takes its pointer with it and leaves every measurement
it ever produced intact.

**Resolution happens ONCE, in the create path, via ``select_standard()``. ``save()`` never
re-resolves.** What ``save()`` does recompute is ``standard_minutes_snapshot``, and only from the
three snapshots and the *current* ``quantity`` — so correcting a mistyped quantity while the session
is still open updates earned minutes correctly, while editing the ``LaborStandard`` row changes
nothing here at all. One writer, one direction. That is the same discipline
``WorkOrder.quantity_produced`` had to be given after two writers quietly overwrote each other.

**An activity without a standard has ``earned_minutes = None``, never ``0``.** Not every job in a
warehouse has been time-studied, and a ratio of 0 earned over 40 booked minutes prints as 0%
performance — an unmeasured job rendered as a failing one, against a named person. ``None`` says
"not measured" and drops the row out of both sides of the ratio, which is the only honest answer.

**Task links are pointers OUT to 4.4, never a column added to it.** ``PickTask``, ``PutawayTask`` and
``CycleCountTask`` already exist and already carry ``assigned_to``; 4.14 records the minutes spent
against them and adds nothing to those tables. At most one may be set, and the one that is set must
match the activity type — otherwise a pick task carries cleaning minutes and every board that reads
"time booked against this task" lies about it.
"""
from datetime import timedelta

from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.LaborManagement._choices import (
    ACTIVITY_CHOICES,
    ACTIVITY_CSS,
    DIRECT_ACTIVITIES,
    INDIRECT_ACTIVITIES,
    INDIRECT_REASON_CHOICES,
    MAX_ACTIVITY_MINUTES,
    MAX_SNAPSHOT_MINUTES,
)

#: Local scalars for the two conversions this file does. Named rather than inlined so the percentage
#: maths reads the same here as it does in ``ReturnPolicy`` (``ONE_HUNDRED``), and underscored so a
#: star import from this module can never shadow a sibling's constant of the same name.
_ONE_HUNDRED = Decimal("100")
_SIXTY = Decimal("60")


class LaborActivity(TenantNumbered):
    """One booked interval inside a shift: what was done, for how long, how much came out [LAB-]."""

    NUMBER_PREFIX = "LAB"

    #: Longest single booked activity, in minutes — one day. Pulled from ``_choices`` so the form,
    #: the seeder and any future verb inherit the same ceiling. See :meth:`clean` for why an interval
    #: needs its LENGTH bounded and not merely the order of its two ends, and see the constant's own
    #: comment for why it is a constant rather than "the session's remaining minutes".
    MAX_ACTIVITY_MINUTES = MAX_ACTIVITY_MINUTES

    #: Which activity types each task pointer is allowed to accompany. **This dict is the single
    #: source of both task rules**: its keys are the "at most one may be set" set, and its values are
    #: the type match. Two hand-typed lists would be one forgotten edit away from a pointer that is
    #: exclusive but unmatched, or matched but not exclusive. ``pick_task`` covers ``pack`` as well
    #: as ``pick`` because 4.4 models packing as the second half of the same pick document — the pack
    #: minutes belong to the task that produced the carton.
    TASK_FK_ACTIVITIES = {
        "pick_task": ("pick", "pack"),
        "putaway_task": ("putaway",),
        "cycle_count_task": ("cycle_count",),
    }

    #: Every outward FK whose target is tenant-scoped. :meth:`clean` walks this list, so a pointer
    #: added later is covered by the cross-tenant guard the moment it is named here — the
    #: ``TradeLicense.TENANT_SCOPED_FKS`` / ``MaintenancePlan`` idiom, rather than a fifth copy of
    #: the same if-block.
    #:
    #: ``session`` and ``standard`` are on this list even though neither is a form field. Neither can
    #: be set from a POST — ``session`` comes from the parent route and ``standard`` from
    #: ``select_standard()`` — so the guard fires only on code that built the instance itself (a
    #: seeder, a test, a future importer). Through a ModelForm an error keyed on a field the form
    #: does not carry surfaces as a ``ValueError`` rather than a field error; that is a fail-CLOSED
    #: outcome for a path that cannot legitimately reach here, and refusing loudly beats writing
    #: another workspace's shift.
    TENANT_SCOPED_FKS = ("session", "pick_task", "putaway_task", "cycle_count_task", "standard")

    # --- whose shift, and what was being done ------------------------------------------------------
    # CASCADE: an activity is meaningless without the shift it was booked inside. Deleting a session
    # must take its minutes with it or the aggregates would keep counting orphaned work.
    session = models.ForeignKey("scm.LaborSession", on_delete=models.CASCADE,
                                related_name="activities")
    activity_type = models.CharField(max_length=18, choices=ACTIVITY_CHOICES, default="pick")
    # Required for indirect work, forbidden for direct — see clean(). ``activity_type`` sizes the
    # loss; the reason is what a supervisor can actually act on.
    indirect_reason = models.CharField(
        max_length=20, choices=INDIRECT_REASON_CHOICES, blank=True,
        help_text="Why the non-productive minutes were spent — required for an indirect activity")

    # --- the interval ------------------------------------------------------------------------------
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(
        null=True, blank=True, help_text="Leave blank while the activity is still running")
    # Computed from the interval in save() — never typed, so the two can never disagree.
    duration_minutes = models.PositiveIntegerField(default=0, editable=False)

    # --- what came out of it -----------------------------------------------------------------------
    quantity = models.DecimalField(
        max_digits=16, decimal_places=4, default=0,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q4)],
        help_text="Units of work completed, in the standard's basis (units, lines, cases, pallets)")
    # The ONE recorded accuracy input. Accuracy percentage is derived from it and never stored: a
    # stored percentage is a second copy of a fact that changes the moment a quantity is corrected.
    error_quantity = models.DecimalField(
        max_digits=16, decimal_places=4, default=0,
        validators=[MinValueValidator(ZERO)],
        help_text="Of those units, how many were wrong — mis-picks, mis-scans, short cartons")

    # --- what it was booked against ----------------------------------------------------------------
    # Pointers OUT to 4.4's existing task tables. SET_NULL on all three: a purged task must not take
    # the record of the minutes somebody spent on it, and payroll-relevant history is not one
    # cascade away from deletion.
    pick_task = models.ForeignKey("scm.PickTask", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="labor_activities")
    putaway_task = models.ForeignKey("scm.PutawayTask", on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="labor_activities")
    cycle_count_task = models.ForeignKey("scm.CycleCountTask", on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="labor_activities")
    reference = models.CharField(
        max_length=40, blank=True,
        help_text="Free-text document or job reference, for work with no task record")

    # --- the standard snapshot (see the module docstring — this is the correctness feature) ---------
    # All five are editable=False: they are stamped by whichever code path files the activity, never
    # typed (L22). A standard a user can type is not a measurement, it is a claim.
    standard = models.ForeignKey(
        "scm.LaborStandard", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="activities",
        help_text="Which standard was in force when this was filed — traceability only; the "
                  "measurement itself lives in the snapshots below")
    standard_fixed_snapshot = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, editable=False,
        help_text="setup_minutes + travel_minutes as they stood at file time")
    standard_rate_snapshot = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, editable=False,
        help_text="minutes_per_unit as it stood at file time")
    standard_allowance_snapshot = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, editable=False,
        help_text="PF&D allowance percentage as it stood at file time")
    standard_minutes_snapshot = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, editable=False,
        help_text="The earned minutes those three produce for this quantity — recomputed in save() "
                  "from the snapshots, never from the live standard")

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # The session detail page and every per-session aggregate walk this one.
            models.Index(fields=["tenant", "session"], name="scm_lab_tnt_sess_idx"),
            # The direct/indirect split and the indirect-bucket GROUP BY.
            models.Index(fields=["tenant", "activity_type"], name="scm_lab_tnt_type_idx"),
            # Every period report range-scans the start time.
            models.Index(fields=["tenant", "started_at"], name="scm_lab_tnt_start_idx"),
        ]
        # Django would pluralise "labor activity" into "labor activitys" — the ReturnPolicy
        # precedent, and it is the string the admin and every generic heading prints.
        verbose_name_plural = "labor activities"

    def __str__(self):
        return f"{self.number or 'LAB'} · {self.get_activity_type_display()} {self.duration_minutes}m"

    # ---------------------------------------------------------------------------------------------
    # Classification
    # ---------------------------------------------------------------------------------------------
    @property
    def is_direct(self):
        """Productive work — minutes that move goods and are measured against a standard.

        Branches on the shared frozenset, never on a hand-typed tuple: this one predicate decides
        which side of the performance ratio the row lands on, so it exists in exactly one place.
        """
        return self.activity_type in DIRECT_ACTIVITIES

    @property
    def is_indirect(self):
        return self.activity_type in INDIRECT_ACTIVITIES

    @property
    def activity_css(self):
        """theme.css badge class for :attr:`activity_type` — one lookup, so no template invents a
        colour and none of the six real classes gets misspelt into unstyled text (L33)."""
        return ACTIVITY_CSS.get(self.activity_type, "badge-muted")

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """The booking contract: whose shift, what kind of work, and does the arithmetic hold.

        The rules exist because this row is an *input to pay and to a person's scorecard*. A booking
        that lands outside its shift, on a shift that has already been signed off, or on a task it
        has nothing to do with does not fail loudly — it quietly moves somebody's numbers.
        """
        super().clean()

        # THE GUARD, and deliberately FIRST rather than last. Every rule below dereferences
        # ``self.session``: run the tenant check afterwards and a crafted session pk would first be
        # measured against another workspace's clock window, which turns the rejection message into
        # an oracle — vary ``started_at``, watch accept/reject, and read back a foreign shift's punch
        # times one refusal at a time. The form's querysets are tenant-scoped, but that is UX; a
        # narrowed dropdown has never held against a crafted POST (L39 §2).
        #
        # Skipped when the instance has no tenant yet: an unsaved model has tenant_id None and
        # ``self.tenant`` would raise RelatedObjectDoesNotExist on a non-nullable FK rather than
        # return None.
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

        # (a) The interval itself.
        if self.started_at and self.ended_at and self.ended_at <= self.started_at:
            raise ValidationError({"ended_at": "The activity must end after it started."})

        # Bound the LENGTH, not just the order. ``duration_minutes`` is editable=False so it never
        # sees form validation, and the hours it yields divide into performance, units per hour and
        # every cost figure built on them. A 1000-01-01 -> 9999-12-31 interval also derives ~4.7e9
        # minutes, past what the PositiveIntegerField column holds — a 500 rather than a rejection.
        # A booked activity is a stretch of a shift, not a geological era.
        if self.started_at and self.ended_at:
            minutes = (self.ended_at - self.started_at).total_seconds() // 60
            if minutes > self.MAX_ACTIVITY_MINUTES:
                raise ValidationError({
                    "ended_at": f"A single booked activity cannot exceed "
                                f"{self.MAX_ACTIVITY_MINUTES // 60} hours — split it into one "
                                f"entry per stretch of work."})

        # (b) The direct / indirect pairing, both directions. Same shape as
        #     ``ProductionTimeLog.downtime_reason``: a category whose companion field is optional is
        #     a category that cannot be totalled afterwards, and a direct row carrying a delay code
        #     would be counted as productive AND as a delay.
        if self.is_direct:
            if not self.quantity or self.quantity <= ZERO:
                raise ValidationError({
                    "quantity": f"A '{self.get_activity_type_display()}' activity is productive "
                                "work — record how many units it completed."})
            if self.indirect_reason:
                raise ValidationError({
                    "indirect_reason": "Only an indirect activity carries a reason."})
        elif self.is_indirect:
            if not self.indirect_reason:
                raise ValidationError({
                    "indirect_reason": f"A '{self.get_activity_type_display()}' activity needs a "
                                       "reason — it is what makes the lost time answerable."})
            # Indirect minutes produce nothing by definition. Units booked on a break would be
            # counted as output against zero DIRECT minutes — a numerator with no denominator, which
            # is how a units-per-hour figure ends up infinite.
            if self.quantity:
                raise ValidationError({
                    "quantity": "Indirect time completes no units — leave the quantity at zero."})
            if self.error_quantity:
                raise ValidationError({
                    "error_quantity": "Indirect time completes no units, so it can contain no "
                                      "errors."})

        # (c) Accuracy has to be a subset of output, or accuracy_pct() goes negative and a worker
        #     who made three mistakes in two picks reads as -50% accurate.
        if (self.error_quantity or ZERO) > (self.quantity or ZERO):
            raise ValidationError({
                "error_quantity": "Errors cannot exceed the units completed."})

        # (d) At most one task pointer, and the one that is set must match the work. Both rules read
        #     TASK_FK_ACTIVITIES, so the exclusive set and the type match cannot drift apart.
        set_links = [name for name in self.TASK_FK_ACTIVITIES
                     if getattr(self, f"{name}_id", None) is not None]
        if len(set_links) > 1:
            raise ValidationError({
                set_links[1]: "An activity books time against one task — file a separate activity "
                              "for each task worked."})
        for name in set_links:
            allowed = self.TASK_FK_ACTIVITIES[name]
            if self.activity_type not in allowed:
                # Otherwise a pick task carries cleaning minutes, and every board that reports
                # "time booked against this task" reports a number that was never spent on it.
                raise ValidationError({
                    name: f"A '{self.get_activity_type_display()}' activity cannot be booked "
                          f"against that task."})

        # (e) The session must still be OPEN. ``closed`` and ``approved`` freeze the shift and its
        #     activities — approved is the payroll export's lock, and a booking added after sign-off
        #     would change hours that have already been paid without the approval being revisited.
        #     A cancelled session is not a shift at all.
        if self.session_id is not None and self.session.status != "open":
            raise ValidationError(
                f"Session {self.session.number} is {self.session.get_status_display().lower()} — "
                "reopen it before booking or correcting activities.")

        # (f) The interval has to fall INSIDE the shift it is booked against (the ``TimesheetEntry``
        #     date-in-period precedent). Minutes booked outside the clock window are minutes nobody
        #     was on site for: they inflate booked time past attended time, and utilisation — booked
        #     over attended — silently exceeds 100% with no explanation on the page.
        if self.session_id is not None and self.started_at:
            session = self.session
            if session.clock_in and self.started_at < session.clock_in:
                raise ValidationError({
                    "started_at": "The activity starts before the shift clocked in."})
            if self.ended_at:
                if session.clock_out:
                    if self.ended_at > session.clock_out:
                        raise ValidationError({
                            "ended_at": "The activity ends after the shift clocked out."})
                # While the session is still running there is no clock_out to bound against, so
                # "now" is the honest ceiling — an activity ending in the future is time nobody has
                # worked yet. The ceiling is rounded UP to the end of the current minute because the
                # datetime-local widget submits whole minutes: a supervisor closing an activity "now"
                # at 10:30:45 sends 10:31, and a bare ``> now`` would refuse the most natural input
                # in the module for 59 seconds out of every 60.
                elif self.ended_at > (timezone.now().replace(second=0, microsecond=0)
                                      + timedelta(minutes=1)):
                    raise ValidationError({
                        "ended_at": "The activity ends in the future — a shift that is still open "
                                    "can only book time that has already been worked."})

    # ---------------------------------------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        """Derive ``duration_minutes`` and re-run the earned-minutes arithmetic — both from data
        already on the row.

        Neither derivation goes back to the ``LaborStandard`` table. ``save()`` NEVER re-resolves the
        standard: resolution happened once, in the create path, via ``select_standard()``. What is
        recomputed is the earned figure, and only from the three snapshots plus the *current*
        quantity — so a mistyped quantity corrected while the session is open produces the right
        earned minutes, while editing the standard itself changes nothing here. One writer, one
        direction.
        """
        if self.started_at and self.ended_at and self.ended_at > self.started_at:
            self.duration_minutes = int((self.ended_at - self.started_at).total_seconds() // 60)
        else:
            self.duration_minutes = 0

        self.standard_minutes_snapshot = self._earned_from_snapshots()

        # A caller passing update_fields=["ended_at"] would otherwise persist the new interval and
        # leave the stale duration behind — and one passing update_fields=["quantity"] would leave
        # last version's earned minutes beside this version's units. A derived field must ride along
        # with its inputs, every time, or a partial save writes a row that contradicts itself.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = list(dict.fromkeys(
                list(update_fields) + ["duration_minutes", "standard_minutes_snapshot"]))
        return super().save(*args, **kwargs)

    def _earned_from_snapshots(self):
        """The earned minutes this row's snapshots produce for its current quantity.

        Deliberately a REPLAY of ``LaborStandard.minutes_for()`` rather than a call to it: calling it
        would read the live standard, which is the one thing the snapshot exists to prevent. The
        three input columns are stored precisely so this arithmetic can be reproduced from the row
        alone, months later, after the standard has been retuned or deleted outright.

        Returns ``None`` — never ``0`` — when the row carries no standard, because a zero here would
        print as 0% performance and render an unmeasured job as a failing one.
        """
        if not self.has_standard:
            return None
        fixed = self.standard_fixed_snapshot or ZERO
        rate = self.standard_rate_snapshot or ZERO
        allowance = self.standard_allowance_snapshot or ZERO
        quantity = self.quantity or ZERO
        earned = q4((fixed + quantity * rate) * (Decimal("1") + allowance / _ONE_HUNDRED))
        # q4() bounds this to DecimalField(14, 4) — TEN integer digits — but the column it is about
        # to be written into is DecimalField(12, 4), which holds EIGHT. So q4() alone is not the
        # bound it looks like: a quantity the form happily accepts (validated only up to MAX_Q4)
        # produces a figure two orders of magnitude too wide for the column, and the failure is a
        # DataError raised by the driver inside save() — an uncaught 500 on this sub-module's
        # primary write path, not a validation message a user could act on.
        # Clamping rather than raising matches q4()'s own posture: a single absurd row degrades to
        # an absurd-but-storable number instead of taking down the save.
        return min(earned, MAX_SNAPSHOT_MINUTES)

    @property
    def has_standard(self):
        """Whether this activity was measured against a standard.

        Asks the SNAPSHOTS, not ``standard_id``. The FK is ``SET_NULL``, so deleting a standard
        clears the pointer — and if that decided the question, every measurement the standard ever
        produced would evaporate the moment somebody tidied the library.

        **An INDIRECT row is never measured, whatever it is carrying.** The create path already
        refuses to stamp one (``_stamp_standard`` gates on ``is_direct``), but that is a gate on how
        snapshots get WRITTEN, and there are other ways a row can end up holding them: editing a
        direct activity's type to ``break`` keeps the determinants that were stamped when it was a
        pick, and so would an admin edit or a future importer. Without this clause such a row reads
        as measured and prints a ``performance_pct()`` on its own detail page — a worker credited
        with achievement for being on a break.
        Enforcing it HERE rather than in the edit view makes it true by construction for every
        writer, which is the difference between an invariant and a habit. The session-level ratio
        was already safe: ``LaborSession._measured()`` skips indirect rows outright.
        """
        if self.activity_type in INDIRECT_ACTIVITIES:
            return False
        return (self.standard_fixed_snapshot is not None
                or self.standard_rate_snapshot is not None)

    # ---------------------------------------------------------------------------------------------
    # Derived figures — methods and properties, never columns. Each returns None (not 0) on a zero
    # denominator: a rate over nothing is not zero, it is unanswerable, and printing 0% against a
    # named person is a claim the data does not support.
    # ---------------------------------------------------------------------------------------------
    @property
    def duration_hours(self):
        """The booked interval in hours, 2dp — the display figure."""
        return q2(Decimal(self.duration_minutes or 0) / _SIXTY)

    @property
    def earned_minutes(self):
        """What the standard says this quantity SHOULD have taken.

        ``None`` when there is no standard. Every caller must cope with that rather than substitute
        zero — an activity nobody has time-studied is unmeasured, not failed, and it must drop out of
        both sides of the ratio instead of dragging one of them down.

        Routed through :attr:`has_standard` rather than returning the column directly, so the
        indirect-work rule that property enforces reaches this figure too: a break row holding
        determinants from a previous activity type answers ``None`` here, not the minutes those
        determinants would produce.
        """
        if not self.has_standard:
            return None
        return self.standard_minutes_snapshot

    def performance_pct(self):
        """Earned minutes over booked minutes, as a percentage — Blue Yonder's "performance vs goal".

        100% is working exactly to standard; above is faster. ``None`` when nothing was booked (the
        ratio has no denominator) or when the row carries no standard (there is no numerator to put
        over it).
        """
        if not self.duration_minutes or not self.has_standard:
            return None
        return q2((self.standard_minutes_snapshot or ZERO) * _ONE_HUNDRED
                  / Decimal(self.duration_minutes))

    def units_per_hour(self):
        """Units completed per booked hour — the naive productivity figure the NavERP bullet names.

        Computed from MINUTES rather than from :attr:`duration_hours`, because dividing by an
        already-2dp-rounded hour figure turns a seven-minute interval into 0.12h and overstates the
        rate by several percent. Shown BESIDE performance-vs-standard, never instead of it: units per
        hour says nothing about how hard the work was.
        """
        if not self.duration_minutes:
            return None
        return q2(Decimal(self.quantity or ZERO) * _SIXTY / Decimal(self.duration_minutes))

    def accuracy_pct(self):
        """Clean units as a percentage of units completed — ``None`` when nothing was completed.

        Zero would read as "0% accurate" on an indirect row that never handled a unit, which is a
        quality verdict on work that never happened.
        """
        quantity = self.quantity or ZERO
        if quantity <= ZERO:
            return None
        return q2((quantity - (self.error_quantity or ZERO)) * _ONE_HUNDRED / quantity)
