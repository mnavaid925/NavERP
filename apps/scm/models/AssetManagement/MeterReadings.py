"""SCM 4.13 Asset Management — ``MeterReading``, the append-only meter log.

Every observation of an asset's meter is a row: the odometer at 41 200 km, the hour counter at 8 640
hours, the bearing temperature at 78 °C, the pressure gauge at 4.2 bar. Maximo's three meter kinds —
continuous runtime, gauge measurement, characteristic observation — all land in the same shape,
because what a scheduler and a trend line need from each is identical: a value, a unit, a timestamp
and who said so.

**A single mutable ``current_reading`` column on ``Asset`` was rejected, and this is the whole
design.** It fails three ways at once:

* **two writers.** A technician typing a reading on the asset page and the work-order complete verb
  capturing one at the moment of work would both own the same column, and the loser silently
  overwrites the winner. That is the exact drift 4.3's append-only ledger and 4.8's derived costs
  were built to avoid;
* **no history.** The column holds today's number and nothing else, so "how many hours did this
  machine run last month" and every usage trend on the asset page become unanswerable — not
  approximate, *impossible*, because the data was overwritten rather than never collected;
* **no meter-based maintenance.** A meter PM is due at *the reading plus an interval*, and a
  condition trigger fires when a reading *crosses* a threshold. Both need to compare the current
  observation against a target, and a condition trigger over a value with no history cannot tell a
  genuine crossing from a value that has been sitting there since installation.

So the reading lives here, once, as a fact with a timestamp, and ``Asset`` carries only the meter
*definition* (``meter_name`` / ``meter_unit``). Nothing can drift, because there is nothing to drift
*from*.

**Documented CRUD exception: list, create and detail — NO edit view and NO delete view.** Exactly the
``scm.StockMove`` posture (``InventoryManagement/StockMoves.py:1-9``): no form for editing, no admin
write, no delete route. A wrong reading is corrected by **posting a later, correct one**, the same
way a wrong stock movement is corrected by a compensating move and a wrong journal entry by a
reversal. ``Asset.latest_reading()`` reads the newest row, so the correction takes effect the moment
it is posted, and the mistaken row stays visible in the history — which is the point of an
append-only log rather than a defect in it. **The absent routes are a decision, not an omission:** an
editable meter reading is a number a scheduler already acted on, changed after the fact, with no
trace that it ever said anything else. ``admin.py`` registers this model read-only for the same
reason (the ``StockMoveAdmin`` posture).

**``reading`` is bounded by a validator and never clamped.** ``q4()`` clamps rather than raises,
which is right for a *computed* figure — one poisoned row degrades only itself. A meter reading is
not computed, it is an assertion about the world, and quietly clamping an odometer would corrupt
every meter-based due date derived from it while looking like a successful save. It is rejected on
the way in instead.

**``meter_name`` is free text and is not validated against ``Asset.meter_name``.** An asset commonly
has several meters (hours *and* temperature *and* pressure); the asset's own ``meter_name`` marks
only the PRIMARY one, which is what ``Asset.latest_reading()`` defaults to and what a meter-based
``MaintenancePlan`` schedules against. Secondary meters are recorded here and read by the trend
panel without needing a meter-definition table this sub-module does not have.

**The "what does this meter say now" query lives on ``Asset``, not here.** ``Asset.latest_reading()``
already owns it — including the rule that a named primary meter does NOT fall back to readings
logged under another name. A second copy on this model would be two canonical answers to one
question, drifting apart the first time either learned about a second meter.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.AssetManagement._choices import METER_SOURCE_CHOICES


class MeterReading(TenantOwned):
    """One observed meter value on one asset at one moment. Append-only: never edited, never deleted.

    ``TenantOwned``, not ``TenantNumbered``, and it carries **no ``NUMBER_PREFIX``** — the
    ``StockMove`` precedent. A human-readable document number is for something a person refers to by
    name across a conversation; a reading is a data point in a series, identified by its asset and
    its timestamp, and minting a per-tenant sequence for one would be a counter nobody ever quotes.
    """

    asset = models.ForeignKey("scm.Asset", on_delete=models.CASCADE, related_name="meter_readings")
    # The spine's Party, never a second employee table (L29). SET_NULL: a technician leaving must
    # not delete the readings they took — the observation outlives the observer.
    recorded_by = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_meter_readings")

    meter_name = models.CharField(
        max_length=40, help_text="Which meter — Hours, Odometer, Bearing Temp. See the module note")
    unit = models.CharField(max_length=16, blank=True, help_text="hrs, km, °C, bar, cycles")
    # Bounded, not clamped — see the module docstring for why this one field is the exception to the
    # q4() convention.
    reading = models.DecimalField(
        max_digits=14, decimal_places=4,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q4)])
    read_at = models.DateTimeField(
        default=timezone.now, help_text="When the meter was read — back-date an observation freely")
    # max_length 12 against a 10-char longest value ('work_order'). Deliberate slack: 4.10 sized a
    # choices column to its longest value and the first longer value added later was a column widen,
    # not the "one-line choices change" it looked like.
    source = models.CharField(max_length=12, choices=METER_SOURCE_CHOICES, default="manual")
    reference = models.CharField(
        max_length=40, blank=True,
        help_text="Source document number — the MWO- number when captured on a job")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        # Newest first: every reader of this table wants the current value, and the trend panel walks
        # backwards from it. The tie-break on -id matters because a bulk import can land several
        # readings on the same timestamp, and Asset.latest_reading() must be deterministic about
        # which one wins.
        ordering = ["-read_at", "-id"]
        indexes = [
            # The workhorse: Asset.latest_reading() and the per-asset trend both filter asset and
            # order by read_at, so the sort is served by the index rather than a filesort per asset.
            #
            # ONLY WHEN THE QUERY CARRIES A TENANT PREDICATE. ``tenant_id`` is the LEADING column,
            # so a query that reaches this table through the related manager alone
            # (``asset.meter_readings...``) states no tenant, cannot open this index, and falls back
            # to the plain FK index on ``asset_id`` plus a filesort. That is exactly what
            # ``Asset.latest_reading()`` used to do — measured, not theorised — which is why it and
            # the two panels that read this table now state a "redundant" ``tenant=`` that narrows
            # nothing and buys the whole index. A reader adding a third caller owes the same line.
            models.Index(fields=["tenant", "asset", "read_at"], name="scm_mtr_tnt_asset_idx"),
            # Whole-workspace views (the readings list, a date-range export) cannot use the index
            # above — asset is not a prefix of the filter.
            models.Index(fields=["tenant", "read_at"], name="scm_mtr_tnt_read_idx"),
        ]

    def __str__(self):
        unit = f" {self.unit}" if self.unit else ""
        return f"{self.meter_name} {self.reading}{unit}"

    def clean(self):
        super().clean()

        # THE GUARD. The create form's querysets are tenant-scoped, but that is UX — a narrowed
        # dropdown has never held against a crafted POST (L39 §2). Without this, a reading could be
        # hung off another workspace's asset and would then feed that workspace's meter-based due
        # dates. Skipped when the instance has no tenant yet: an unsaved model has tenant_id None
        # and self.tenant would raise RelatedObjectDoesNotExist on a non-nullable FK.
        if self.tenant_id is not None:
            for name in ("asset", "recorded_by"):
                if getattr(self, f"{name}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None instead of 500-ing inside validation.
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another workspace."})

        # A reading dated in the future would sort to the top of an append-only log and become "the
        # current value" for a machine that has not reached it yet — silently advancing every
        # meter-based due date and firing condition triggers off a number nobody observed. There is
        # no legitimate case: back-dating an observation is supported, post-dating one is a claim
        # about a measurement that has not happened (the ComplianceCheck.performed_on posture).
        if self.read_at and self.read_at > timezone.now():
            raise ValidationError(
                {"read_at": "A meter reading cannot be dated in the future — record it once the "
                            "meter has actually been read."})
