"""SCM 4.15 Cold Chain Management — ``ColdChainMonitor`` [CCM-], the monitoring point.

A monitor is **one device, watching one thing, from one date, against these limits**. That sentence
is the whole model, and each clause in it is a reason this is a single table rather than two:

* **the device is not a master.** A ``Sensor`` / ``Device`` fleet table alongside a deployment table
  is the right shape for a company that *sells* loggers and has to track where its hardware is; here
  it would be pure overhead, because every question this sub-module asks ("was the product in
  range?", "how long was it out?", "is this probe still reporting?") is a question about the
  DEPLOYMENT. ``device_serial`` and ``device_type`` are two columns on the deployment instead.
* **a cold room IS a ``scm.Location``** (``location_type="zone"`` or ``"bin"``), so there is no
  ``ColdRoom`` table. 4.3 already owns the location hierarchy, the stock ledger hangs off it, and a
  parallel cold-room master would fork both.
* **a reefer IS a ``scm.Asset``.** 4.13 already carries the asset, its maintenance plans, its work
  orders and its meter log, so there is no ``Reefer`` table either — "Maintenance of Reefers" is a
  BOARD computed over 4.13, and 4.15 declares zero maintenance entities.

**The subject is three typed FKs, exactly one of which is set — never a ``GenericForeignKey``.**
``SupplyChainAlerts.py:109-114`` already settled this for SCM: *"a bare int carries neither a tenant
nor a type, so it can point at a deleted or cross-tenant row (L40 §3)."* ``SUBJECT_FIELDS`` names the
three in one place so ``clean()`` walks them and a template renders "what this watches" without a
three-branch if-chain.

**The subjects are ``PROTECT`` here, where ``SupplyChainAlert``'s are ``SET_NULL``, and the
difference is the point.** An alert is *history*: it must survive the thing it was about being
retired, so its subject goes null. A monitor is a *live configuration*, and a monitor with no
subject is uninterpretable — it also instantly violates its own exactly-one-subject rule, so the row
could never be saved again. You retire the monitor; you do not delete the cold room out from under
it. Every delete view that can reach a protected subject must catch ``ProtectedError`` and message
it rather than 500.

**The subject FREEZES once readings exist.** ``clean()`` refuses to re-point a monitor that already
has history, because an audit report must not be rewritable by moving the pointer under it: last
quarter's "Cold Room 2 was in range 99.4% of the time" would silently become a statement about
Cold Room 5.

--------------------------------------------------------------------------------------------------
TEMPERATURE COLUMNS ARE SIGNED. ``MinValueValidator(ZERO)`` IS A BUG HERE, NOT A CONSISTENCY FIX.
--------------------------------------------------------------------------------------------------
Every other decimal column in ``apps/scm`` carries ``MinValueValidator(ZERO)``, so adding one here
looks like tidying. It is not: **-18 °C is the normal operating point of half this sub-module**, and
a non-negative validator would reject every frozen limit, every frozen setpoint and every frozen
reading in the module. Temperature columns instead carry
``[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)]``.

``warning_margin_c`` IS bounded below by a positive number, and that is deliberate rather than
inconsistent — a margin is a **magnitude**, not a temperature. It is the one field on this model
that a non-negative bound is correct for, and it is flagged again at the field itself so the next
reader does not "fix" the temperatures to match it.

**Nothing in this sub-module passes a temperature through ``q2()`` or ``q4()``**, either. See
``TemperatureReadings.py`` for the full statement of that half of the rule.
--------------------------------------------------------------------------------------------------

**``status`` is USER-OWNED and the user is its only writer.** The detector never flips it — the
``Asset.status`` ruling (``Assets.py:12-19``): one writer per column, no drift. It is therefore ON
the create/edit form, in deliberate contrast to ``TemperatureExcursion.status``, which is
workflow-controlled and ``editable=False``. Do not "fix" either one to match the other.

**Nothing derived is stored.** In range, in the warning band, still reporting, calibration due, the
open episode, the open triage count — all of them are recomputed on read. A stored ``offline`` flag
or ``calibration_status`` column would need something to run every night to stay true, and nothing
runs every night here (the 4.12 licence-expiry / ``Asset.warranty_chip()`` ruling). Every one of
them answers **``None``** for "unknown" and never ``False``/``0``: an unknown that renders red is a
page that cries wolf, and a page that cries wolf is a page nobody reads.

**Compliance posture.** This model records ``calibrated_on`` / ``calibration_due_on`` /
``calibration_reference`` and every change to it goes through ``write_audit_log()``. That is an
audit TRAIL. It is **not** 21 CFR Part 11 / EU Annex 11 / GAMP 5 conformance and no docstring,
template or page may claim it is: there is no e-signature (no re-authentication at signing, no
stated meaning of signature, no tamper-evident record), no validated-system evidence and no
database-level immutability guarantee. Over-claiming here is worse than the gap.
"""
from datetime import timedelta

