"""SCM 4.8 Manufacturing — BillOfMaterials + BOMLine, the recipe [BOM-].

Realizes the "Bill of Materials (BOM)" bullet and feeds Production Scheduling, Work Order Management
and MRP.

Two decisions worth reading before changing anything here:

**Make-vs-buy is DERIVED, not a flag.** An item is manufactured iff an active, effective BOM exists
for it — :meth:`BillOfMaterials.manufactured_item_ids` answers that for a whole tenant in ONE query.
There is deliberately no ``Item.is_manufactured`` column: a second source of truth would need a data
migration every time sourcing changes and would silently disagree with the recipes the moment one
was archived.

**``default_work_center`` is the documented stand-in for the deferred routing master.** A real
routing is an ordered set of operations, each with its own centre and standard times. Until that
lands, a BOM names one centre and ``ProductionTimeLog.operation`` is free text — the same
"free-text now, master later" call 4.1 made for purchase-order lines. Promoting it means adding a
``WorkOrderOperation`` child and moving these two fields onto it.

``status`` IS an ordinary form field here, unlike the status on WorkOrder. A BOM's draft→active→
obsolete progression is master-data curation, not a workflow that gates a stock posting, so it needs
no transition actions and no ``editable=False``.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class BillOfMaterials(TenantNumbered):
    """The recipe for one produced item — components, quantities and effectivity [BOM-]."""

    NUMBER_PREFIX = "BOM"

    #: Depth ceiling for a multi-level explosion. Paired with the visited-set guard below: the set
    #: stops a true cycle, the cap stops a legal-but-absurd nesting from running away.
    MAX_EXPLODE_DEPTH = 5
    #: Row ceiling for one explosion. Depth alone does NOT bound the output — the result is the
    #: PRODUCT of the branch factors, so five chained 50-line recipes emit 50^4 = 6.25M rows and
    #: OOM a worker shared by every tenant. Any logged-in member can author that, so this is a
    #: denial-of-service bound, not a tidiness one.
    MAX_EXPLODE_ROWS = 5000

    BOM_TYPE_CHOICES = [
        ("manufacture", "Manufacture"),   # produces a stocked good via a work order
        ("kit", "Kit"),                   # exploded at pick time, never stocked as an assembly
        ("phantom", "Phantom"),           # a grouping level that is blown through, never built
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("obsolete", "Obsolete"),
    ]

    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="boms",
                             help_text="The produced good this recipe makes")
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=20, default="1")
    bom_type = models.CharField(max_length=12, choices=BOM_TYPE_CHOICES, default="manufacture")
    output_quantity = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Quantity this recipe yields — component quantities scale by order qty / this")
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="boms")
    lead_time_days = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(3650)],
        help_text="In-house production time. NOT ReorderRule.lead_time_days, which is the "
                  "purchasing lead time for a bought item")
    default_work_center = models.ForeignKey(
        "scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True, related_name="boms",
        help_text="Stand-in for a routing until an operations master lands")

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_default = models.BooleanField(
        default=False, help_text="The recipe chosen when a work order names no BOM")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["item__sku", "version"]
        unique_together = (("tenant", "number"), ("tenant", "item", "version"))
        indexes = [
            models.Index(fields=["tenant", "item", "status"], name="scm_bom_tnt_item_status_idx"),
            models.Index(fields=["tenant", "status"], name="scm_bom_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name} v{self.version}"

    # --- validation ------------------------------------------------------------------------------
    def clean(self):
        super().clean()
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "Effective-to cannot precede effective-from."})
        # Direct self-reference is enforced by BaseBOMLineFormSet, which sees the submitted lines.
        # It is deliberately NOT re-checked here against the DATABASE: this clean() runs on the
        # header form, so a query-based check would fail validation before formset.save() could
        # remove the offending line — making an already-saved bad recipe permanently unrepairable
        # through the UI. Deeper cycles are caught at explode time by the visited set anyway (they
        # can be built from two individually-valid BOMs, so no single save can reject them).
        # MySQL has no partial/conditional UniqueConstraint, so "one default active BOM per item"
        # is enforced here plus a save-time demotion — not by a database constraint.
        if self.is_default and self.item_id and self.tenant_id:
            clash = BillOfMaterials.objects.filter(
                tenant_id=self.tenant_id, item_id=self.item_id, is_default=True)
            if self.pk:
                clash = clash.exclude(pk=self.pk)
            if clash.exists():
                raise ValidationError({
                    "is_default": f"{self.item} already has a default BOM ({clash.first().number}). "
                                  "Clear that one first."})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            result = super().save(*args, **kwargs)
            # Demote any sibling default. clean() already refuses the clash on a validated form;
            # this closes the same hole for the seeder, the admin and any programmatic writer.
            if self.is_default and self.item_id:
                BillOfMaterials.objects.filter(
                    tenant_id=self.tenant_id, item_id=self.item_id, is_default=True
                ).exclude(pk=self.pk).update(is_default=False)
        return result

    # --- effectivity -----------------------------------------------------------------------------
    def is_effective(self, on=None):
        """Active AND inside its effectivity window on ``on`` (default today)."""
        if self.status != "active":
            return False
        on = on or timezone.localdate()
        if self.effective_from and on < self.effective_from:
            return False
        if self.effective_to and on > self.effective_to:
            return False
        return True

    @classmethod
    def active_for(cls, tenant, item, on=None):
        """The BOM a work order should use for ``item`` — the default first, else the first active.

        Effectivity is filtered in Python rather than SQL because ``is_effective`` also encodes the
        null-means-open-ended rule on both bounds; the candidate set per item is tiny (versions of
        one recipe), so this costs one query either way.
        """
        if tenant is None or item is None:
            return None
        candidates = cls.objects.filter(tenant=tenant, item=item, status="active").order_by(
            "-is_default", "-version", "-id")
        for bom in candidates:
            if bom.is_effective(on):
                return bom
        return None

    @classmethod
    def manufactured_item_ids(cls, tenant, on=None):
        """``{item_id}`` for every item with an active, effective BOM — ONE query.

        The batched make-vs-buy test the MRP report needs. A per-row ``EXISTS`` here would be an
        N+1 across the whole item master (L18), which is the entire reason this is a classmethod
        returning a set rather than a property on Item.
        """
        if tenant is None:
            return set()
        on = on or timezone.localdate()
        rows = cls.objects.filter(tenant=tenant, status="active").filter(
            Q(effective_from__isnull=True) | Q(effective_from__lte=on)
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on))
        return set(rows.values_list("item_id", flat=True))

    @classmethod
    def is_manufactured(cls, tenant, item):
        """Single-row convenience wrapper — replaces an ``Item.is_manufactured`` flag entirely."""
        return cls.active_for(tenant, item) is not None

    @classmethod
    def explosion_index(cls, tenant_id, on=None):
        """``{item_id: BillOfMaterials}`` for every active, effective BOM — lines prefetched, TWO queries.

        The batched form of :meth:`active_for`, and the only sane way to explode more than one item.
        ``explode()`` otherwise asks ``active_for`` whether each component has its own recipe, which
        is a query per line per level; run inside MRP's loop over every demanded item that reached
        ~2,300 queries for one page on a realistic tenant.

        Selection is deliberately identical to ``active_for``: same ordering, first effective BOM per
        item wins — so the batched and single-row paths can never disagree about which recipe is
        current.
        """
        if tenant_id is None:
            return {}
        on = on or timezone.localdate()
        boms = (cls.objects.filter(tenant_id=tenant_id, status="active")
                .select_related("tenant", "item", "uom")
                .prefetch_related(models.Prefetch(
                    "lines", queryset=BOMLine.objects.select_related(
                        "component", "component__uom", "uom")))
                .order_by("item_id", "-is_default", "-version", "-id"))
        index = {}
        for bom in boms:
            if bom.item_id not in index and bom.is_effective(on):
                index[bom.item_id] = bom
        return index

    def _explode_lines(self):
        """This BOM's lines, reusing the prefetch when it came from :meth:`explosion_index`."""
        if "lines" in getattr(self, "_prefetched_objects_cache", {}):
            return self._prefetched_objects_cache["lines"]
        return self.lines.select_related("component", "component__uom", "uom").all()

    # --- explosion -------------------------------------------------------------------------------
    @property
    def component_count(self):
        return self.lines.count()

    def explode(self, quantity, depth_cap=None, index=None, _visited=None, _level=1,
                _budget=None):
        """Flatten this recipe into the raw components needed to build ``quantity``.

        Returns ``[{"item", "quantity", "level", "source_bom"}]``. A component that has its own
        active BOM recurses; anything else is a leaf. Each line contributes
        ``quantity × quantity_per × (1 + scrap_pct/100) / output_quantity``.

        Cycle safety mirrors ``Location.path()``: a visited set of item ids on the current branch
        stops A→B→A outright, and ``depth_cap`` bounds a legal but pathological nesting. A component
        that would revisit an ancestor is emitted as a LEAF rather than dropped — silently losing a
        requirement would understate the shortage, which is the more dangerous failure.
        """
        depth_cap = self.MAX_EXPLODE_DEPTH if depth_cap is None else depth_cap
        # Build the index once at the top of the recursion (and reuse a caller-supplied one, which
        # is how MRP shares a single index across every item it explodes). `tenant_id`, never
        # `self.tenant` — the latter is a FK deref that costs a query per recursion level.
        if index is None:
            index = self.explosion_index(self.tenant_id)
        visited = set(_visited or ())
        visited.add(self.item_id)
        quantity = Decimal(quantity or ZERO)
        output = self.output_quantity or Decimal("1")
        # A one-element list so every frame of the recursion shares one counter.
        budget = [self.MAX_EXPLODE_ROWS] if _budget is None else _budget
        rows = []
        for line in self._explode_lines():
            if budget[0] <= 0:
                break
            required = q4(quantity * line.effective_quantity_per / output)
            child = None
            if _level < depth_cap and line.component_id not in visited:
                child = index.get(line.component_id)
            if child is None:
                budget[0] -= 1
                rows.append({"item": line.component, "quantity": required, "level": _level,
                             "source_bom": self, "issue_method": line.issue_method,
                             "uom": line.uom or line.component.uom})
            else:
                rows.extend(child.explode(required, depth_cap=depth_cap, index=index,
                                          _visited=visited, _level=_level + 1, _budget=budget))
        return rows

    def explode_was_truncated(self, rows):
        """True when ``rows`` hit :attr:`MAX_EXPLODE_ROWS` — the page must say so rather than
        quietly present a short list as complete."""
        return len(rows) >= self.MAX_EXPLODE_ROWS

    def estimated_unit_cost(self, rows=None):
        """Standard cost of one output unit, rolled up from the exploded leaves.

        Uses each component's ``standard_cost`` and falls back to its ledger-derived
        ``average_cost`` — an estimating figure for the BOM page, NOT the cost a work order posts.
        The posted cost is always what the StockMoves actually carried.

        Pass ``rows`` when the caller has already exploded at ``output_quantity`` — the detail page
        does, and re-exploding there doubled the whole cost of rendering it.
        """
        output = self.output_quantity or Decimal("1")
        total = ZERO
        for row in (self.explode(output) if rows is None else rows):
            item = row["item"]
            unit = item.standard_cost or item.average_cost or ZERO
            total += row["quantity"] * unit
        return q4(total / output)


class BOMLine(models.Model):
    """One component of a recipe. Tenant-less — reached only through its parent BOM."""

    ISSUE_METHOD_CHOICES = [
        ("manual", "Manual"),        # issued explicitly by the shop floor
        ("backflush", "Backflush"),  # consumed automatically when output is reported
    ]

    bom = models.ForeignKey("scm.BillOfMaterials", on_delete=models.CASCADE, related_name="lines")
    sequence = models.PositiveIntegerField(default=10)
    component = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="bom_lines")
    quantity_per = models.DecimalField(max_digits=14, decimal_places=4,
                                       validators=[MinValueValidator(Decimal("0.0001"))],
                                       help_text="Per the BOM's output quantity, before scrap")
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="+")
    scrap_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))],
        help_text="Expected component loss — inflates the quantity a work order requires")
    issue_method = models.CharField(max_length=10, choices=ISSUE_METHOD_CHOICES, default="manual")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.component} × {self.quantity_per}"

    @property
    def effective_quantity_per(self):
        """``quantity_per`` grossed up for expected scrap."""
        return q4((self.quantity_per or ZERO) * (Decimal("1") + (self.scrap_pct or ZERO) / Decimal("100")))
