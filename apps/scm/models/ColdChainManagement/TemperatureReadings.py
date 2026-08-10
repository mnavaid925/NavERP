"""SCM 4.15 Cold Chain Management — ``TemperatureReading``, the append-only product-environment log.

This is the record of **what the goods actually experienced**: one row per logging interval per
monitor, forever. Every compliance figure in the sub-module — time in range, time out of range, mean
kinetic temperature, the excursion episodes themselves — is derived from these rows and from the
monitor's limits, and nothing about that derivation is stored anywhere.

**A row is an INTERVAL SUMMARY, not a raw sample.** It carries ``temperature`` (the representative
value for the window) plus optional ``min_temperature`` / ``max_temperature`` / ``sample_count``.
That is the shape a logger's own PDF summary and a gateway batch already emit, and it is what makes
the duration and MKT arithmetic correct, because **each row carries its own weight**. At the
30-minute default it is ~17.5k rows per monitor per year instead of ~105k at 5-minute sampling.

Four bounds keep the table finite, and they are the design rather than an afterthought:
``MAX_BATCH_READINGS`` per import; a list page that is always monitor-scoped **and** date-scoped;
``MAX_READING_WINDOW_DAYS`` on every chart and profile; and ``unique_together (monitor, reading_at)``
so a re-uploaded logger file cannot double the series.

**Retention is a NAMED NON-GOAL, not an oversight.** GDP wants years of records, so a default purge
would be exactly the wrong behaviour — the seam is a future ``purge_temperature_readings``
management command with a per-tenant window, deliberately not shipped this pass.

--------------------------------------------------------------------------------------------------
THE TWO-PART TRAP: ``MinValueValidator(ZERO)`` AND ``q4()`` ARE BOTH WRONG FOR A TEMPERATURE
--------------------------------------------------------------------------------------------------
They are separate bugs and each has bitten a different sub-module before.

**The validator.** Every other decimal in ``apps/scm`` carries ``MinValueValidator(ZERO)``, so
adding one here looks like restoring consistency. It would reject every frozen reading in the
module: -18 °C is the normal operating point of half of 4.15. Temperature columns carry
``[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)]`` instead.

**The helper.** ``_base.py:48`` — ``q4()`` is ``min(max(Decimal(value or ZERO), -MAX_Q4), MAX_Q4)``.
The *sign* survives the clamp, so at a glance it looks safe for a signed column. It is not:
**``value or ZERO`` turns ``None`` into ``Decimal("0")``, and 0 °C is a perfectly plausible
temperature.** A logger row with a blank temperature cell would import as "the fridge was at
freezing" — a wrong measurement that reads exactly like a real one, which is the worst possible
failure mode for a record that ends up in an audit pack.

**The rule for this whole sub-module: NO temperature, humidity or MKT value passes through ``q2()``
or ``q4()``.** A missing reading stays ``None``. Quantize with ``.quantize(Decimal("0.01"))`` applied
to a value already proven non-``None``, never with the clamping helpers. The importer **skips and
counts** a row whose temperature cell is blank or unparseable; it never substitutes a number.

This is ``MeterReading.reading``'s "bounded by a validator and never clamped" ruling
(``MeterReadings.py:39-43``) taken one step further: 4.13 rejected the clamp, 4.15 also rejects the
coercion.

**Corollary — why this is a separate table from ``MeterReading`` at all.** ``MeterReading.reading``
itself carries ``MinValueValidator(ZERO)`` (``MeterReadings.py:81-83``), so that table **structurally
cannot record a sub-zero temperature**. On top of that, ``MeterReading.asset`` is a non-nullable
CASCADE FK that cannot name a cold room or a shipment. Two tables, two subjects, two questions:
``MeterReading`` keeps the **asset-condition** series that feeds
``MaintenancePlan(trigger_type="condition")`` (run hours, discharge-air temperature); this keeps the
**product-environment** series.
--------------------------------------------------------------------------------------------------

**Documented CRUD exception — a decision, not an omission.** List, create, detail and import. **NO
edit view, NO delete view, no admin write** — exactly the ``StockMove`` (``StockMoves.py:1-9``) and
``MeterReading`` (``MeterReadings.py:28-37``) posture. A wrong reading is corrected by **posting a
later, correct one**; the mistaken row stays visible, which is the point of an append-only log
rather than a defect in it. It is also the only posture that survives an ALCOA+ review, where a
silently editable measurement IS the finding. ``admin.py`` registers this model read-only for the
same reason.

**Nothing derived is stored on a reading** — no ``is_excursion`` boolean, no ``mkt``, no
``in_range``. Each would be a second copy of a fact the monitor's limits already determine, and each
would go stale the moment a limit was edited.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.ColdChainManagement._choices import (
    MAX_HUMIDITY_PCT,
    MAX_LOGGING_INTERVAL_MINUTES,
    MAX_SAMPLE_COUNT,
    MAX_TEMPERATURE_C,
    MIN_HUMIDITY_PCT,
    MIN_LOGGING_INTERVAL_MINUTES,
    MIN_TEMPERATURE_C,
    READING_SOURCE_CHOICES,
)


class TemperatureReading(TenantOwned):
    """One interval summary from one monitor. Append-only: never edited, never deleted.

    ``TenantOwned``, not ``TenantNumbered``, and it carries **no ``NUMBER_PREFIX``** — the
    ``StockMove`` / ``MeterReading`` precedent (``MeterReadings.py:63-67``). A human-readable
    document number is for something a person refers to by name across a conversation; a reading is
    a data point in a series, identified by its monitor and its timestamp, and minting a per-tenant
    sequence for one would be a counter nobody ever quotes.
    """

    # THE LEDGER'S ONLY FK. The three-way subject polymorphism is resolved ONCE, on the low-volume
    # master (ColdChainMonitor); pushing it down here would widen the highest-volume table in the
    # sub-module by three columns and force every aggregate to COALESCE across them. CASCADE because
    # a reading is meaningless without the deployment that defines the limits it is judged against —
    # unlike the excursion, which is evidence and is therefore PROTECT.
    monitor = models.ForeignKey("scm.ColdChainMonitor", on_delete=models.CASCADE,
                                related_name="readings")

    # No default=timezone.now, deliberately. An interval summary always STATES its own window, and a
    # defaulted "now" would silently file an imported logger row under the import time — turning a
    # back-dated shipment log into a claim that the whole journey happened during the upload.
    reading_at = models.DateTimeField(help_text="End of the interval this row summarises")

    # SIGNED, NOT NULL, BOUNDED AND NEVER CLAMPED. Both halves of the trap in the module docstring
    # apply to this one field: no MinValueValidator(ZERO), and no q4().
    temperature = models.DecimalField(
        max_digits=6, decimal_places=2,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="Representative temperature for the interval, °C")
    # Relative humidity genuinely IS non-negative, unlike the temperatures around it. Recorded
    # because Emerson GO, Tive, ORBCOMM and ELPRO all treat it as co-equal with temperature;
    # humidity EXCURSIONS are out of scope this pass and nothing detects on this column.
    humidity_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(MIN_HUMIDITY_PCT), MaxValueValidator(MAX_HUMIDITY_PCT)],
        help_text="Relative humidity for the interval, %")

    # --- interval statistics ----------------------------------------------------------------------
    # Both optional because a SINGLE-SAMPLE interval has no extremes — and a manual reading typed by
    # a warehouse supervisor is exactly that. Signed and bounded like every temperature here.
    min_temperature = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="Coldest sample in the interval, °C")
    max_temperature = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(MIN_TEMPERATURE_C), MaxValueValidator(MAX_TEMPERATURE_C)],
        help_text="Warmest sample in the interval, °C")
    sample_count = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(MAX_SAMPLE_COUNT)],
        help_text="How many raw samples this row rolled up")

    # THE ROW'S OWN WEIGHT, and the reason MKT and time-out-of-range cannot be retroactively
    # re-weighted. SNAPSHOTTED from the monitor by the create / import verb and never a form field:
    # editing the monitor's logging interval next month must not restate last month's arithmetic.
    # Same rule as LaborActivity.standard_minutes_snapshot and CycleCountTaskLine.expected_quantity.
    interval_minutes = models.PositiveSmallIntegerField(
        default=30, editable=False,
        validators=[MinValueValidator(MIN_LOGGING_INTERVAL_MINUTES),
                    MaxValueValidator(MAX_LOGGING_INTERVAL_MINUTES)],
        help_text="Minutes this row weighs — snapshotted from the monitor when the row was filed")

    # --- provenance: stamped by the verb, never typed (L20/L22) ------------------------------------
    # The 4.13 MeterReading fix applied from the start. A member must not be able to forge a
    # system-filed reading by POSTing source=sensor_api&recorded_by=<pk> onto a record that ends up
    # in an audit pack — a provenance a user can choose is not a provenance.
    source = models.CharField(max_length=16, choices=READING_SOURCE_CHOICES, default="manual",
                              editable=False,
                              help_text="How the row reached the system — stamped by the verb")
    # SET_NULL because "the observation outlives the observer" (MeterReadings.py:70-74) — a
    # technician leaving must not delete the readings they took. `scm_temperature_readings` is
    # DISTINCT from 4.13's `scm_meter_readings`, which is already taken on core.Party.
    recorded_by = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="scm_temperature_readings")

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        # Newest first: every reader of this table wants the current value, and the trend panel walks
        # backwards from it. The tie-break on -id matters because a bulk import can land several rows
        # on one timestamp and ColdChainMonitor.latest_reading() must be deterministic.
        ordering = ["-reading_at", "-id"]
        # THE IDEMPOTENT-IMPORT GUARD: re-uploading the same logger file cannot double the series.
        # Deliberately TWO columns and not ("tenant", "monitor", "reading_at") — the monitor already
        # implies the tenant, and adding it would let one monitor hold two rows at one timestamp if
        # it were ever re-pointed between tenants.
        unique_together = ("monitor", "reading_at")
        indexes = [
            # The workhorse: every per-monitor chart, the profile aggregate, the detector's walk and
            # ColdChainMonitor.latest_reading() all filter monitor and order by reading_at.
            #
            # ONLY WHEN THE QUERY CARRIES A TENANT PREDICATE. ``tenant_id`` is the LEADING column, so
            # a caller reaching this table through the related manager alone (``monitor.readings…``)
            # states no tenant, cannot open this index, and falls back to the plain FK index on
            # ``monitor_id`` plus a filesort over the whole monitor's history. That is the measured
            # 4.13 finding (``MeterReadings.py:101-116``, ``Assets.py:616-625``), which is why every
            # reader here states a "redundant" ``tenant=`` that narrows nothing and buys the whole
            # index. EVERY READER OWES THAT LINE.
            models.Index(fields=["tenant", "monitor", "reading_at"], name="scm_tmp_tnt_mon_idx"),
            # The whole-workspace list and the date-range export cannot use the index above —
            # ``monitor`` is not a prefix of their filter.
            models.Index(fields=["tenant", "reading_at"], name="scm_tmp_tnt_read_idx"),
        ]

    def __str__(self):
        return f"{self.temperature} °C @ {self.reading_at:%Y-%m-%d %H:%M}"

    def clean(self):
        super().clean()

        # (1) THE GUARD. The create form's querysets are tenant-scoped, but that is UX — a narrowed
        #     dropdown has never held against a crafted POST (L39 §2). Without this, a reading could
        #     be hung off another workspace's monitor and would then drive that workspace's
        #     compliance figures. Skipped when the instance has no tenant yet: an unsaved model has
        #     tenant_id None and self.tenant would raise RelatedObjectDoesNotExist on a non-nullable
        #     FK. Defaulted getattr for the same reason as everywhere else in this app:
        #     RelatedObjectDoesNotExist subclasses AttributeError, so a pointer whose row went away
        #     degrades to None rather than 500-ing inside validation.
        if self.tenant_id is not None:
            for name in ("monitor", "recorded_by"):
                if getattr(self, f"{name}_id", None) is None:
                    continue
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another workspace."})

        # (2) No future readings — MeterReadings.py:145-148, verbatim reasoning. A future row sorts
        #     to the top of an append-only log and becomes "the current value" for a fridge that has
        #     not reached it yet, silently driving every chip, every profile and every excursion
        #     decision off a number nobody observed. Back-dating an observation is supported and
        #     expected (that is what a logger download IS); post-dating one is a claim about a
        #     measurement that has not happened.
        if self.reading_at and self.reading_at > timezone.now():
            raise ValidationError({
                "reading_at": "A reading cannot be dated in the future — file it once the interval "
                              "has actually elapsed."})

        # (3) The interval statistics have to bracket the representative value. Checked
        #     INDEPENDENTLY so a one-sided statistic stays legal: a logger that reports only a
        #     maximum is common, and refusing it would push the importer into inventing a minimum.
        if self.temperature is not None:
            if self.min_temperature is not None and self.min_temperature > self.temperature:
                raise ValidationError({
                    "min_temperature": "The interval minimum cannot be warmer than the reading."})
            if self.max_temperature is not None and self.max_temperature < self.temperature:
                raise ValidationError({
                    "max_temperature": "The interval maximum cannot be colder than the reading."})
        if (self.min_temperature is not None and self.max_temperature is not None
                and self.max_temperature < self.min_temperature):
            raise ValidationError({
                "max_temperature": "The interval maximum cannot be below the interval minimum."})

        # (4) A reading cannot predate the deployment. A re-usable logger has many deployments, one
        #     per shipment; a row from before this one started belongs to a DIFFERENT monitor's
        #     history, and filing it here would attribute another consignment's journey to this one.
        #     localtime() is only meaningful on an aware value; a naive one is read as-is rather than
        #     crashing validation.
        monitor = getattr(self, "monitor", None) if self.monitor_id is not None else None
        if monitor is not None and monitor.deployed_on and self.reading_at:
            stamped = (timezone.localtime(self.reading_at) if timezone.is_aware(self.reading_at)
                       else self.reading_at)
            if stamped.date() < monitor.deployed_on:
                raise ValidationError({
                    "reading_at": f"This monitor was deployed on {monitor.deployed_on} — a reading "
                                  f"from before then belongs to an earlier deployment."})