from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models._choices import (
    FROZEN_CONDITIONS,
    STORAGE_CONDITION_CHOICES,
)
from apps.scm.models.ColdChainManagement._choices import (
    CALIBRATION_NOTICE_DAYS,
    DEVICE_TYPE_CHOICES,
    MAX_EXCURSION_GRACE_MINUTES,
    MAX_HUMIDITY_PCT,
    MAX_LOGGING_INTERVAL_MINUTES,
    MAX_TEMPERATURE_C,
    MAX_WARNING_MARGIN_C,
    MIN_HUMIDITY_PCT,
    MIN_LOGGING_INTERVAL_MINUTES,
    MIN_TEMPERATURE_C,
    MONITOR_STATUS_CHOICES,
    MONITOR_STATUS_CSS,
    OPEN_EXCURSION_STATUSES,
    STALE_INTERVAL_MULTIPLIER,
)


class ColdChainMonitor(TenantNumbered):
    """One monitoring point [CCM-] — this device, watching this thing, against these limits."""

    NUMBER_PREFIX = "CCM"

    #: The three subject FKs, in one place: ``clean()`` walks them for the exactly-one rule and a
    #: template renders "what this watches" without a three-branch if-chain — the
    #: ``SupplyChainAlert.SUBJECT_FIELDS`` idiom (``SupplyChainAlerts.py:68-70``).
    SUBJECT_FIELDS = ("location", "asset", "shipment")

    #: Every outward FK whose target is tenant-scoped. ``clean()`` walks this list, so a pointer
    #: added later is covered by the cross-tenant guard the moment it is named here — the
    #: ``LaborSession.TENANT_SCOPED_FKS`` idiom rather than another copy of the same if-block.
    TENANT_SCOPED_FKS = ("location", "asset", "shipment")

    #: Public so the compliance report and the list-page chip filter the same set the model does.
    CALIBRATION_NOTICE_DAYS = CALIBRATION_NOTICE_DAYS

    # --- identity ----------------------------------------------------------------------------------
    name = models.CharField(max_length=255,
                            help_text="What this monitoring point is called, e.g. 'Cold Room 2 - top probe'")
    # DELIBERATELY NOT UNIQUE PER TENANT, and not indexed as unique either. A re-usable logger has
    # MANY deployments — one per shipment — and each is its own monitor row with its own limits and
    # its own reading history; that is the whole reason ELPRO, Controlant and Tive can run
    # single-use, re-usable and real-time devices through one database. The rule that IS enforced is
    # "no second ACTIVE monitor may share a serial", and it lives in clean() rather than in a
    # constraint for the Asset._validate_tag_code reason (Assets.py:251-258): MariaDB stores a blank
    # CharField as "" and not NULL, so a (tenant, device_serial) unique_together would permit exactly
    # ONE untagged monitor per workspace and reject the second with an IntegrityError 500.
    device_serial = models.CharField(max_length=64, blank=True,
                                     help_text="Logger / probe serial. Re-usable devices legitimately "
                                               "appear on many monitors — only one may be ACTIVE")
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES, default="fixed_sensor")

    # --- the subject: EXACTLY ONE of these three ---------------------------------------------------
    # Typed FKs, never a GenericForeignKey, and PROTECT rather than SET_NULL — see the module
    # docstring for both. All three are nullable at the database level because only one is ever set;
    # the exactly-one rule is clean()'s, since no column-level constraint can express it.
    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="cold_chain_monitors",
                                 help_text="Cold room, chiller zone or bin being monitored")
    asset = models.ForeignKey("scm.Asset", on_delete=models.PROTECT, null=True, blank=True,
                              related_name="cold_chain_monitors",
                              help_text="Reefer unit, chiller or freezer being monitored")
    shipment = models.ForeignKey("scm.Shipment", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="cold_chain_monitors",
                                 help_text="In-transit consignment being monitored")

    # --- the limits --------------------------------------------------------------------------------
    # All nullable: a ONE-SIDED limit is legitimate (a freezer that only ever needs a ceiling), and
    # the detector treats a null side as "no limit on that side" rather than as zero.
    storage_condition = models.CharField(
        max_length=14, choices=STORAGE_CONDITION_CHOICES, blank=True,
        help_text="Temperature class this point is held at — pre-fills the limits, never overrides them")
    # SIGNED. NEVER MinValueValidator(ZERO) — see the module docstring. -18 is an ordinary value here.
    min_temperature = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="Lower alarm limit in °C — blank means no lower limit")
    max_temperature = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="Upper alarm limit in °C — blank means no upper limit")
    # THE ONE NON-NEGATIVE FIELD IN THIS BLOCK, and it is correct: a margin is a MAGNITUDE, not a
    # temperature. Do not propagate this validator to the columns above it.
    warning_margin_c = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(MAX_WARNING_MARGIN_C)],
        help_text="Warn this many °C BEFORE a limit is reached (Sensitech's warning band)")
    # Humidity is genuinely non-negative — 0-100%. Recorded because four of the eleven surveyed
    # products treat it as co-equal with temperature; humidity EXCURSIONS are out of scope this pass.
    humidity_min = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(MIN_HUMIDITY_PCT), MaxValueValidator(MAX_HUMIDITY_PCT)],
        help_text="Lower relative-humidity limit, %")
    humidity_max = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(MIN_HUMIDITY_PCT), MaxValueValidator(MAX_HUMIDITY_PCT)],
        help_text="Upper relative-humidity limit, %")
    # What the unit was TOLD, not a command channel. ORBCOMM / Carrier Lynx Fleet / Thermo King all
    # ship two-way setpoint control; that is deferred, and this column is the RECORD of the setpoint
    # so `setpoint_gap()` can show a unit drifting away from what it was asked for.
    setpoint_temperature = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="What the unit is set to in °C — a record, not a control channel")

    # --- the rules the detector reads --------------------------------------------------------------
    # THE SINGLE MOST IMPORTANT FIELD IN THE SUB-MODULE. Without a grace period every door-open is an
    # incident, the queue fills with noise inside a week and then nobody reads it. ELPRO's
    # duration-outside-limits alarm criterion, Tive and Controlant all delay on duration.
    excursion_grace_minutes = models.PositiveIntegerField(
        default=30, validators=[MaxValueValidator(MAX_EXCURSION_GRACE_MINUTES)],
        help_text="How long a breach may run before it counts as a reportable excursion")
    logging_interval_minutes = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(MIN_LOGGING_INTERVAL_MINUTES),
                    MaxValueValidator(MAX_LOGGING_INTERVAL_MINUTES)],
        help_text="Minutes each reading summarises — SNAPSHOTTED onto every reading row as it is filed")

    # --- calibration: the one genuinely persistent audit artefact ----------------------------------
    # The certificate PDF attaches as a core.Document (the generic content_type/object_id attachment
    # the spine already ships) from the detail page — there is NO new attachment table here.
    calibrated_on = models.DateField(null=True, blank=True,
                                     help_text="Date of the last calibration certificate")
    calibration_due_on = models.DateField(null=True, blank=True,
                                          help_text="When the certificate lapses")
    calibration_reference = models.CharField(
        max_length=64, blank=True,
        help_text="Certificate number — ISO 17025 / NIST-traceable reference")

    # --- lifecycle ---------------------------------------------------------------------------------
    # USER-EDITABLE and ON the form. The detector never writes this column (the Asset.status ruling).
    # Deliberately unlike TemperatureExcursion.status, which is workflow-controlled and editable=False
    # — see the module docstring before "fixing" either one to match the other.
    status = models.CharField(max_length=16, choices=MONITOR_STATUS_CHOICES, default="active",
                              help_text="You own this column — no detector pass ever changes it")
    deployed_on = models.DateField(null=True, blank=True,
                                   help_text="When this deployment started — readings before it are refused")
    retired_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_ccm_tnt_status_idx"),
            # The active-serial rule in clean() runs this lookup on every save.
            models.Index(fields=["tenant", "device_serial"], name="scm_ccm_tnt_serial_idx"),
            # The three subject lookups: "what watches this cold room / reefer / shipment", read by
            # the location, asset and shipment detail panels.
            models.Index(fields=["tenant", "location"], name="scm_ccm_tnt_loc_idx"),
            models.Index(fields=["tenant", "asset"], name="scm_ccm_tnt_asset_idx"),
            models.Index(fields=["tenant", "shipment"], name="scm_ccm_tnt_shp_idx"),
            # The calibration chip and the compliance report's overdue list both order on this.
            models.Index(fields=["tenant", "calibration_due_on"], name="scm_ccm_tnt_caldue_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'CCM'} · {self.name}"

    # ---------------------------------------------------------------------------------------------
    # Validation — nine invariants, in this order
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """Everything that has to be true before a monitor can be detected against.

        These are refusals rather than badges because each one silently corrupts an AUDIT record if
        it is allowed through: a monitor with two subjects reports on neither, a re-pointed monitor
        rewrites last quarter's compliance figure, and an active monitor with no limit can never be
        in or out of range at all.
        """
        super().clean()

        # (1) THE GUARD, first — every rule below reads through these pointers. The form's querysets
        #     are tenant-scoped, but that is UX; a narrowed dropdown has never held against a crafted
        #     POST (L39 §2). Skipped when the instance has no tenant yet: an unsaved model has
        #     tenant_id None and ``self.tenant`` would raise RelatedObjectDoesNotExist rather than
        #     return None.
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

        # (2) Exactly one subject. Zero and two are different mistakes and get different messages.
        chosen = [name for name in self.SUBJECT_FIELDS
                  if getattr(self, f"{name}_id", None) is not None]
        if not chosen:
            raise ValidationError({
                "location": "A monitor has to watch something — choose a location, an asset or a "
                            "shipment."})
        if len(chosen) > 1:
            raise ValidationError({
                chosen[1]: "A monitor watches exactly one thing — clear the others."})

        # (3) The subject FREEZES once readings exist. An audit report must not be rewritable by
        #     re-pointing a monitor: every figure on the compliance pack is derived from THIS
        #     monitor's readings against THIS monitor's limits, and moving the pointer would silently
        #     restate all of them about a different cold room. The stored row is read ONCE, with only
        #     the three pointer columns loaded.
        if self.pk and self.tenant_id is not None:
            if self.readings.filter(tenant_id=self.tenant_id).exists():
                stored = (ColdChainMonitor.objects
                          .filter(pk=self.pk)
                          .only("location", "asset", "shipment")
                          .first())
                if stored is not None:
                    for name in self.SUBJECT_FIELDS:
                        if getattr(self, f"{name}_id", None) != getattr(stored, f"{name}_id", None):
                            raise ValidationError({
                                name: "This monitor already has readings, so what it watches is "
                                      "fixed — retire it and deploy a new monitor instead."})

        # (4) A band needs two distinct ends. STRICT: equal limits describe a band nothing can ever
        #     sit inside, so every reading would be an excursion in one direction or the other.
        if self.min_temperature is not None and self.max_temperature is not None:
            if self.max_temperature <= self.min_temperature:
                raise ValidationError({
                    "max_temperature": "The upper limit must be above the lower limit."})

        # (5) An ACTIVE monitor must have at least one limit — the 4.11 "an alert with no threshold"
        #     finding. Without one it can never be in or out of range, so every chip on every page
        #     reads "unknown" forever and the detector skips it silently. An inactive or
        #     in-calibration monitor is allowed to be limitless: that is how a point is parked while
        #     somebody works out what its band should be.
        if self.status == "active" and self.min_temperature is None and self.max_temperature is None:
            raise ValidationError({
                "min_temperature": "An active monitor needs at least one temperature limit — "
                                   "without one nothing can ever be in or out of range."})

        # (6) The humidity band, same rule one field over.
        if self.humidity_min is not None and self.humidity_max is not None:
            if self.humidity_max <= self.humidity_min:
                raise ValidationError({
                    "humidity_max": "The upper humidity limit must be above the lower limit."})

        # (7) The warning band has to fit INSIDE the band. A margin at or past half the width means
        #     the two warning zones meet or overlap in the middle, so the monitor warns while sitting
        #     exactly where it is supposed to be — and a warning that is always on is a warning
        #     nobody looks at.
        if (self.warning_margin_c is not None
                and self.min_temperature is not None and self.max_temperature is not None):
            if self.warning_margin_c * 2 >= (self.max_temperature - self.min_temperature):
                raise ValidationError({
                    "warning_margin_c": "The warning margin must be less than half the band width, "
                                        "or the monitor warns inside its own safe zone."})

        # (8) Date order. Both pairs, both optional, both checked only when complete.
        if self.deployed_on and self.retired_on and self.retired_on < self.deployed_on:
            raise ValidationError({"retired_on": "A monitor cannot be retired before it was deployed."})
        if self.calibrated_on and self.calibration_due_on and self.calibration_due_on < self.calibrated_on:
            raise ValidationError({
                "calibration_due_on": "The calibration due date cannot be before the calibration date."})

        # (9) One ACTIVE deployment per physical device. Historic deployments of the same re-usable
        #     logger are fine and expected — what is not fine is two live monitors claiming the same
        #     probe, because the readings arriving from it have no defined home and the two would
        #     report different verdicts about the same hardware. In clean() and NOT in a partial
        #     unique index: MariaDB has no partial indexes (Django SILENTLY omits a conditional
        #     UniqueConstraint on this backend while SQLite, which the tests run on, honours it — a
        #     guard that exists only under test is more dangerous than no guard), and a blank serial
        #     is "" rather than NULL, so a plain unique_together would allow exactly one
        #     serial-less monitor per workspace.
        if self.device_serial and self.status == "active" and self.tenant_id is not None:
            clash = (ColdChainMonitor.objects
                     .filter(tenant_id=self.tenant_id, device_serial=self.device_serial,
                             status="active")
                     .exclude(pk=self.pk)
                     .first())
            if clash is not None:
                raise ValidationError({
                    "device_serial": f"Device {self.device_serial} is already deployed on "
                                     f"{clash.number or 'another monitor'} ({clash.name}) — retire "
                                     f"that deployment before starting this one."})

    # ---------------------------------------------------------------------------------------------
    # The subject
    # ---------------------------------------------------------------------------------------------
    @property
    def subject(self):
        """The one thing this monitor watches, or ``None`` on a row that predates the rule."""
        for name in self.SUBJECT_FIELDS:
            if getattr(self, f"{name}_id", None) is not None:
                return getattr(self, name, None)
        return None

    @property
    def subject_kind(self):
        """``"location"`` / ``"asset"`` / ``"shipment"`` / ``""`` — what KIND of thing is watched.

        Templates branch on this to pick an icon and a detail-page URL; nothing branches on
        ``isinstance``, which would need three model imports in a template tag.
        """
        for name in self.SUBJECT_FIELDS:
            if getattr(self, f"{name}_id", None) is not None:
                return name
        return ""

    @property
    def subject_label(self):
        """The one line that says what this is about, for a list row with no space for three FKs —
        the ``SupplyChainAlert.subject_label`` shape."""
        subject = self.subject
        return str(subject) if subject is not None else "Unassigned"

    # ---------------------------------------------------------------------------------------------
    # Derived — NOTHING below is stored
    # ---------------------------------------------------------------------------------------------
    def latest_reading(self):
        """The newest reading on this monitor, or ``None``.

        The ``tenant_id=`` is **REDUNDANT AND LOAD-BEARING** — the house idiom, and the measured
        ``Asset.latest_reading()`` finding (``Assets.py:616-625``, ``MeterReadings.py:101-116``).
        ``scm_tmp_tnt_mon_idx`` is ``(tenant, monitor, reading_at)`` and ``tenant_id`` is the LEADING
        column, so a query that reaches this table through the related manager alone states no
        tenant, cannot open that index, and falls back to the plain FK index plus a filesort over the
        monitor's entire history to find one row. The related manager already constrains by
        ``monitor``, which implies the tenant, so this narrows nothing and costs no query —
        ``self.tenant_id`` is already on the instance. **A reader adding a third caller to this
        table owes the same line.**

        The ordering is stated explicitly rather than inherited from ``TemperatureReading.Meta``: a
        reader of this method should not have to open another file to know which row comes back.
        """
        return (self.readings.filter(tenant_id=self.tenant_id)
                .order_by("-reading_at", "-id")
                .first())

    def effective_limits(self):
        """``(min, max)`` — the pair the detector SNAPSHOTS onto an excursion at fire time.

        One accessor rather than two attribute reads scattered across the detector, the profile and
        three templates, so "what limits are in force" has a single answer.
        """
        return self.min_temperature, self.max_temperature

    def _reading_temperature(self, reading=None):
        """The temperature to judge, or ``None`` when there is nothing to judge.

        ``reading`` is resolved to the latest row when not supplied, so a page that has already
        fetched it pays for one query instead of four (the ``CycleCountTask.variance_count(lines)``
        idiom).
        """
        row = self.latest_reading() if reading is None else reading
        return getattr(row, "temperature", None)

    def is_in_range(self, reading=None):
        """``True`` / ``False`` / **``None``**, where ``None`` means "we cannot say".

        ``None`` when there is no reading, or no limit at all. **Never ``False`` for unknown** — a
        page that renders an unmonitored point red is a page that cries wolf, and after a week of it
        the red means nothing. A one-sided band is judged on the side it has.
        """
        temperature = self._reading_temperature(reading)
        if temperature is None:
            return None
        if self.min_temperature is None and self.max_temperature is None:
            return None
        if self.min_temperature is not None and temperature < self.min_temperature:
            return False
        if self.max_temperature is not None and temperature > self.max_temperature:
            return False
        return True

    def is_in_warning_band(self, reading=None):
        """Inside the limits but within ``warning_margin_c`` of one — Sensitech's warning band.

        Tri-state for the same reason as :meth:`is_in_range`: ``None`` when there is no reading, no
        margin configured or no limits. An ALREADY out-of-range point answers ``False`` here — it is
        an excursion, not a warning, and double-badging it would make the warning colour meaningless.
        """
        temperature = self._reading_temperature(reading)
        if temperature is None or self.warning_margin_c is None:
            return None
        if self.min_temperature is None and self.max_temperature is None:
            return None
        if self.is_in_range(reading) is not True:
            return False
        if self.min_temperature is not None and temperature < self.min_temperature + self.warning_margin_c:
            return True
        if self.max_temperature is not None and temperature > self.max_temperature - self.warning_margin_c:
            return True
        return False

    def is_reporting(self, now=None):
        """Is this monitor still sending? ``True`` / ``False`` / **``None``**.

        ``False`` once the newest reading is older than ``STALE_INTERVAL_MULTIPLIER`` logging
        intervals — a probe that has gone quiet is watching nothing, which is the failure mode
        Controlant's device-health assessments, ELPRO's missing-logger alerts and Berlinger's device
        delivery rates all exist to catch. **``None`` when there has never been a reading at all**,
        because "not yet commissioned" and "stopped reporting" are different problems with different
        fixes.

        There is deliberately no stored ``offline`` flag: this answer changes by the clock ticking,
        and a stored one would need a nightly job to stay true (the ``Asset.warranty_chip()`` ruling).
        """
        row = self.latest_reading()
        if row is None or row.reading_at is None:
            return None
        interval = self.logging_interval_minutes or MIN_LOGGING_INTERVAL_MINUTES
        deadline = row.reading_at + timedelta(minutes=interval * STALE_INTERVAL_MULTIPLIER)
        return (now or timezone.now()) <= deadline

    def open_episode(self):
        """The still-running excursion on this monitor, or ``None`` — **the detector's de-dupe
        target**, and the row it re-fires instead of raising a second one.

        "Still running" is ``ended_at IS NULL`` and has nothing to do with triage status: a closed
        episode can be under investigation for a week, and a running one can already be assessed.
        See :meth:`open_excursion_count` for the other question.

        The redundant ``tenant_id`` buys ``scm_exc_tnt_ended_idx`` — same rule as
        :meth:`latest_reading`.
        """
        return (self.excursions.filter(tenant_id=self.tenant_id, ended_at__isnull=True)
                .order_by("-started_at")
                .first())

    def open_excursion_count(self):
        """How many excursions on this monitor still need a human — **a TRIAGE count**.

        Named apart from :meth:`open_episode` on purpose. An episode can be over (``ended_at`` set)
        while its triage is still open, and a page that conflated the two would tell somebody an
        incident is still happening when it stopped yesterday.
        """
        return (self.excursions
                .filter(tenant_id=self.tenant_id, status__in=OPEN_EXCURSION_STATUSES)
                .count())

    def days_to_calibration_due(self, today=None):
        """Days until the certificate lapses (negative once past), or ``None`` if none is recorded."""
        if not self.calibration_due_on:
            return None
        return (self.calibration_due_on - (today or timezone.localdate())).days

    def is_calibration_due(self, today=None):
        """``True`` once the certificate is inside the notice window or already lapsed.

        ``False`` when it is comfortably in date, and ``False`` — not ``True`` — when no calibration
        is recorded at all: "no certificate on file" is a data-completeness problem the compliance
        report lists separately, not a due date that has arrived.
        """
        days = self.days_to_calibration_due(today)
        return days is not None and days <= self.CALIBRATION_NOTICE_DAYS

    def setpoint_gap(self, reading=None):
        """Latest temperature minus the setpoint, or ``None`` when either is missing.

        The number that shows a unit drifting away from what it was told — ORBCOMM, Carrier Lynx
        Fleet and Thermo King all surface it. ``None`` rather than ``0`` when there is no setpoint:
        a gap of zero means "exactly on setpoint", which is the opposite of "we never recorded one".
        """
        temperature = self._reading_temperature(reading)
        if temperature is None or self.setpoint_temperature is None:
            return None
        return (temperature - self.setpoint_temperature).quantize(Decimal("0.01"))

    @property
    def is_frozen_condition(self):
        """Is this a frozen / deep-frozen / cryogenic point? Drives MKT's honest ``None``.

        USP <1079.2> states mean kinetic temperature does not apply to frozen product, so quoting a
        figure for one would let a warm spell be "offset" by the cold hours either side of it.
        """
        return self.storage_condition in FROZEN_CONDITIONS

    # ---------------------------------------------------------------------------------------------
    # Chips — ``(label, css)`` pairs; templates read ``.0`` and ``.1``
    # ---------------------------------------------------------------------------------------------
    # "Not recorded" is its OWN muted state everywhere below and is never green: not knowing whether
    # a probe is in range, reporting or in calibration is not the same as knowing that it is. That
    # is the Asset.warranty_chip() rule, and it is the difference between a blank that makes someone
    # go and look and a green tile that stops them.

    def range_chip(self, reading=None):
        """Where the monitor sits against its band right now."""
        in_range = self.is_in_range(reading)
        if in_range is None:
            return ("Not recorded", "badge-muted")
        if in_range is False:
            return ("Out of range", "badge-red")
        if self.is_in_warning_band(reading) is True:
            return ("Near limit", "badge-amber")
        return ("In range", "badge-green")

    def reporting_chip(self, now=None):
        """Whether the device is still sending — the missing-logger chip."""
        reporting = self.is_reporting(now)
        if reporting is None:
            return ("No readings", "badge-muted")
        return ("Reporting", "badge-green") if reporting else ("Not reporting", "badge-red")

    def calibration_chip(self, today=None):
        """Certificate state, on the ``Asset.warranty_chip()`` shape."""
        days = self.days_to_calibration_due(today)
        if days is None:
            return ("Not recorded", "badge-muted")
        if days < 0:
            return ("Calibration overdue", "badge-red")
        if days == 0:
            return ("Due today", "badge-amber")
        if days <= self.CALIBRATION_NOTICE_DAYS:
            return (f"{days} days left", "badge-amber")
        return ("In calibration date", "badge-green")

    @property
    def status_css(self):
        """theme.css badge class for :attr:`status` — one lookup, so no template invents a colour."""
        return MONITOR_STATUS_CSS.get(self.status, "badge-muted")
