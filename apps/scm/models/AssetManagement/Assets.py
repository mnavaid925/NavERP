"""SCM 4.13 Asset Management — ``Asset`` [AST-] + ``AssetSparePart``, the operational asset spine.

**Why this table is here and not in Module 11.** Module 11 (Asset Management System) is the eventual
home of full EAM, but 11.x is unbuilt, a maintenance work order needs something to point at today,
and grep confirms no ``Asset`` row exists anywhere in the project — ``core.Asset``, ``scm.Asset`` and
``scm.Equipment`` are all absent. So this is the first and only one: ``scm.Asset`` is the operational
asset spine, exactly as 4.3 owns ``Item`` / ``Location`` / ``StockMove`` for every module that moves
stock. Module 11 extends it by string FK (11.2 tracking, 11.7 condition monitoring, 11.19 fleet)
instead of re-declaring it. A throwaway 4.13 table that Module 11 later duplicates is the
second-parallel-schema bug L29 exists to forbid.

**``status`` has exactly one writer, and it is the user.** No work-order verb touches it: raising,
starting, completing or closing a job leaves ``status`` alone. "Is this machine down right now" is a
DERIVED chip — an open job with ``downtime_start`` set and ``downtime_end`` still null — so the
question is answered from the rows that know the answer rather than from a column something else has
to remember to flip. The alternative (a verb that flips the asset to ``under_maintenance`` and back)
needs a rule for every path out of a job — cancelled, put on hold, superseded by a second job on the
same asset — and the first path anyone forgets leaves an asset permanently reading "under
maintenance" while it is happily running. One writer per column, no drift.

**No ``current_reading`` column.** The asset declares its meter (``meter_name`` / ``meter_unit``) and
nothing else; the numbers live in ``MeterReading``, append-only, in exactly the spirit of
``StockMove``. A single mutable "current reading" would have two writers the moment a technician can
type one on a work order as well as on the meter page, and it cannot answer meter-based PM due dates,
usage trends or condition triggers at all — those need the history, not the last value.

**``fixed_asset`` is a pointer, and nothing more.** ``accounting.FixedAsset`` already owns
acquisition cost, salvage value, useful life, method and accumulated depreciation, and it is the
thing that posts the depreciation journal. 4.13 stores none of those figures, builds no second
depreciation ledger and posts no ``JournalEntry`` (the standing 4.9-4.12 rule). The link exists so
the asset page can show a book value and the TCO report can show a repair-vs-replace ratio — both by
READING the accounting row. Two writers of one accumulated figure is precisely how the two numbers on
the two pages come to disagree.

**Every reliability figure is derived, and an honest one can answer ``None``.** MTBF, MTTR and
availability all divide by something that can legitimately be zero — an asset with no recorded
failures, or one whose observation window cannot be established. They return ``None`` there, never
``0``: an MTBF of 0 h reads as "this thing fails constantly", which is the exact opposite of the
truth, and the 4.11 lesson is that a confident number in a tile is worse than a blank, because the
blank makes someone go and look.
"""
from apps.scm.models._base import *  # noqa: F401,F403

from apps.scm.models.AssetManagement._choices import (
    CRITICALITY_CHOICES,
    CRITICALITY_CSS,
)


