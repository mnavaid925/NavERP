"""SCM 4.15 Cold Chain Management — ``TemperatureExcursion`` [EXC-], the episode and its judgement.

An excursion is **one continuous period during which a monitor was outside its limits**, plus what a
human decided about it. The two halves are written by two different owners and must never be
confused, which is the ``SupplyChainAlert`` detector-vs-triage split (``SupplyChainAlerts.py:1-8``)
applied one domain over:

* **the measured half is DETECTOR-WRITTEN and every column of it is ``editable=False``.**
  ``started_at`` / ``ended_at`` / ``duration_minutes`` / ``breach_direction`` /
  ``extreme_temperature`` / ``limit_min`` / ``limit_max`` / ``reading_count`` / ``mkt`` /
  ``last_detected_at`` are computed by ``apps/scm/coldchain.py`` from the reading ledger, and no form
  in this app touches any of them. A measurement a user can retype is not a measurement.
* **the human half is the only writable block:** severity, the product assessment, the cause code,
  the corrective action, and the links out to the NCR / work order / lot that somebody else acts on.

**``limit_min`` / ``limit_max`` are a SNAPSHOT taken when the episode opened, and they are never
re-written when it extends.** The record must read the same next year: if the limits are widened
next month, an audit reader has to still see the band that was actually in force when this fired.
Same rule as ``LaborActivity.standard_minutes_snapshot``, ``CycleCountTaskLine.expected_quantity``
and ``MaintenanceWorkOrderTask``.

**``mkt`` is nullable and answers ``None`` honestly.** Mean kinetic temperature does not apply to
frozen / deep-frozen / cryogenic product (USP <1079.2>) and cannot be computed for a window with no
readings. It is **never 0** in either case: an MKT of 0 °C reads as a perfectly-cold shipment, which
is the precise opposite of "we do not know" — the 4.13 "an honest figure can answer ``None``, never
0" rule.

--------------------------------------------------------------------------------------------------
"ONE OPEN EPISODE PER MONITOR" IS A DETECTOR GUARD, NOT A DATABASE CONSTRAINT
--------------------------------------------------------------------------------------------------
The shape that *looks* right is
``UniqueConstraint(fields=["tenant", "monitor"], condition=Q(ended_at__isnull=True))``. It is wrong
twice over, and ``SupplyChainAlerts.py:17-37`` already recorded the finding for this app:

* **MariaDB has no partial indexes**, so Django SILENTLY omits a conditional constraint on this
  backend — it would protect nothing in the deployment that matters. Worse, the test settings run on
  SQLite, which *does* support them: the constraint would be created there, pass every test, and be
  absent in production. *A guard that exists only under test is more dangerous than no guard.*
* **a constraint can only REFUSE a write; it cannot MERGE one**, and merging is the actual rule here
  — a breach that keeps breaching must re-fire the existing open episode (moving ``last_detected_at``
  and extending the duration), not raise a second row.

So the rule lives in ``coldchain.detect_excursions()``, inside ``transaction.atomic()``, behind a
``select_for_update()`` **on the monitor row** taken *before* any reading is read. The monitor row
always exists, so the lock is never a no-op, and it also serialises the reading-import path against
the detector.

:meth:`clean` below carries a belt-and-braces copy of the same rule for the form path. **It is NOT
the concurrency guard** and must never be mistaken for one: a form runs outside the detector's
transaction and its lock, so two simultaneous posts can both pass it. It exists to stop a
hand-created row from landing on top of a live episode, nothing more.
--------------------------------------------------------------------------------------------------

**Nothing here re-declares what a sibling sub-module owns.** There is no second disposition
vocabulary (4.9's ``DISPOSITION_CHOICES``), no second CAPA table (4.9's ``CapaAction``), no second
alert queue (4.11's ``SupplyChainAlert`` — that one is generic and carries no *episode*), no second
quarantine mechanism (4.9 flips ``LotSerial.status``; **4.15 reads that column and never writes
it**), and no ``accounting.JournalEntry`` (L29). The three FKs out are one-way pointers, exactly the
``MaintenanceWorkOrder.non_conformance`` precedent (``MaintenanceWorkOrders.py:175-179``), and 4.15
adds **no reciprocal value to any 4.9 or 4.13 vocabulary**.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.ColdChainManagement._choices import (
    ASSESSMENT_CHOICES,
    ASSESSMENT_CSS,
    BREACH_DIRECTION_CHOICES,
    BREACH_DIRECTION_CSS,
    EDITABLE_EXCURSION_STATUSES,
    EXCURSION_CAUSE_CHOICES,
    EXCURSION_SEVERITY_CHOICES,
    EXCURSION_SEVERITY_CSS,
    EXCURSION_STATUS_CHOICES,
    EXCURSION_STATUS_CSS,
    MAX_EXCURSION_MINUTES,
    MAX_TEMPERATURE_C,
    MIN_TEMPERATURE_C,
    OPEN_EXCURSION_STATUSES,
)


class TemperatureExcursion(TenantNumbered):
    """One out-of-limits episode [EXC-] — what was measured, and what a person decided about it."""

    NUMBER_PREFIX = "EXC"

    #: Triage still outstanding — the gate every workflow verb below shares. Owned by ``_choices``
    #: so the detector, the model and the pages that filter on it cannot drift apart.
    OPEN_STATUSES = OPEN_EXCURSION_STATUSES

    #: Statuses in which the human block may still be edited on the form.
    EDITABLE_STATUSES = EDITABLE_EXCURSION_STATUSES

    #: Terminal. Stated as the closed set rather than derived from the open one so a status added
    #: later (``awaiting_lab``, say) counts as OPEN by default — that errs towards keeping a row on
    #: somebody's queue, which is the safe direction to be wrong in.
    CLOSED_STATUSES = ("closed", "dismissed")

    #: Colour lookups pulled from ``_choices`` so a badge is styled in exactly one place. Only the
    #: two whose ``_choices`` name differs are re-bound here; ``ASSESSMENT_CSS`` and
    #: ``BREACH_DIRECTION_CSS`` are read straight off the module import by their properties below,
    #: because ``NAME = NAME`` inside a class body reads as a typo even when it works.
    STATUS_CSS = EXCURSION_STATUS_CSS
    SEVERITY_CSS = EXCURSION_SEVERITY_CSS

    #: Every outward FK whose target is tenant-scoped. ``clean()`` walks this list — the
    #: ``LaborSession.TENANT_SCOPED_FKS`` idiom rather than a fourth copy of the same if-block. The
    #: two ``AUTH_USER_MODEL``/``core.Party`` stamps are absent on purpose: they are written from the
    #: verbs and are ``editable=False``, so no request path can carry a crafted pk into them.
    TENANT_SCOPED_FKS = ("monitor", "non_conformance", "maintenance_work_order", "lot_serial")

    # PROTECT — the record must survive. You retire a monitor; you do not delete the evidence that it
    # fired. (Contrast TemperatureReading.monitor, which is CASCADE: a raw interval summary is
    # meaningless without the deployment that defines its limits, while an excursion carries its own
    # snapshotted limits and stays readable forever.)
    monitor = models.ForeignKey("scm.ColdChainMonitor", on_delete=models.PROTECT,
                                related_name="excursions")

    # ---------------------------------------------------------------------------------------------
    # DETECTOR-WRITTEN — every column below is editable=False and no form ever touches one
    # ---------------------------------------------------------------------------------------------
    started_at = models.DateTimeField(editable=False,
                                      help_text="First reading outside the limits")
    # NULL MEANS THE EPISODE IS STILL RUNNING — the detector's de-dupe target, and the one thing
    # `close()` refuses to work around.
    ended_at = models.DateTimeField(null=True, blank=True, editable=False,
                                    help_text="First reading back inside the limits — null while it "
                                              "is still breaching")
    duration_minutes = models.PositiveIntegerField(
        default=0, editable=False, validators=[MaxValueValidator(MAX_EXCURSION_MINUTES)],
        help_text="Minutes outside the limits, minute-weighted from the reading intervals")
    breach_direction = models.CharField(max_length=6, choices=BREACH_DIRECTION_CHOICES,
                                        default="high", editable=False)
    # Signed and bounded, NEVER MinValueValidator(ZERO) and never through q4() — see
    # TemperatureReadings.py for the full statement of the rule. The worst value seen in the window;
    # null when the window somehow held no readable temperature.
    extreme_temperature = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, editable=False,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="Worst temperature reached during the episode, °C")

    # THE SNAPSHOT of what was in force when this fired. Written at OPEN time and never re-written on
    # extend — see the module docstring. Nullable because a one-sided band is legitimate.
    limit_min = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, editable=False,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="The lower limit in force when the episode opened")
    limit_max = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, editable=False,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="The upper limit in force when the episode opened")

    reading_count = models.PositiveIntegerField(
        default=0, editable=False, help_text="How many reading rows fall inside the episode window")
    # Nullable and HONESTLY None for a frozen / deep-frozen / cryogenic monitor and for a window with
    # no readings. Never 0 — see the module docstring.
    mkt = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, editable=False,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="Mean kinetic temperature over the episode, °C — blank when it does not apply")
    # The re-fire stamp (the SupplyChainAlert.last_seen_at idiom): a breach that keeps breaching
    # shows "still breaching" by moving this, WITHOUT a duplicate row.
    last_detected_at = models.DateTimeField(default=timezone.now, editable=False)

    # ---------------------------------------------------------------------------------------------
    # HUMAN TRIAGE — the only writable block
    # ---------------------------------------------------------------------------------------------
    # WORKFLOW-CONTROLLED (L22): moved only by the four verbs at the foot of this class, each of
    # which validates what it is doing. Note the DELIBERATE contrast with ColdChainMonitor.status,
    # which IS on its form because it is user-owned lifecycle rather than workflow state. Do not
    # "fix" either one to match the other.
    status = models.CharField(max_length=16, choices=EXCURSION_STATUS_CHOICES, default="open",
                              editable=False)
    # Seeded by the detector at OPEN time and human-writable afterwards. The detector must NOT
    # overwrite it on a later pass — a triager's downgrade has to survive the next detection run, or
    # the queue silently re-escalates everything anybody has already judged.
    severity = models.CharField(max_length=10, choices=EXCURSION_SEVERITY_CHOICES, default="major")

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="scm_excursions_acknowledged")
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)

    # The PRODUCT-LEVEL RELEASE DECISION — ELPRO's "assess at product level to reduce unnecessary
    # quarantines", Sensitech's "faster, more precise release decisions". The disposition that
    # FOLLOWS from it is 4.9's and is reached through `non_conformance`, never re-declared here.
    assessment = models.CharField(max_length=20, choices=ASSESSMENT_CHOICES, default="pending")
    # core.Party rather than a login: the person who signs off product quality is frequently a QA
    # lead with no ERP account, and Party is how SCM has named a person since 4.8. SET_NULL — the
    # assessment outlives the assessor.
    assessed_by = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="scm_excursion_assessments")
    assessed_on = models.DateTimeField(null=True, blank=True, editable=False)

    cause = models.CharField(max_length=20, choices=EXCURSION_CAUSE_CHOICES, blank=True,
                             help_text="Closed vocabulary so 'what costs us the most spoilage' is a "
                                       "GROUP BY rather than a pile of free text")
    corrective_action = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # ---------------------------------------------------------------------------------------------
    # LINKS OUT — all SET_NULL, all one-way, and NO reciprocal vocabulary edit anywhere
    # ---------------------------------------------------------------------------------------------
    # 4.9 owns disposition, the quarantine verb that flips LotSerial.status, and cost_of_quality.
    # 4.13 owns the repair. 4.15 records the verdict and POINTS at the row somebody else acts on —
    # the MaintenanceWorkOrder.non_conformance precedent (MaintenanceWorkOrders.py:175-179).
    non_conformance = models.ForeignKey(
        "scm.NonConformance", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cold_chain_excursions",
        help_text="The NCR raised for affected product — 4.9 owns the disposition")
    maintenance_work_order = models.ForeignKey(
        "scm.MaintenanceWorkOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cold_chain_excursions",
        help_text="The repair job raised against the failing unit — 4.13 owns the work")
    lot_serial = models.ForeignKey(
        "scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cold_chain_excursions",
        help_text="The affected batch — this module READS its status and never writes it")

    class Meta:
        ordering = ["-started_at", "-id"]
        unique_together = ("tenant", "number")
        # NO UniqueConstraint(condition=…) HERE, EVER — MariaDB silently omits partial indexes while
        # the SQLite test settings honour them, so such a guard would pass every test and be absent
        # in production; and a constraint can only refuse a write, never merge one, which is the
        # actual rule. See the module docstring: the guard is the detector's row lock.
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_exc_tnt_status_idx"),
            models.Index(fields=["tenant", "monitor", "started_at"], name="scm_exc_tnt_mon_idx"),
            models.Index(fields=["tenant", "started_at"], name="scm_exc_tnt_start_idx"),
            models.Index(fields=["tenant", "severity"], name="scm_exc_tnt_sev_idx"),
            # THE DETECTOR'S HOT PATH: one lookup for the still-running episode, per monitor, per
            # pass — and the same index serves "everything still breaching right now" on the board.
            models.Index(fields=["tenant", "ended_at"], name="scm_exc_tnt_ended_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'EXC'} · {self.get_breach_direction_display()}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        super().clean()

        # THE GUARD, first. The form's querysets are tenant-scoped, but that is UX — a narrowed
        # dropdown has never held against a crafted POST (L39 §2), and this row can point at an NCR,
        # a work order and a lot. Skipped when the instance has no tenant yet: an unsaved model has
        # tenant_id None and self.tenant would raise RelatedObjectDoesNotExist on a non-nullable FK.
        if self.tenant_id is not None:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None instead of 500-ing inside validation.
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another workspace."})

        # An episode that ended before it started derives a negative duration, and every figure built
        # on it inverts.
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({"ended_at": "An excursion cannot end before it started."})

        # A future start would put an incident on the board for weather nobody has had yet, and
        # live_duration_minutes() would run negative until the clock caught up.
        if self.started_at and self.started_at > timezone.now():
            raise ValidationError({"started_at": "An excursion cannot start in the future."})

        # The snapshotted band has to be a band.
        if (self.limit_min is not None and self.limit_max is not None
                and self.limit_min > self.limit_max):
            raise ValidationError({"limit_max": "The upper limit cannot be below the lower limit."})

        # A verdict that product was affected, with no recorded action and no NCR, is not an audit
        # record — it is a note. Either the action is written down here or the row that carries it is
        # linked, and 4.9 owns that row.
        if (self.assessment == "product_affected" and not (self.corrective_action or "").strip()
                and self.non_conformance_id is None):
            raise ValidationError({
                "corrective_action": "Record what was done, or link the non-conformance that acts "
                                     "on it — an affected-product verdict with neither is not an "
                                     "audit record."})

        # BELT AND BRACES ONLY — **THIS IS NOT THE CONCURRENCY GUARD.** A form runs outside the
        # detector's transaction and outside its row lock, so two simultaneous posts can both pass
        # this check and both insert. The real guard is coldchain.detect_excursions(), which takes
        # select_for_update() on the MONITOR row before it reads anything. This exists so a
        # hand-created row cannot land on top of a live episode on the normal single-user path, and
        # it must never be cited as the reason a database constraint is unnecessary — the reason for
        # that is in the module docstring.
        if self.ended_at is None and self.monitor_id is not None and self.tenant_id is not None:
            clash = (TemperatureExcursion.objects
                     .filter(tenant_id=self.tenant_id, monitor_id=self.monitor_id,
                             ended_at__isnull=True)
                     .exclude(pk=self.pk)
                     .first())
            if clash is not None:
                raise ValidationError({
                    "monitor": f"{clash.number or 'An excursion'} on this monitor is still running "
                               f"— an episode is extended, never duplicated."})

    # ---------------------------------------------------------------------------------------------
    # Derived — NOTHING below is stored
    # ---------------------------------------------------------------------------------------------
    @property
    def is_open(self):
        """Is the TRIAGE still outstanding? The gate every workflow verb shares."""
        return self.status in self.OPEN_STATUSES

    @property
    def is_episode_running(self):
        """Is the monitor STILL OUT OF LIMITS right now?

        Named apart from :attr:`is_open` deliberately, and the two are genuinely independent: an
        episode that stopped yesterday can still be under investigation, and one that is still
        breaching can already be assessed. A page that conflated them would tell somebody an
        incident is ongoing when it ended, or that it is over when the freezer is still warming.
        """
        return self.ended_at is None

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    def live_duration_minutes(self, now=None):
        """Minutes out of limits — the stored figure once closed, the live one while it runs.

        The clock is read ONCE per call so two figures rendered on one page cannot disagree (the
        ``Asset._reliability_agg`` open-window rule: a window still running contributes to the
        FIGURE but not to the stored column). Clamped to ``MAX_EXCURSION_MINUTES`` because this
        number is fed to ``timedelta(minutes=…)`` downstream, where an out-of-range value is an
        ``OverflowError`` — a 500, not a message.
        """
        if self.ended_at is not None:
            return self.duration_minutes or 0
        if not self.started_at:
            return 0
        elapsed = int(((now or timezone.now()) - self.started_at).total_seconds() // 60)
        return max(0, min(elapsed, MAX_EXCURSION_MINUTES))

    @property
    def is_reportable(self):
        """Has this episode outlived the monitor's grace period?

        **Tier 2, derived, never stored.** The grace period is a monitor SETTING, and editing it has
        to move this answer — a stored ``reportable`` flag would freeze last month's policy onto
        this month's episodes and nothing would ever recompute it. That is the same ruling that
        keeps ``is_reporting`` and the calibration chip off the columns list.
        """
        grace = getattr(self.monitor, "excursion_grace_minutes", 0) or 0
        return self.live_duration_minutes() >= grace

    def excess_c(self):
        """How far past the SNAPSHOTTED limit the extreme went, or ``None``.

        ``None`` — never ``0`` — when there is no extreme recorded or no limit on the breached side:
        an excess of zero means "it touched the limit exactly", which is a different statement from
        "we cannot compute this".
        """
        if self.extreme_temperature is None:
            return None
        gaps = []
        if self.breach_direction in ("high", "both") and self.limit_max is not None:
            gaps.append(self.extreme_temperature - self.limit_max)
        if self.breach_direction in ("low", "both") and self.limit_min is not None:
            gaps.append(self.limit_min - self.extreme_temperature)
        if not gaps:
            return None
        return max(gaps).quantize(Decimal("0.01"))

    def readings(self):
        """The reading rows that fall inside the episode window.

        Reached through the monitor's related manager rather than by importing
        ``TemperatureReading``, so this module imports no sibling entity module (the
        ``Asset.open_jobs()`` posture). A still-running episode is bounded at "now", so the window is
        always closed and the query always ranged.

        The ``tenant_id=`` is REDUNDANT and load-bearing — ``scm_tmp_tnt_mon_idx`` is
        ``(tenant, monitor, reading_at)`` and ``tenant_id`` is the LEADING column, so without it
        MariaDB falls back to the plain FK index and filesorts. See
        ``ColdChainMonitor.latest_reading()``.
        """
        end = self.ended_at or timezone.now()
        return (self.monitor.readings
                .filter(tenant_id=self.tenant_id,
                        reading_at__gte=self.started_at, reading_at__lte=end)
                .order_by("reading_at", "id"))

    @property
    def status_css(self):
        """Colour for :attr:`status` — open is red because open means unattended."""
        return self.STATUS_CSS.get(self.status, "badge-muted")

    @property
    def severity_css(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-muted")

    @property
    def assessment_css(self):
        return ASSESSMENT_CSS.get(self.assessment, "badge-muted")

    @property
    def breach_direction_css(self):
        return BREACH_DIRECTION_CSS.get(self.breach_direction, "badge-muted")

    # ---------------------------------------------------------------------------------------------
    # Workflow — the ONLY writers of the triage columns
    # ---------------------------------------------------------------------------------------------
    # Each returns the ``{field: [before, after]}`` diff for ``write_audit_log``, or ``{}`` when
    # nothing changed — the ``SupplyChainAlert`` contract, so the views stay thin and the seeder and
    # the tests drive the same code path the buttons do. **Every one is no-op safe**: re-acknowledging
    # must not blank the first acknowledger. A ValidationError is raised only for a caller-supplied
    # VALUE that is out of range, or for the one STATE refusal worth being loud about (closing an
    # episode that is still happening) — never for merely being in the wrong status, which stays a
    # silent no-op (the SupplyChainAlert.snooze split, SupplyChainAlerts.py:293-305).

    @staticmethod
    def _actor(user):
        """A saveable user or ``None`` — a view is ``@login_required``, but an ``AnonymousUser``
        passed by a management command would otherwise raise on assignment rather than simply going
        unattributed (``SupplyChainAlerts.py:246-250``)."""
        return user if getattr(user, "pk", None) else None

    @staticmethod
    def _party(party):
        """The ``core.Party`` sibling of :meth:`_actor` — an unsaved or absent party goes null."""
        return party if getattr(party, "pk", None) else None

    def _stamp_seen(self, user, changes, fields):
        """Record that a human looked at this, if nobody has been recorded yet.

        Closing or dismissing an excursion means somebody saw it, and a terminal row with no person
        attached to it anywhere is the audit hole the ``SupplyChainAlert.resolved_by`` comment names.
        There is deliberately no separate ``closed_by`` column — ``status`` is what says whether the
        episode was acted on or judged not worth acting on, and the acting login is also captured by
        ``write_audit_log`` from the returned diff. The first acknowledger always wins: this only
        ever fills a blank.
        """
        if self.acknowledged_by_id is not None or self.acknowledged_at is not None:
            return
        actor = self._actor(user)
        if actor is None:
            return
        self.acknowledged_by = actor
        self.acknowledged_at = timezone.now()
        changes["acknowledged_by"] = ["", str(actor)]
        fields.extend(["acknowledged_by", "acknowledged_at"])

    def acknowledge(self, user):
        """Somebody has seen it → ``investigating``. No-op once past ``open``: the first
        acknowledger is the true one, and re-acknowledging must not overwrite them."""
        if not self.is_open or self.status != "open":
            return {}
        changes = {"status": [self.status, "investigating"]}
        self.status = "investigating"
        self.acknowledged_by = self._actor(user)
        self.acknowledged_at = timezone.now()
        # Only recorded when there IS somebody to record — an unattributed pass (a management
        # command's AnonymousUser) would otherwise put a ["", ""] no-change pair in the audit
        # payload, which reads as a field that was blanked.
        if self.acknowledged_by is not None:
            changes["acknowledged_by"] = ["", str(self.acknowledged_by)]
        self.save(update_fields=["status", "acknowledged_by", "acknowledged_at", "updated_at"])
        return changes

    def assess(self, party, assessment, cause="", corrective_action=""):
        """Record the PRODUCT-LEVEL verdict → ``assessed``.

        ``assessment`` is validated against the vocabulary here and not only on the form: a wrong
        VALUE is the caller's mistake and is rejected loudly, while a wrong STATE stays a silent
        no-op. ``product_affected`` additionally requires an action or a linked non-conformance —
        the same rule :meth:`clean` enforces, restated because this verb writes the column directly
        and never runs ``full_clean()``.

        The disposition that follows is 4.9's: this method records the verdict and **never** touches
        ``LotSerial.status``.
        """
        valid = dict(ASSESSMENT_CHOICES)
        if assessment not in valid:
            raise ValidationError({"assessment": "Choose a valid product assessment."})
        corrective_action = (corrective_action or "").strip()
        if assessment == "product_affected" and not (
                corrective_action or (self.corrective_action or "").strip()
                or self.non_conformance_id):
            raise ValidationError({
                "corrective_action": "Record what was done, or link the non-conformance that acts "
                                     "on it, before marking product affected."})
        if cause and cause not in dict(EXCURSION_CAUSE_CHOICES):
            raise ValidationError({"cause": "Choose a valid cause."})
        if not self.is_open:
            return {}

        changes = {}
        fields = ["updated_at"]
        if self.assessment != assessment:
            changes["assessment"] = [self.assessment, assessment]
            self.assessment = assessment
            fields.append("assessment")
        if cause and self.cause != cause:
            changes["cause"] = [self.cause, cause]
            self.cause = cause
            fields.append("cause")
        if corrective_action and self.corrective_action != corrective_action:
            # Truncated in the diff: the audit payload is an index of what changed, not a second copy
            # of the note.
            changes["corrective_action"] = [self.corrective_action[:200], corrective_action[:200]]
            self.corrective_action = corrective_action
            fields.append("corrective_action")
        if self.status != "assessed":
            changes["status"] = [self.status, "assessed"]
            self.status = "assessed"
            fields.append("status")
        if not changes:
            return {}
        # Re-stamped on every real change: an assessment is a signed judgement, so the name and the
        # moment must describe the verdict that is actually on the row now, not the first draft.
        self.assessed_by = self._party(party)
        self.assessed_on = timezone.now()
        fields.extend(["assessed_by", "assessed_on"])
        self.save(update_fields=fields)
        return changes

    def close(self, user, note=""):
        """Close it as dealt with → ``closed``.

        **Refuses while the episode is still running** (``ended_at is None``). This is the one STATE
        refusal in the sub-module worth being loud about: closing an incident that is still
        happening files a compliance record saying the product was back in range when the freezer is
        still warming, and every duration on the report would be understated. Run the detector (or
        wait for the next pass) so the episode is ended first.

        No-op once closed — re-closing must not blank the first note.
        """
        if self.is_episode_running:
            raise ValidationError({
                "status": "This excursion is still running — it cannot be closed until the monitor "
                          "is back inside its limits."})
        if not self.is_open:
            return {}
        changes = {"status": [self.status, "closed"]}
        fields = ["status", "updated_at"]
        self.status = "closed"
        note = (note or "").strip()
        if note:
            existing = (self.notes or "").strip()
            self.notes = f"{existing}\n{note}".strip() if existing else note
            changes["notes"] = ["", note[:200]]
            fields.append("notes")
        self._stamp_seen(user, changes, fields)
        self.save(update_fields=fields)
        return changes

    def dismiss(self, user):
        """Close it as not worth acting on → ``dismissed``.

        The honest terminal state for a blip that never outlived its grace period. Kept apart from
        ``closed`` so the compliance report can tell "we fixed it" from "we judged it a non-event" —
        collapsing the two would make the excursion count meaningless. No-op once closed.
        """
        if not self.is_open:
            return {}
        changes = {"status": [self.status, "dismissed"]}
        fields = ["status", "updated_at"]
        self.status = "dismissed"
        self._stamp_seen(user, changes, fields)
        self.save(update_fields=fields)
        return changes
