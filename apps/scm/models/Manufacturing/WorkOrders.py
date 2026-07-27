"""SCM 4.8 Manufacturing — WorkOrder + WorkOrderComponent, the production run [WO-].

Realizes "Work Order Management" entirely and the scheduling half of "Production Scheduling"; it is
the object MRP and Shop Floor Control both point at.

**Components are a SNAPSHOT.** ``explode_components()`` copies the exploded BOM onto
``WorkOrderComponent`` rows once, and everything afterwards reads the rows — never the recipe. A BOM
edited next month cannot rewrite what a run three weeks ago actually required.

**Costs are DERIVED from the ledger, not from the snapshot.** ``material_cost`` sums the
``consumption`` StockMoves that carry this order's number; labour and machine cost come from the
ProductionTimeLog entries. ``wip_value`` is computed on the detail page and stored nowhere — there
is no WIP location, no WIP quantity column and no WIP GL account. SCM does not post journal entries
(L29): the ledger effect of a production run is entirely the StockMove rows it writes, which
accounting reads through the valuation report. If a GL hand-off is ever wanted it follows the 4.6
freight pattern — a DRAFT accounting document, never a posted JournalEntry from here.

**Two stock move types, and they are not interchangeable.** Components leave as ``consumption`` and
output arrives as ``production``. Reusing ``issue`` for consumption would corrupt demand planning:
4.7's ``demand_series`` filters ``move_type="issue"`` and reads it as CUSTOMER demand, so every raw
material drawn to the shop floor would inflate the forecasts built on the stock-issues source.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class WorkOrder(TenantNumbered):
    """One production run — what to build, from which recipe, when and where [WO-]."""

    NUMBER_PREFIX = "WO"

    ORDER_POLICY_CHOICES = [
        ("make_to_stock", "Make to Stock"),
        ("make_to_order", "Make to Order"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]
    SCHEDULE_DIRECTION_CHOICES = [
        ("forward", "Forward — from the start date"),
        ("backward", "Backward — from the due date"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("planned", "Planned"),
        ("released", "Released"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    #: Statuses whose header/components the planner may still edit.
    EDITABLE_STATUSES = ("draft", "planned")
    #: Statuses where the run is live — time logs may be booked, stock may move.
    OPEN_STATUSES = ("released", "in_progress")

    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="work_orders")
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="work_orders")
    bom = models.ForeignKey("scm.BillOfMaterials", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="work_orders",
                            help_text="Recipe exploded onto the component lines — the lines, not "
                                      "this link, are what the run consumes")
    quantity_planned = models.DecimalField(max_digits=14, decimal_places=4,
                                           validators=[MinValueValidator(Decimal("0.0001"))])
    order_policy = models.CharField(max_length=14, choices=ORDER_POLICY_CHOICES,
                                    default="make_to_stock")
    sales_order = models.ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="work_orders",
                                    help_text="Make-to-order peg — the demand this run covers")
    work_center = models.ForeignKey("scm.WorkCenter", on_delete=models.PROTECT, null=True,
                                    blank=True, related_name="work_orders")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="normal")

    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    schedule_direction = models.CharField(max_length=8, choices=SCHEDULE_DIRECTION_CHOICES,
                                          default="forward")
    due_date = models.DateField(null=True, blank=True)

    component_location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, null=True,
                                           blank=True, related_name="wo_component_sources",
                                           help_text="Where components are drawn from")
    output_location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, null=True,
                                        blank=True, related_name="wo_output_targets",
                                        help_text="Where finished goods are received")
    output_lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True,
                                          blank=True, related_name="work_orders")

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft",
                              editable=False)
    actual_start = models.DateTimeField(null=True, blank=True, editable=False)
    actual_end = models.DateTimeField(null=True, blank=True, editable=False)
    # Written ONLY by the report-production action. Nothing else — not the form, not the admin, not
    # ProductionTimeLog.quantity_completed, which is advisory shop-floor progress.
    quantity_produced = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            editable=False)
    quantity_scrapped = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            editable=False)
    produced_unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                             editable=False)
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False, related_name="+")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_wo_tnt_status_idx"),
            models.Index(fields=["tenant", "work_center", "planned_start"],
                         name="scm_wo_tnt_wc_start_idx"),
            models.Index(fields=["tenant", "item"], name="scm_wo_tnt_item_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.item} × {self.quantity_planned}"

    def clean(self):
        super().clean()
        if self.planned_start and self.planned_end and self.planned_end < self.planned_start:
            raise ValidationError({"planned_end": "Planned end cannot precede planned start."})
        if self.order_policy == "make_to_order" and self.sales_order_id is None:
            raise ValidationError({"sales_order": "A make-to-order run must name the sales order "
                                                  "it is pegged to."})
        # The recipe must actually make the thing being built. The create form offers every active
        # BOM in the tenant (the item isn't known until the form binds), so without this a
        # mis-picked recipe explodes the wrong components onto a run that then consumes real stock.
        if self.bom_id and self.item_id and self.bom.item_id != self.item_id:
            raise ValidationError({"bom": f"{self.bom.number} produces {self.bom.item}, not "
                                          f"{self.item} — pick a BOM for the item being built."})

    # --- state -----------------------------------------------------------------------------------
    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def quantity_remaining(self):
        return q4(max((self.quantity_planned or ZERO)
                      - (self.quantity_produced or ZERO) - (self.quantity_scrapped or ZERO), ZERO))

    # --- costs (all derived; nothing here is stored) ----------------------------------------------
    def _move_totals(self):
        """``(consumed_value, produced_value)`` from the moves carrying this order's number.

        The ledger is authoritative — not the component snapshot, which records what was *planned*
        to be consumed. One grouped query.
        """
        from apps.scm.models import StockMove
        rows = (StockMove.objects
                .filter(tenant_id=self.tenant_id, reference=self.number,
                        move_type__in=("consumption", "production"))
                .values("move_type")
                .annotate(v=Sum(F("quantity") * F("unit_cost"),
                                output_field=models.DecimalField(max_digits=20, decimal_places=4))))
        totals = {row["move_type"]: (row["v"] or ZERO) for row in rows}
        # Consumption is signed negative in the append-only ledger — negate to read as cost.
        return -(totals.get("consumption") or ZERO), (totals.get("production") or ZERO)

    @property
    def material_cost(self):
        return q4(self._move_totals()[0])

    def _time_costs(self):
        """``(labor_cost, machine_cost)`` over this order's time logs — one pass, rates per centre.

        ``downtime`` is EXCLUDED: idle time is a loss metric, not a cost the good units absorb.
        """
        labor = ZERO
        machine = ZERO
        for log in self.time_logs.select_related("work_center").all():
            if log.entry_type == "downtime":
                continue
            hours = log.duration_hours
            centre = log.work_center
            if log.entry_type == "machine":
                machine += hours * (centre.machine_cost_per_hour or ZERO)
            else:  # setup + labor both cost at the labour rate
                labor += hours * (centre.labor_cost_per_hour or ZERO)
        return q4(labor), q4(machine)

    @property
    def labor_cost(self):
        return self._time_costs()[0]

    @property
    def machine_cost(self):
        return self._time_costs()[1]

    @property
    def wip_value(self):
        """Cost put in, less the value already taken out as finished goods.

        A COMPUTED figure for the detail page. There is no WIP location and no WIP account — see the
        module docstring.
        """
        consumed, produced = self._move_totals()
        labor, machine = self._time_costs()
        # ``consumed`` is already returned sign-flipped to a positive cost — see _move_totals.
        return q4(consumed + labor + machine - produced)

    def computed_unit_cost(self, good_quantity):
        """Cost of one good unit in the layer being posted RIGHT NOW.

        Divides the **unabsorbed** pool — cost put in, less the value earlier production layers
        already took out — by *this* layer's good quantity. Three choices worth knowing:

        1. ``setup`` and ``labor`` logs cost at the centre's labour rate, ``machine`` at its machine
           rate; ``downtime`` is excluded entirely.
        2. The pool divides by the GOOD quantity, so scrapped units' cost is absorbed by the units
           that survived — standard practice, and the reason a scrappy run reports a higher unit
           cost rather than hiding the loss.
        3. It is the UNABSORBED pool, not the whole pool over cumulative output. Dividing the whole
           pool by the cumulative good quantity re-charges cost an earlier layer already carried:
           on a 3-then-2 split of a run costing C that posts ``3 × C/3 = C`` then ``2 × C/5 = 0.4C``
           — banking 1.4C of stock value against C of real cost, and driving ``wip_value`` negative,
           which is the proof the two disagreed. The ledger is append-only, so an over-valued layer
           can never be corrected in place; it has to be right when it is posted.

        A sub-quantum residual can still remain in ``wip_value``: a 4dp unit cost multiplied by a
        quantity cannot represent every pool exactly. That is rounding, bounded by one quantum per
        unit posted — not the systematic overage described in (3).
        """
        good_quantity = Decimal(good_quantity or ZERO)
        if good_quantity <= ZERO:
            return ZERO
        consumed, produced = self._move_totals()
        labor, machine = self._time_costs()
        unabsorbed = consumed + labor + machine - produced
        if unabsorbed <= ZERO:
            return ZERO
        return q4(unabsorbed / good_quantity)

    # --- hours -----------------------------------------------------------------------------------
    @property
    def planned_hours(self):
        if not self.planned_start or not self.planned_end:
            return ZERO
        return q2(Decimal((self.planned_end - self.planned_start).total_seconds()) / Decimal("3600"))

    @property
    def actual_hours(self):
        minutes = self.time_logs.aggregate(m=Sum("duration_minutes"))["m"] or 0
        return q2(Decimal(minutes) / Decimal("60"))

    @property
    def duration_variance_hours(self):
        return q2(self.actual_hours - self.planned_hours)

    # --- components --------------------------------------------------------------------------------
    def explode_components(self):
        """Snapshot the BOM onto WorkOrderComponent rows. Returns the number written.

        Only when the order has NO components yet — a hand-edited component set is never silently
        overwritten by a re-explode. Callers wanting a rebuild delete the rows first, deliberately.
        """
        if self.bom_id is None or self.components.exists():
            return 0
        rows = self.bom.explode(self.quantity_planned)
        WorkOrderComponent.objects.bulk_create([
            WorkOrderComponent(
                work_order=self, sequence=(index + 1) * 10, item=row["item"],
                quantity_required=row["quantity"], uom=row.get("uom"),
                issue_method=row.get("issue_method") or "manual",
                unit_cost=row["item"].standard_cost or row["item"].average_cost or ZERO,
            )
            for index, row in enumerate(rows)
        ])
        return len(rows)

    def material_shortfalls(self, components=None):
        """``[{component, required, available, short}]`` for components the source location can't cover.

        ONE grouped aggregate keyed by ``(item_id, lot_serial_id)`` — the ``stocktransfer_detail``
        precedent. An aggregate per line here would be an N+1 on the module's fastest-growing table.

        Pass ``components`` when the caller already has them (the detail page does) to skip the
        duplicate fetch.
        """
        from apps.scm.models import StockMove
        if components is None:
            components = list(self.components.select_related("item", "lot_serial").all())
        if not components or self.component_location_id is None:
            return []
        rows = (StockMove.objects
                .filter(tenant_id=self.tenant_id, location_id=self.component_location_id,
                        item_id__in={c.item_id for c in components})
                .values("item_id", "lot_serial_id")
                .annotate(q=Sum("quantity")))
        on_hand = {(row["item_id"], row["lot_serial_id"]): (row["q"] or ZERO) for row in rows}
        item_totals = {}
        for (item_id, _lot_id), qty in on_hand.items():
            item_totals[item_id] = item_totals.get(item_id, ZERO) + qty
        shortfalls = []
        for component in components:
            outstanding = component.quantity_outstanding
            if outstanding <= ZERO:
                continue
            if component.lot_serial_id is not None:
                available = on_hand.get((component.item_id, component.lot_serial_id), ZERO)
            else:
                available = item_totals.get(component.item_id, ZERO)
            if outstanding > available:
                shortfalls.append({"component": component, "required": outstanding,
                                   "available": available, "short": q4(outstanding - available)})
        return shortfalls


class WorkOrderComponent(models.Model):
    """One material line of a run — snapshotted from the BOM. Tenant-less child."""

    ISSUE_METHOD_CHOICES = [
        ("manual", "Manual"),
        ("backflush", "Backflush"),
    ]

    work_order = models.ForeignKey("scm.WorkOrder", on_delete=models.CASCADE,
                                   related_name="components")
    sequence = models.PositiveIntegerField(default=10)
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT,
                             related_name="work_order_components")
    quantity_required = models.DecimalField(max_digits=14, decimal_places=4,
                                            validators=[MinValueValidator(ZERO)],
                                            help_text="From the BOM explosion, inclusive of scrap")
    # Maintained by the issue action alone — never a form field, never the admin.
    quantity_issued = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                          editable=False)
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="+")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="work_order_components")
    issue_method = models.CharField(max_length=10, choices=ISSUE_METHOD_CHOICES, default="manual")
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                    validators=[MinValueValidator(ZERO)],
                                    help_text="Cost snapshot taken when the line was issued")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.item} × {self.quantity_required}"

    @property
    def quantity_outstanding(self):
        return q4(max((self.quantity_required or ZERO) - (self.quantity_issued or ZERO), ZERO))

    @property
    def issued_value(self):
        return q4((self.quantity_issued or ZERO) * (self.unit_cost or ZERO))