class Asset(TenantNumbered):
    """A maintainable thing — machine, vehicle, rack, facility — and its place in the plant [AST-]."""

    NUMBER_PREFIX = "AST"

    # `it_equipment` is the longest value at 12; the column is 14 for headroom. The 4.10 lesson: a
    # 15-char value dropped into a max_length=14 column is a column WIDEN, not "a one-line change to
    # choices", and it lands on a table that by then has rows in it.
    ASSET_TYPE_CHOICES = [
        ("machine", "Machine"),
        ("vehicle", "Vehicle"),
        ("forklift", "Forklift"),
        ("conveyor", "Conveyor"),
        ("rack", "Rack / Storage Equipment"),
        ("tool", "Tool"),
        ("facility", "Facility"),
        ("it_equipment", "IT Equipment"),
        ("other", "Other"),
    ]

    # Deliberately a DIFFERENT vocabulary from accounting.FixedAsset.status (cip / active / disposed).
    # The operational states belong here and the financial ones belong there; an asset can be
    # `standby` operationally while being perfectly `active` financially, and neither column writes
    # the other. Merging them would force one page to lie.
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_service", "In Service"),
        ("under_maintenance", "Under Maintenance"),
        ("standby", "Standby"),
        ("idle", "Idle"),
        ("retired", "Retired"),
        ("disposed", "Disposed"),
    ]

    #: Colour per status, decided in ONE place (the ``KpiSnapshot.BAND_CSS`` / ``TradeLicense``
    #: precedent) so the list page and the detail page cannot disagree. theme.css has
    #: badge-green / red / amber / info / muted / slate ONLY — badge-success and friends render
    #: completely unstyled (L33).
    STATUS_CSS = {
        "planned": "badge-info",
        "in_service": "badge-green",
        "under_maintenance": "badge-amber",
        "standby": "badge-slate",
        "idle": "badge-muted",
        "retired": "badge-muted",
        "disposed": "badge-red",
    }

    #: Work-order statuses that mean the job is finished with. Stated as the TERMINAL set rather than
    #: the open set on purpose: a status added to ``MaintenanceWorkOrder`` later is far more likely to
    #: be a mid-lifecycle state (``awaiting_parts``, ``awaiting_approval``) than a new ending, so
    #: excluding the terminal three makes an unknown status count as OPEN. That errs towards showing
    #: a job on the asset page, which is the safe direction to be wrong in.
    CLOSED_JOB_STATUSES = ("completed", "closed", "cancelled")

    #: What counts as a failure. One definition, read by :meth:`failure_count`, :meth:`mtbf_hours`
    #: and :meth:`mttr_hours`, so the three cannot end up counting different rows and producing a
    #: set of numbers that do not reconcile with each other. ``corrective`` is deliberately NOT here:
    #: planned corrective work (a scheduled bearing change) is repair, not breakdown, and counting it
    #: would depress MTBF for doing maintenance properly.
    FAILURE_WORK_TYPES = ("breakdown",)

    #: Hard cap on the parent walk in :meth:`clean`. It bounds both the recursion AND the query count
    #: (each hop is one SELECT), so a hierarchy that is already looped — built before this guard
    #: existed, or by a fixture — cannot hang the request that is trying to repair it.
    MAX_HIERARCHY_DEPTH = 20

    #: How far ahead a warranty starts reading as "expiring" — the 4.12 licence-notice idiom, fixed
    #: rather than per-row because a warranty has no renewal workflow to configure it from.
    WARRANTY_NOTICE_DAYS = 60

    #: The FKs :meth:`clean` tenant-checks. Table-driven so adding a pointer means adding it here,
    #: not remembering to copy an eighth if-block.
    TENANT_SCOPED_FKS = ("parent", "location", "work_center", "org_unit", "custodian", "supplier",
                         "service_vendor", "fixed_asset")

    # --- identity ----------------------------------------------------------------------------------
    code = models.CharField(max_length=32, help_text="Short plant code, unique in this workspace")
    name = models.CharField(max_length=255)
    asset_type = models.CharField(max_length=14, choices=ASSET_TYPE_CHOICES, default="machine")
    status = models.CharField(max_length=18, choices=STATUS_CHOICES, default="in_service",
                              help_text="The operational lifecycle state — you set it; no work order "
                                        "changes it")
    # 10, not 8: `critical` is exactly 8 and a column sized to its longest current value has no room
    # for the next one. Same headroom rule as `asset_type` and `work_type` above — a widen on a table
    # with rows in it is a migration, not a choices edit.
    criticality = models.CharField(max_length=10, choices=CRITICALITY_CHOICES, default="medium",
                                   help_text="How much it hurts when this asset stops")
    # Plain text, deliberately NOT a FK to scm.ItemCategory: an asset family ("Compressors", "Fork
    # trucks") is not an item taxonomy, and overloading the item categories with it would make the
    # item category list unusable for the module that owns it. CharField(120) also MATCHES
    # accounting.FixedAsset.category, which is what lets the depreciation report read consistently
    # across the two tables.
    category = models.CharField(max_length=120, blank=True)

    manufacturer = models.CharField(max_length=120, blank=True)
    model_number = models.CharField(max_length=64, blank=True)
    serial_number = models.CharField(max_length=64, blank=True)
    # The QR/barcode VALUE — printable today; camera scanning is a front-end job for later. Uniqueness
    # is enforced in clean(), NOT by unique_together: a blank here is "" and not NULL on MariaDB, so a
    # (tenant, tag_code) constraint would let exactly one asset in the workspace go untagged.
    tag_code = models.CharField(max_length=64, blank=True,
                                help_text="QR / barcode value. Must be unique in this workspace")

    # Capacity, voltage, rated output — free text on purpose. A real user-defined-field engine is
    # 11.3's "Custom Attributes"; inventing half of one as a 4.13 table would be a schema everyone
    # then has to migrate off.
    specifications = models.TextField(blank=True, help_text="Capacity, voltage, rated output, ratings")

    # --- where it is, who looks after it -----------------------------------------------------------
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="children",
                               help_text="The assembly this is a component of")
    location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="assets", help_text="Where the asset physically sits")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_assets", help_text="Owning department")
    # THE SCM DIFFERENTIATOR. Taking a machine down is not a maintenance fact, it is a capacity fact:
    # 4.8's load board and OEE both read the centre, so the link that lets a repair explain a
    # capacity hole has to exist. SET_NULL, not CASCADE — retiring a work centre must not delete the
    # asset, which is the record with the cost history hanging off it.
    work_center = models.ForeignKey("scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="assets",
                                    help_text="Production work centre this asset serves")
    # The spine's Party plus its roles — never a second employee or vendor table (L29).
    custodian = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="scm_custodian_assets",
                                  help_text="Person or team accountable for the asset")
    supplier = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_supplied_assets", help_text="Who we bought it from")
    service_vendor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="scm_serviced_assets",
                                       help_text="Default contractor for outsourced work")

    # --- commercial --------------------------------------------------------------------------------
    purchase_date = models.DateField(null=True, blank=True)
    commissioned_on = models.DateField(null=True, blank=True,
                                       help_text="When it entered service — the reliability clock "
                                                 "starts here")
    warranty_expires_on = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q2)])
    # The depreciation link and nothing more — see the module docstring. SET_NULL because the asset
    # keeps running after the finance team disposes of its book entry.
    fixed_asset = models.ForeignKey("accounting.FixedAsset", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="scm_assets",
                                    help_text="The capitalised record that depreciates this asset")

    # --- the meter DEFINITION (the readings live in MeterReading) -----------------------------------
    meter_name = models.CharField(max_length=40, blank=True,
                                  help_text="Primary meter, e.g. Running Hours, Odometer, Cycles")
    meter_unit = models.CharField(max_length=16, blank=True, help_text="h, km, cycles, L")

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = (("tenant", "code"), ("tenant", "number"))
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_ast_tnt_status_idx"),
            # The maintenance queue orders critical assets first; the PM board filters on it.
            models.Index(fields=["tenant", "criticality"], name="scm_ast_tnt_crit_idx"),
            models.Index(fields=["tenant", "location"], name="scm_ast_tnt_loc_idx"),
            # The warranty chip and the expiring-warranty report both order/filter on this.
            models.Index(fields=["tenant", "warranty_expires_on"], name="scm_ast_tnt_wty_idx"),
            models.Index(fields=["tenant", "is_active"], name="scm_ast_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.code} · {self.name}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """Cross-tenant FK guard, the tag uniqueness rule, and the hierarchy guard.

        The form's dropdowns are already tenant-scoped, but that is UX — a narrowed ``<select>`` has
        never held against a crafted POST (L39 §2), and this model is reachable by any logged-in
        member of any workspace.
        """
        super().clean()

        # Skipped when the instance has no tenant yet: an unsaved model has tenant_id None, and
        # ``self.tenant`` on a non-nullable FK raises RelatedObjectDoesNotExist rather than returning
        # None. Most of these are None on a real save and cost nothing.
        if self.tenant_id is not None:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row has gone away degrades to None here instead of 500-ing inside
                # validation.
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another workspace."})

        self._validate_tag_code()
        self._validate_hierarchy()

    def _validate_tag_code(self):
        """One barcode, one asset — enforced here because a DB constraint cannot express "when set".

        MariaDB stores a blank CharField as ``""``, not NULL, so ``unique_together`` on
        ``(tenant, tag_code)`` would allow exactly ONE untagged asset per workspace and reject the
        second with an IntegrityError 500. A scan that resolved to two assets would be worse than
        useless, so the rule still has to exist — it just has to exist in Python.
        """
        if not self.tag_code or self.tenant_id is None:
            return
        clash = Asset.objects.filter(tenant_id=self.tenant_id, tag_code=self.tag_code)
        if self.pk:
            clash = clash.exclude(pk=self.pk)
        other = clash.first()
        if other is not None:
            raise ValidationError({
                "tag_code": f"Tag {self.tag_code} is already on {other.code} ({other.name})."})

    def _validate_hierarchy(self):
        """Reject a self-parent, and reject any cycle — walking upward under a hard depth cap.

        Three separate failures, not one. Self-parenting is the obvious typo. A cycle two or three
        hops long (A under B under A) is what actually happens when someone reorganises a plant, and
        it is invisible on the form that creates it. Both would make :meth:`path`-style ancestry
        walks, the tree page and every roll-up loop forever.

        The cap is the third guard and the important one: it bounds the walk even when the DATA is
        already broken. Without it, repairing a pre-existing loop would be impossible — the edit form
        that fixes it would hang on validation before it could save. Twenty levels is far past any
        real plant hierarchy, so hitting the cap is itself a refusal.
        """
        if self.parent_id is None:
            return
        if self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "An asset cannot be its own parent."})

        seen = {self.pk} if self.pk else set()
        node = self.parent
        for _ in range(self.MAX_HIERARCHY_DEPTH):
            if node is None:
                return
            if node.pk in seen:
                raise ValidationError({
                    "parent": f"{node.code} is already below this asset — that would make a loop "
                              "in the hierarchy."})
            seen.add(node.pk)
            node = node.parent
        raise ValidationError({
            "parent": f"The asset hierarchy is more than {self.MAX_HIERARCHY_DEPTH} levels deep "
                      "above this row. Flatten it before setting a parent here."})

    # ---------------------------------------------------------------------------------------------
    # Work-order history. Everything below reads the reverse relations by related_name
    # (``work_orders`` / ``meter_readings`` / ``maintenance_plans``) rather than importing the
    # sibling modules: apps/scm/models/__init__.py imports THIS module first (the FKs all point at
    # scm.Asset), so a module-level import here would invert the dependency edge. The one place that
    # genuinely needs a class object takes a local import, the TradeLicense.recompute_usage /
    # WorkCenter.scheduled_hours_map precedent.
    # ---------------------------------------------------------------------------------------------
    def open_jobs(self):
        """Maintenance work orders still on somebody's list. See :attr:`CLOSED_JOB_STATUSES`."""
        return self.work_orders.exclude(status__in=self.CLOSED_JOB_STATUSES)

    def open_job_count(self):
        """How many jobs are outstanding — the queue badge on the asset row."""
        return self.open_jobs().count()

    def is_down_now(self):
        """Is there an OPEN downtime window on this asset right now?

        Defined as an open job with ``downtime_start`` set and ``downtime_end`` still null — the
        derived answer the module docstring promises instead of a stored flag.

        Deliberately not restricted to ``work_type="breakdown"``: what makes an asset down is an open
        downtime window, not the label on the job. A preventive service that took the line down is a
        line that is down, and a page that said otherwise would be wrong in the direction that gets
        someone sent to a machine that is in pieces.
        """
        return self.open_jobs().filter(
            downtime_start__isnull=False, downtime_end__isnull=True).exists()

    def _jobs(self):
        """Work orders that actually happened — cancelled ones excluded.

        A cancelled job may still carry a downtime window and a labour figure typed before it was
        called off; counting those would charge the asset for work nobody did.
        """
        return self.work_orders.exclude(status="cancelled")

    def downtime_minutes(self, since=None):
        """Total minutes this asset has been down, INCLUDING any window still running.

        Two queries, and the second one is the point. ``MaintenanceWorkOrder.downtime_minutes`` is
        derived in ``save()`` from the start/end pair, so a window that is still open contributes
        ZERO to the stored column — a machine that has been down for three days would report no
        downtime at all while :meth:`is_down_now` said it was down. The running windows are therefore
        added here as ``now - downtime_start``. There are never many of them (one per open job).

        ``since`` filters on ``downtime_start``, so a window is attributed in full to the period it
        BEGAN in. No proration across a period boundary: splitting a window between two months is a
        reporting engine's job (4.11), and doing half of it here would produce a figure that does not
        add up to the total on any other page.
        """
        rows = self._jobs()
        if since is not None:
            rows = rows.filter(downtime_start__gte=since)
        total = rows.aggregate(m=Sum("downtime_minutes"))["m"] or 0

        now = timezone.now()
        for start in rows.filter(downtime_start__isnull=False, downtime_end__isnull=True
                                 ).values_list("downtime_start", flat=True):
            if start < now:
                total += int((now - start).total_seconds() // 60)
        return total

    def failure_count(self, since=None):
        """Breakdowns recorded against this asset — the denominator of MTBF and MTTR.

        Windowed on ``reported_at`` (when the fault was raised), not on ``completed_at``: a failure
        happened when it happened, and hanging it off the repair date would move failures between
        periods every time a job stayed open over a month end.
        """
        rows = self._jobs().filter(work_type__in=self.FAILURE_WORK_TYPES)
        if since is not None:
            rows = rows.filter(reported_at__gte=since)
        return rows.count()

    def _observed_hours(self, since=None):
        """Hours in the reliability observation window, or ``None`` when it cannot be established.

        The window always ends now and starts at, in order of preference: the caller's ``since``, the
        commissioning date, or the day the record was created. It is deliberately NOT "the first work
        order", which would give an asset with no jobs a zero-length window and therefore 100%
        availability by construction — the flattering number this whole model is arranged to avoid.

        ``None`` rather than ``0`` when there is nothing to measure, so every caller has to decide
        what to print rather than dividing by a zero it did not expect.
        """
        now = timezone.now()
        if since is not None:
            hours = Decimal((now - since).total_seconds()) / Decimal("3600")
        elif self.commissioned_on:
            # localdate(), not date.today(): the project is TZ-aware and the server's date is not
            # necessarily the workspace's. Whole days is as precise as a commissioning date ever is.
            hours = Decimal((timezone.localdate() - self.commissioned_on).days) * Decimal("24")
        elif self.created_at:
            hours = Decimal((now - self.created_at).total_seconds()) / Decimal("3600")
        else:
            return None
        return hours if hours > ZERO else None

    def mtbf_hours(self, since=None):
        """Mean time between failures, in hours — ``(observed hours - downtime hours) / failures``.

        Uptime over failures, not elapsed time over failures: an asset that spent half the window in
        pieces did not spend that half operating, and dividing by elapsed time would flatter it for
        being broken.

        Returns ``None`` — never ``0`` — when there are no failures, or when the observation window
        cannot be established. An MTBF of 0 h reads as "fails constantly", the exact opposite of an
        asset that has never failed, and it is the number that would sit in a red tile on a
        reliability page and start a conversation about a machine that is fine.
        """
        failures = self.failure_count(since=since)
        if not failures:
            return None
        observed = self._observed_hours(since)
        if observed is None:
            return None
        downtime = Decimal(self.downtime_minutes(since=since)) / Decimal("60")
        uptime = max(observed - downtime, ZERO)
        return q2(uptime / Decimal(failures))

    def mttr_hours(self, since=None):
        """Mean time to repair, in hours — repair downtime over FINISHED breakdowns.

        Only completed and closed breakdowns count. A repair still in progress has no repair time
        yet; including it would divide a partial numerator by a full denominator and pull the average
        down every time something is currently broken — the moment the figure is most looked at.

        Counts only breakdowns whose downtime window was actually RECORDED AND CLOSED. A finished
        repair that nobody timed carries ``downtime_minutes = 0`` (it is derived in ``save()`` from
        the start/end pair, and an unset pair derives to zero), so leaving it in would add nothing to
        the numerator and one to the denominator — every untimed repair silently dragging the mean
        toward zero and making the fleet look faster to fix the worse the record-keeping got. It is
        excluded from BOTH halves instead, so the figure means "mean over the repairs we timed"
        rather than "mean over the repairs we know about". A genuine same-instant repair still
        counts: the window was recorded, it was simply short.

        ``None``, not ``0``, when no breakdown has been finished: the honest answer is "not enough
        history", and a 0 h MTTR reads as instant repairs.
        """
        rows = self._jobs().filter(work_type__in=self.FAILURE_WORK_TYPES,
                                   status__in=("completed", "closed"),
                                   downtime_start__isnull=False, downtime_end__isnull=False)
        if since is not None:
            rows = rows.filter(reported_at__gte=since)
        agg = rows.aggregate(m=Sum("downtime_minutes"), n=models.Count("id"))
        repairs = agg["n"] or 0
        if not repairs:
            return None
        return q2(Decimal(agg["m"] or 0) / Decimal("60") / Decimal(repairs))

    def availability_pct(self, since=None):
        """Share of the observation window the asset was NOT down, as a percentage.

        ``(observed - downtime) / observed × 100``. Not floored at anything except zero: when the
        recorded downtime exceeds the window — overlapping windows, or downtime logged against a
        machine commissioned last week — the answer is 0%, which is visibly wrong and sends someone
        to look at the data. Silently clamping it to something plausible would not.

        ``None`` when there is no window to measure against, for the reason :meth:`_observed_hours`
        gives.
        """
        observed = self._observed_hours(since)
        if observed is None:
            return None
        downtime = Decimal(self.downtime_minutes(since=since)) / Decimal("60")
        uptime = max(observed - downtime, ZERO)
        return q2(uptime / observed * Decimal("100"))

    def maintenance_cost_to_date(self, since=None):
        """Everything this asset has cost to keep running: issued parts + labour + contractors.

        TWO aggregates over TWO grains, never one. Asking for the parts total in the same
        ``aggregate()`` as the labour and contractor totals joins the child rows in, which FANS THE
        JOB ROWS OUT and multiplies every ``labour_cost`` and ``external_cost`` by that job's part
        count — a three-part repair would be charged three times its labour, silently, forever. This
        is the same trap ``TradeLicense.recompute_usage`` documents; the fix is one query per grain.

        Only ISSUED parts count. ``unit_cost`` is stamped from the item's average cost at issue time,
        so a part that is merely reserved still carries 0.00 — counting it would add a real line at a
        fake price, and the job has not consumed any stock yet either.
        """
        jobs = self._jobs()
        if since is not None:
            jobs = jobs.filter(reported_at__gte=since)

        header = jobs.aggregate(
            labour=Sum(F("labour_hours") * F("labour_rate"),
                       output_field=models.DecimalField(max_digits=20, decimal_places=4)),
            external=Sum("external_cost"))

        # Local import for the reason given above the section: this module is imported before its
        # siblings, so the symbol cannot be pulled in at module level.
        from apps.scm.models import MaintenanceWorkOrderPart
        parts = MaintenanceWorkOrderPart.objects.filter(
            work_order__in=jobs, is_issued=True).aggregate(
                v=Sum(F("quantity") * F("unit_cost"),
                      output_field=models.DecimalField(max_digits=20, decimal_places=4)))["v"]

        # q2 rather than a bare sum: it clamps an over-range total to what the column shape holds, so
        # one poisoned rate can only degrade this asset's figure instead of raising inside a report
        # that is rendering a hundred rows.
        return q2((header["labour"] or ZERO) + (header["external"] or ZERO) + (parts or ZERO))

    # ---------------------------------------------------------------------------------------------
    # Maintenance plans and meters
    # ---------------------------------------------------------------------------------------------
    def next_pm_due(self):
        """The earliest date any ACTIVE plan on this asset falls due, or ``None``.

        ``values_list(...).first()`` rather than fetching the plan: the callers (the list column, the
        detail header) want the date, and pulling a whole row per asset across a page is the
        difference between one small query and a hundred.
        """
        return (self.maintenance_plans
                .filter(is_active=True, next_due_on__isnull=False)
                .order_by("next_due_on")
                .values_list("next_due_on", flat=True)
                .first())

    def latest_reading(self, meter_name=None):
        """The most recent ``MeterReading`` row for one meter, or ``None``.

        Defaults to the asset's PRIMARY meter and, when that is set, does NOT fall back to readings
        logged under another name. Different meters measure different things: an odometer reading of
        300 000 handed to a plan whose interval is in running hours would schedule a service roughly
        never, and the failure would be silent. A missing reading is recoverable; a reading from the
        wrong meter is not.

        Ordering is stated explicitly rather than inherited from ``MeterReading.Meta`` — a reader of
        this method should not have to open another file to know which row comes back.
        """
        rows = self.meter_readings.all()
        name = meter_name if meter_name is not None else self.meter_name
        if name:
            rows = rows.filter(meter_name=name)
        return rows.order_by("-read_at", "-id").first()

    # ---------------------------------------------------------------------------------------------
    # Chips — derived, never stored (the 4.12 licence-expiry precedent)
    # ---------------------------------------------------------------------------------------------
    def days_to_warranty_expiry(self, today=None):
        """Days until the warranty lapses (negative once past), or ``None`` if none is recorded."""
        if not self.warranty_expires_on:
            return None
        return (self.warranty_expires_on - (today or timezone.localdate())).days

    def warranty_chip(self, today=None):
        """``(label, css)`` for the warranty state — templates read ``.0`` and ``.1``.

        A derived pair rather than a stored ``warranty_status`` column, for the same reason 4.12
        refused one on licences: the fact changes by the calendar rolling over, and a stored flag
        would need something to run every night to stay true. Nothing runs every night here, so it
        would quietly go stale and a lapsed warranty would keep reading green — the one outcome that
        actually costs money, because it is the state in which someone pays for a repair the supplier
        owed them.

        "Not recorded" is its own muted state and never green: not knowing whether an asset is under
        warranty is not the same as knowing it is.
        """
        days = self.days_to_warranty_expiry(today)
        if days is None:
            return ("Not recorded", "badge-muted")
        if days < 0:
            return ("Expired", "badge-red")
        if days == 0:
            return ("Expires today", "badge-amber")
        if days <= self.WARRANTY_NOTICE_DAYS:
            return (f"{days} days left", "badge-amber")
        return ("In warranty", "badge-green")

    @property
    def status_css(self):
        """theme.css badge class for :attr:`status` — one lookup, so no template invents a colour."""
        return self.STATUS_CSS.get(self.status, "badge-muted")

    @property
    def criticality_css(self):
        """theme.css badge class for :attr:`criticality`, from the shared vocabulary's own map."""
        return CRITICALITY_CSS.get(self.criticality, "badge-muted")


class AssetSparePart(models.Model):
    """An item this asset consumes when it is serviced — the machine's parts list.

    **Tenant-less on purpose**, reached through ``asset__tenant`` (the ``ComplianceCheck`` /
    ``TradeDocumentLine`` precedent). A child that carried its own tenant column could disagree with
    its parent's, and then two rows of the same asset would belong to two workspaces. Every view over
    this table therefore scopes on ``asset__tenant``, never on the child alone.

    **There is no ``SparePart`` table.** ``scm.Item`` already carries UoM, category, costing method,
    average cost, reorder point and a derived on-hand across every location; a parallel parts master
    would duplicate all of it and then need reconciling with the stock ledger the maintenance issue
    posts into. This row is the ASSOCIATION — which item, how much per service, and whether running
    out stops the job — and nothing else.
    """

    asset = models.ForeignKey("scm.Asset", on_delete=models.CASCADE, related_name="spare_parts")
    # PROTECT, unlike the asset side's CASCADE: deleting an item that a machine's parts list depends
    # on must not silently make that list wrong. The delete view guards the resulting ProtectedError
    # with a message rather than leaving it as a 500.
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="asset_spare_parts")
    quantity_per_service = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal("1"),
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q4)],
        help_text="How many are consumed in one service")
    is_critical = models.BooleanField(
        default=False, help_text="Running out of this one stops the job")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("asset", "item")
        ordering = ["item__sku"]
        indexes = [models.Index(fields=["asset"], name="scm_asp_asset_idx")]

    def __str__(self):
        return f"{self.item} × {self.quantity_per_service}"

    def clean(self):
        """The item must belong to the ASSET's workspace.

        Checked through the parent because this row has no tenant of its own, and checked at all
        because ``asset`` is taken from the URL and never from POST — which leaves ``item`` as the
        one field a crafted request could point at another workspace's row. The form's queryset is
        already scoped, but a narrowed dropdown is UX, not a guard (L39 §2).
        """
        super().clean()
        if self.asset_id is None or self.item_id is None:
            return
        asset = getattr(self, "asset", None)
        item = getattr(self, "item", None)
        if asset is not None and item is not None and item.tenant_id != asset.tenant_id:
            raise ValidationError({"item": "That item belongs to another workspace."})

    def save(self, *args, **kwargs):
        """Normalise the quantity through :func:`q4` — 4dp, and clamped to what the column holds.

        Clamping matters more than quantizing here: an over-range figure raises ``DataError`` inside
        a formset save, which fails the whole parts list rather than the one bad line.
        """
        self.quantity_per_service = q4(self.quantity_per_service)
        return super().save(*args, **kwargs)
