"""Procurement 6.18 Inventory & Warehouse Integration — ReplenishmentRun [RPL-] + suggestions.

**The gap this closes.** ``scm:reorder_alerts`` and ``inventory:reorderdraft`` both
compute-and-forget: they render a shortfall list and throw it away. **Nothing in the repo
persists a proposal.** A buyer therefore cannot say "we looked at this on Tuesday and decided not
to order", cannot snooze a line, and cannot show anybody what the numbers were at the moment the
decision was taken. A :class:`ReplenishmentRun` is that missing record — the batch proposal
Oracle's min-max report, Odoo's replenishment dashboard, NetSuite's AIM and D365's master planning
all produce.

**What it is NOT.** It is not a second reorder rule and not a second stock ledger (L36). Every
planning number it uses is READ from ``scm.ReorderRule`` and every quantity is READ from the
``StockMove`` ledger; the only figures this model owns are the ones it *snapshots*, and they are
snapshots precisely so the record still explains itself after the stock has moved on (the
``CycleCountTaskLine.expected_quantity`` precedent,
``apps/inventory/models/StocktakingCycleCounting/CycleCountTasks.py:97-98``).

**Two verbs, and the boundary between them is the point.**

* :meth:`ReplenishmentRun.generate` proposes. It writes nothing outside this sub-module.
* :meth:`ReplenishmentRun.release` commits — and it commits into ``scm.PurchaseRequisition`` **in
  ``draft``**, never into a purchase order and never auto-approved. That is deliberate and it is
  NavERP.md's literal wording ("generation of **requisitions**"): a draft requisition still runs
  6.3's approval routing, 6.15's budget check and 6.10's PO conversion. Releasing straight to a PO
  — the ``inventory:reorderdraft`` shape — would route a machine's opinion around every control
  the workspace has.

**Performance is a correctness property here, not a nicety.** A run walks every active reorder
rule in the workspace. :meth:`generate` therefore issues **nine grouped read queries and then does
pure Python** — there is no database access of any kind inside the per-rule loop. A per-rule
``resolve()`` or a per-rule ``Sum()`` would be an N+1 over the entire warehouse, which is exactly
what ``ReorderRule.on_hand_map`` and :meth:`ReplenishmentPolicy.resolve_map` exist to prevent.

**The on-order figure is TWO queries, never one.** Annotating a PO line's ``quantity`` alongside
its child ``receipt_lines__quantity_received`` joins every receipt row onto its line, and that
fan-out multiplies ``ordered`` by the receipt count — an order of 10 received as 4+6 reports 10
outstanding instead of 0. The shape is mirrored from
``apps/inventory/views/InventoryTrackingControl/StockLevels.py:37-67`` and deliberately
**re-implemented locally**: peer apps do not import each other's view internals.

**Two honest imprecisions, stated rather than hidden.**

1. *On-order and open-requisition quantities are per-SKU, not per-location.* 4.1's PO lines and
   requisition lines predate the item spine (L28) — they carry a free-text ``sku_hint`` and no
   location at all. So a SKU stocked at three locations nets the SAME network-wide incoming
   quantity off each one, and the run under-proposes. A run scoped to a single location (the
   normal case) is exact. The pages say so; :attr:`ReplenishmentSuggestion.on_order_qty` is
   snapshotted so a reader can see what was netted off.
2. *The trigger tests on-hand plus incoming supply, not availability.* That is ``ReorderRule
   .is_below_point()``'s own definition (``ReorderRules.py:133``), and a run that disagreed with
   the SCM alert about whether an item is below its point would be worse than one that is merely
   conservative. :attr:`~ReplenishmentSuggestion.allocated_qty` and
   :attr:`~ReplenishmentSuggestion.available_qty` are still snapshotted, using the ONE availability
   formula (``StockLevels.py:124``: ``on_hand − claims − non-sellable``), so a buyer can see that a
   nominally healthy item is in fact entirely spoken for.

**Import discipline.** Every cross-app FK is a STRING and every cross-app model class is imported
INSIDE the method that needs it, mirroring the rest of this app. ``ReplenishmentPolicy`` is a
sibling ENTITY MODULE of this same sub-module and is imported from its module path, never from
``apps.procurement.models`` — the package re-export does not exist until the Integrator lands it.
"""
from datetime import timedelta
from decimal import Decimal as _Decimal

from apps.core.utils import write_audit_log
from apps.procurement.models._base import *  # noqa: F401,F403
from apps.procurement.models.InventoryWarehouseIntegration.Policies import ReplenishmentPolicy

#: Snapshot columns are 4dp; every figure that lands on one goes through this.
_Q4 = _Decimal("0.0001")


def _q4(value):
    """Quantize to the 4dp shape every snapshot column on a suggestion holds."""
    return (value if isinstance(value, Decimal) else Decimal(str(value or 0))).quantize(_Q4)


def _pair_map(queryset, item_key="item_id", location_key="location_id"):
    """``{(item_id, location_id): Σ quantity}`` for one claim/classification source.

    Callers project the pair as ALIASES where the natural field names collide with the model's own
    columns — the spine allocation reaches its item through the order LINE, so it aliases both
    halves (``StockLevels.py:93-97``).
    """
    return {(row[item_key], row[location_key]): (row["s"] or ZERO) for row in queryset}


def _on_order_map(tenant):
    """``{sku: outstanding}`` across every RECEIVABLE purchase order, keyed by ``sku_hint``.

    **TWO grouped queries merged in Python, deliberately not one** — see the module docstring for
    the fan-out that makes a single annotation wrong.

    4.1's PO lines carry a free-text ``sku_hint`` rather than an item FK (L28), so the match is
    EXACT-STRING against ``Item.sku``: a fuzzy or case-insensitive guess would attach somebody
    else's open order to the wrong SKU. Outstanding = ordered − accepted receipts (cancelled GRNs
    excluded), floored at zero so an over-receipt cannot read as negative demand.

    Mirrored from ``StockLevels.py:37-67`` rather than imported: peer apps do not reach into each
    other's view internals (the ``resolve_line_item`` precedent,
    ``apps/procurement/models/ReceiptInspection/ReceiptTolerances.py:398-405``).
    """
    from apps.scm.models import GoodsReceiptLine, PurchaseOrder, PurchaseOrderLine

    ordered_rows = (PurchaseOrderLine.objects
                    .filter(purchase_order__tenant=tenant,
                            purchase_order__status__in=PurchaseOrder.RECEIVABLE_STATUSES)
                    .exclude(sku_hint="")
                    .values("sku_hint")
                    .annotate(ordered=Sum("quantity")))
    # Received is scoped to the SAME receivable POs, so both halves of the subtraction cover
    # exactly the same order population.
    received_rows = (GoodsReceiptLine.objects
                     .filter(po_line__purchase_order__tenant=tenant,
                             po_line__purchase_order__status__in=PurchaseOrder.RECEIVABLE_STATUSES)
                     .exclude(goods_receipt__status="cancelled")
                     .values(sku=F("po_line__sku_hint"))
                     .annotate(received=Sum("quantity_received")))
    ordered = {row["sku_hint"]: (row["ordered"] or ZERO) for row in ordered_rows}
    received = {row["sku"]: (row["received"] or ZERO) for row in received_rows}
    return {sku: max(qty - received.get(sku, ZERO), ZERO) for sku, qty in ordered.items()}


def _open_requisition_map(tenant):
    """``{sku: quantity}`` already sitting on requisitions that count as supply. ONE query.

    "Counts as supply" is 6.15's definition, imported rather than restated:
    ``REQUESTED_PR_STATUSES + COMMITTED_PR_STATUSES`` — pending-approval and approved. ``draft``
    is excluded, and that is load-bearing in both directions: a half-keyed requisition nobody has
    submitted is not supply, **and** the draft requisitions :meth:`ReplenishmentRun.release`
    itself raises therefore do not suppress the next run until somebody actually submits them.
    ``converted`` is excluded too — its quantity has become a purchase order and is already
    counted by :func:`_on_order_map`, so counting both would net the same incoming stock twice.

    Same free-text ``sku_hint`` match as the on-order map, and the same per-SKU (not per-location)
    imprecision.
    """
    from apps.procurement.models.BudgetCostManagement.BudgetMappings import (
        COMMITTED_PR_STATUSES, REQUESTED_PR_STATUSES)
    from apps.scm.models import PurchaseRequisitionLine

    rows = (PurchaseRequisitionLine.objects
            .filter(requisition__tenant=tenant,
                    requisition__status__in=tuple(REQUESTED_PR_STATUSES) + tuple(COMMITTED_PR_STATUSES))
            .exclude(sku_hint="")
            .values("sku_hint")
            .annotate(q=Sum("quantity")))
    return {row["sku_hint"]: (row["q"] or ZERO) for row in rows}


class ReplenishmentRun(TenantNumbered):
    """One batch replenishment proposal: what was short, by how much, and what was decided."""

    NUMBER_PREFIX = "RPL"

    TRIGGER_CHOICES = [
        ("manual", "Manual"),
        ("scheduled", "Scheduled"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("proposed", "Proposed"),
        ("released", "Released"),
        ("cancelled", "Cancelled"),
    ]
    #: UPPERCASE, because this filters ``scm.ReorderRule.abc_class`` — see the field's help_text.
    ABC_CHOICES = [("A", "A"), ("B", "B"), ("C", "C")]

    EDITABLE_STATUSES = ("draft",)
    RELEASABLE_STATUSES = ("proposed",)
    CANCELLABLE_STATUSES = ("draft", "proposed")
    #: A run may re-propose from either of these — re-generating a proposed run replaces its lines.
    GENERATABLE_STATUSES = ("draft", "proposed")

    #: Hard cap on one run. An unbounded batch is not a feature: a workspace with 40,000 rules
    #: would render a page nobody can read and hold a row lock while it did. When the cap bites,
    #: the run keeps the HIGHEST-VALUE shortfalls and stamps :attr:`TRUNCATION_PREFIX` on the
    #: notes, so the omission is on the record rather than silent.
    MAX_SUGGESTIONS = 500
    TRUNCATION_PREFIX = "[Truncated:"

    #: theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
    #: badge-slate (L33) — a semantic badge-success renders unstyled.
    STATUS_CSS = {"draft": "badge-muted", "proposed": "badge-amber",
                  "released": "badge-green", "cancelled": "badge-slate"}
    TRIGGER_CSS = {"manual": "badge-slate", "scheduled": "badge-info"}

    location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_replenishment_runs",
        help_text="Location to plan for. Blank = the whole network, which is also the only scope "
                  "where the network-wide on-order figure is a rough netting rather than exact.")
    run_date = models.DateField(
        help_text="The date this proposal is for. Requisition due dates are counted forward from "
                  "it using each line's lead time.")
    trigger = models.CharField(
        max_length=12, choices=TRIGGER_CHOICES, default="manual",
        help_text="How this run was started. 'Scheduled' records that a timetable asked for it — "
                  "the column ships, the cron does not, exactly as CountProgram.is_due() does.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    abc_class_filter = models.CharField(
        max_length=1, choices=ABC_CHOICES, blank=True,
        help_text="Plan only this ABC class. GOTCHA: this filters scm.ReorderRule.abc_class, "
                  "which is the UPPERCASE revenue rank A/B/C — NOT scm.Location.abc_class, which "
                  "is the lowercase bin-velocity attribute a/b/c. They are different things.")
    notes = models.TextField(blank=True)

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="procurement_replenishment_runs",
        help_text="Who last generated the proposal (system-stamped)")
    generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    released_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-run_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_rpl_tnt_status_idx"),
            models.Index(fields=["tenant", "run_date"], name="prc_rpl_tnt_date_idx"),
        ]
        verbose_name = "Replenishment Run"
        verbose_name_plural = "Replenishment Runs"

    def __str__(self):
        return f"{self.number or 'RPL-?'} · {self.scope_label}"

    # ------------------------------------------------------------------ display helpers
    @property
    def scope_label(self):
        """What this run planned for, as one readable phrase."""
        return self.location.code if self.location_id else "Whole network"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-muted")

    @property
    def trigger_css(self):
        return self.TRIGGER_CSS.get(self.trigger, "badge-muted")

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def can_generate(self):
        return self.status in self.GENERATABLE_STATUSES

    @property
    def can_release(self):
        return self.status in self.RELEASABLE_STATUSES

    @property
    def can_cancel(self):
        return self.status in self.CANCELLABLE_STATUSES

    @property
    def is_truncated(self):
        """True when :meth:`generate` hit :attr:`MAX_SUGGESTIONS` and said so on the notes."""
        return self.TRUNCATION_PREFIX in (self.notes or "")

    # ------------------------------------------------------------------ derived figures
    # Each costs ONE query and is meant for a single object (the detail page computes its whole
    # totals strip in one conditional aggregate instead, and the register annotates). They are
    # deliberately NOT stored: a cached count that drifts from its rows is worse than a query.
    @property
    def line_count(self):
        return self.lines.count()

    @property
    def accepted_count(self):
        return self.lines.filter(decision="accepted").count()

    @property
    def total_value(self):
        """Σ suggested_qty × unit_cost over every line, in ONE aggregate."""
        return self.lines.aggregate(v=Sum(F("suggested_qty") * F("unit_cost")))["v"] or ZERO

    # ------------------------------------------------------------------ the proposal
    def generate(self, user=None):
        """Re-propose this run's suggestion lines. **Nine grouped queries, then pure Python.**

        Idempotent by construction: the run's existing lines are deleted first, so pressing
        Generate twice leaves one set of lines rather than two. ``select_for_update()`` on the
        header serialises concurrent presses — the second waits for the first to finish and then
        replaces its work, instead of both bulk-inserting into the same run.

        The nine reads, in order, and NONE of them is inside the per-rule loop:

        ===  ==========================================================================
        Q1   the active reorder rules in scope (location + ABC filters applied in SQL)
        Q2   on-hand, via ``ReorderRule.on_hand_map`` — one grouped StockMove aggregate
        Q3   sales-order allocations (4.5), active statuses only
        Q4   inventory reservations (5.6), active statuses only
        Q5   non-sellable stock classifications (5.6)
        Q6   ordered quantity on receivable purchase orders
        Q7   accepted receipt quantity against those same orders
        Q8   quantity on requisitions that already count as supply
        Q9   the replenishment policies, via ``ReplenishmentPolicy.resolve_map``
        ===  ==========================================================================

        Q6 and Q7 are two queries on purpose (module docstring). Q9 is one query for the whole
        batch: a per-rule ``ReplenishmentPolicy.resolve()`` would be the N+1 this module exists to
        avoid.

        **An item with no policy still gets a suggestion.** ``resolve_map`` answers ``None`` for an
        unconfigured pair, and the shortfall is then shaped by an unsaved default
        :class:`ReplenishmentPolicy` — all defaults, no rounding, no vendor. Skipping unconfigured
        items would silently hide exactly the ones nobody has thought about yet. The suggestion's
        ``policy`` FK stays null, which is what makes "no policy" visible on the page.

        Only policies whose ``source_method`` is in
        :attr:`ReplenishmentPolicy.REQUISITIONABLE_SOURCE_METHODS` are proposed for: a transfer is
        SCM's stock-transfer document and a manufacture is 4.8's work order, and quietly buying
        either would be wrong. That tuple is READ, never hard-coded to ``"buy"`` here.

        Returns the number of suggestion lines written.
        """
        # The override-versus-fallback rule (policy.target_level else rule.reorder_point +
        # safety_stock; policy.lead_time_days_override tested `is not None` so a stored 0 is a real
        # override) is ReplenishmentPolicy.effective_numbers() — ONE written-down definition, on
        # the model, read below through `shaping`. It used to live in the detail VIEW, which made
        # this method import upward into apps.procurement.views at call time; every import in this
        # sub-module now runs downward.
        from apps.inventory.models import InventoryReservation, StockStatus
        from apps.scm.models import ReorderRule, SalesOrderAllocation

        with transaction.atomic():
            # select_related("tenant") so the nine grouped queries below stay nine: every one of
            # them is handed ``locked.tenant``, and a lazy fetch of it would be a tenth.
            locked = type(self).objects.select_for_update().select_related("tenant").get(pk=self.pk)
            if locked.status not in self.GENERATABLE_STATUSES:
                raise ValidationError(
                    f"{locked.number} is {locked.get_status_display().lower()} and can no longer "
                    f"be generated — released and cancelled runs are a record of what was decided.")
            self.status = locked.status
            tenant_id = locked.tenant_id

            # --- Q1: the rules in scope ------------------------------------------------------
            rules = (ReorderRule.objects
                     .filter(tenant_id=tenant_id, is_active=True)
                     .select_related("item", "item__uom", "location"))
            if self.location_id:
                rules = rules.filter(location_id=self.location_id)
            if self.abc_class_filter:
                rules = rules.filter(abc_class=self.abc_class_filter)
            rules = list(rules)

            # Wipe first so a re-generate replaces rather than appends. Done even when there are
            # no rules left in scope: a run that used to propose ten lines and now legitimately
            # proposes none must show none.
            self.lines.all().delete()

            if not rules:
                return self._finish_generation(user, [], truncated=False)

            # --- Q2-Q9: every figure the loop needs, one grouped query per source -------------
            on_hand = ReorderRule.on_hand_map(locked.tenant, rules)                       # Q2
            allocations = _pair_map(                                                     # Q3
                SalesOrderAllocation.objects
                .filter(status__in=SalesOrderAllocation.ACTIVE_STATUSES,
                        sales_order_line__sales_order__tenant_id=tenant_id)
                # The item sits on the ORDER LINE and both field names collide with the model's
                # own columns, so both halves of the pair key are aliased.
                .values(iid=F("sales_order_line__item_id"), loc=F("location_id"))
                .annotate(s=Sum("quantity")),
                item_key="iid", location_key="loc")
            reservations = _pair_map(                                                    # Q4
                InventoryReservation.objects
                .filter(tenant_id=tenant_id, status__in=InventoryReservation.ACTIVE_STATUSES)
                .values("item_id", "location_id").annotate(s=Sum("quantity")))
            unsellable = _pair_map(                                                      # Q5
                StockStatus.objects.filter(tenant_id=tenant_id).exclude(status="active")
                .values("item_id", "location_id").annotate(s=Sum("quantity")))
            on_order = _on_order_map(locked.tenant)                                      # Q6+Q7
            open_requisitions = _open_requisition_map(locked.tenant)                     # Q8
            policies = ReplenishmentPolicy.resolve_map(                                  # Q9
                locked.tenant, [(r.item_id, r.location_id) for r in rules])

            # --- pure Python from here: NOT ONE query inside this loop ------------------------
            # One unsaved instance, reused for every unconfigured pair. It carries the model's own
            # defaults (net off on-order and open requisitions, source "buy", no rounding, no
            # vendor) and its round_quantity() is the same single implementation every other line
            # goes through — so "no policy" cannot accidentally mean "different arithmetic".
            unconfigured = ReplenishmentPolicy()
            candidates = []
            for rule in rules:
                policy = policies.get((rule.item_id, rule.location_id))
                shaping = policy or unconfigured
                if not shaping.raises_requisitions:
                    continue  # transfer / manufacture — recorded elsewhere, never bought here

                key = (rule.item_id, rule.location_id)
                sku = rule.item.sku
                held = unsellable.get(key, ZERO)
                allocated = allocations.get(key, ZERO) + reservations.get(key, ZERO)
                hand = on_hand.get(key, ZERO)
                ordered = on_order.get(sku, ZERO) if shaping.include_on_order else ZERO
                requested = open_requisitions.get(sku, ZERO) if shaping.include_open_requisitions else ZERO

                # The TRIGGER is on-hand plus incoming supply — ReorderRule.is_below_point()'s own
                # definition, so a run and the SCM alert can never disagree about whether an item
                # is below its point. `available` is snapshotted alongside (the ONE availability
                # formula, StockLevels.py:124) so a buyer can still see stock that is spoken for.
                supply = hand + ordered + requested
                reorder_point = rule.reorder_point or ZERO
                if supply > reorder_point:
                    continue

                effective = shaping.effective_numbers(rule)
                target = effective["target_level"]["value"]
                if target is None:
                    continue  # nothing supplies an order-up-to level; proposing 0 would be noise
                raw = Decimal(target) - supply
                suggested = shaping.round_quantity(raw)
                if suggested <= ZERO:
                    continue

                unit_cost = rule.item.standard_cost or rule.item.average_cost or ZERO
                lead_time = effective["lead_time_days"]["value"] or 0
                candidates.append(ReplenishmentSuggestion(
                    run=self,
                    item_id=rule.item_id,
                    location_id=rule.location_id,
                    reorder_rule=rule,
                    policy=policy,                       # the REAL policy, null when unconfigured
                    vendor_id=shaping.preferred_vendor_id,
                    on_hand_qty=_q4(hand),
                    allocated_qty=_q4(allocated),
                    on_order_qty=_q4(on_order.get(sku, ZERO)),
                    open_requisition_qty=_q4(open_requisitions.get(sku, ZERO)),
                    available_qty=_q4(hand - allocated - held),
                    reorder_point_snapshot=_q4(reorder_point),
                    target_level_snapshot=_q4(target),
                    raw_suggested_qty=_q4(raw),
                    suggested_qty=_q4(suggested),
                    unit_cost=_q4(unit_cost),
                    lead_time_days=int(lead_time),
                ))

            # The cap keeps the HIGHEST-VALUE shortfalls rather than the alphabetically luckiest —
            # if 500 of 900 lines survive, they should be the 500 worth arguing about. Meta
            # ordering puts them back in SKU order for display.
            truncated = len(candidates) > self.MAX_SUGGESTIONS
            if truncated:
                candidates.sort(key=lambda s: s.suggested_qty * s.unit_cost, reverse=True)
                candidates = candidates[:self.MAX_SUGGESTIONS]

            ReplenishmentSuggestion.objects.bulk_create(candidates)
            return self._finish_generation(user, candidates, truncated)

    def _finish_generation(self, user, candidates, truncated):
        """Stamp the run after :meth:`generate` has written its lines. Called inside the atomic."""
        self.notes = self._notes_with_truncation_marker(truncated)
        self.generated_at = timezone.now()
        self.generated_by = user if getattr(user, "is_authenticated", False) else None
        self.status = "proposed"
        self.save(update_fields=["notes", "generated_at", "generated_by", "status", "updated_at"])
        write_audit_log(user, self, "generate",
                        {"lines": len(candidates), "truncated": truncated})
        return len(candidates)

    def _notes_with_truncation_marker(self, truncated):
        """Notes with exactly zero or one truncation marker — never a stack of them.

        Re-generating is expected, so an unconditional append would grow a marker per press. Any
        existing marker line is dropped first and a fresh one added only if the cap bit this time.
        """
        kept = [line for line in (self.notes or "").splitlines()
                if not line.startswith(self.TRUNCATION_PREFIX)]
        if truncated:
            kept.append(
                f"{self.TRUNCATION_PREFIX} this run hit the {self.MAX_SUGGESTIONS}-line cap. The "
                f"highest-value shortfalls were kept and the rest were not proposed. Narrow the "
                f"location or ABC filter and generate again to see them.]")
        return "\n".join(kept).strip()

    # ------------------------------------------------------------------ the commitment
    def release(self, user=None):
        """Turn every accepted suggestion into a **draft** ``scm.PurchaseRequisition``, one per vendor.

        **Draft, never approved.** A released run hands 6.3's approval routing, 6.15's budget check
        and 6.10's PO conversion a normal requisition to work on. Auto-approving here — or writing
        a purchase order directly, the ``inventory:reorderdraft`` shape — would route a machine's
        opinion around every control the workspace has.

        ``select_for_update()`` on the header is what makes a double-clicked Release safe: the
        second request blocks, then finds the status already ``released`` and refuses, instead of
        raising a second identical set of requisitions nobody notices until the invoices arrive.

        Grouping is by ``vendor_id``; lines with no vendor collect into one unassigned requisition
        rather than being dropped, because "we decided to buy this but nobody has picked a supplier"
        is a real state and a buyer completes it on the requisition.

        Returns the list of requisitions created.
        """
        from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine

        with transaction.atomic():
            locked = type(self).objects.select_for_update().select_related("tenant").get(pk=self.pk)
            if locked.status not in self.RELEASABLE_STATUSES:
                raise ValidationError(
                    f"{locked.number} is {locked.get_status_display().lower()} — only a proposed "
                    f"run can be released, and a released one has already raised its requisitions.")

            accepted = list(self.lines.filter(decision="accepted")
                            .select_related("item", "item__uom", "vendor",
                                            "policy", "policy__default_org_unit",
                                            "policy__default_budget", "policy__default_gl_account"))
            if not accepted:
                raise ValidationError(
                    "No line on this run has been accepted. Accept at least one suggestion before "
                    "releasing — a requisition with nothing on it commits nobody to anything.")

            groups = {}
            for line in accepted:
                groups.setdefault(line.vendor_id, []).append(line)

            requester = user if getattr(user, "is_authenticated", False) else None
            created = []
            for vendor_id, lines in groups.items():
                vendor_name = lines[0].vendor.name if lines[0].vendor_id else "Unassigned vendor"
                # The requisition's department / budget come from the FIRST line in the group that
                # names one. Policies inside a vendor group can legitimately disagree; picking the
                # first is deterministic (lines arrive in Meta order) and a buyer can change it on
                # the draft, which is precisely what a draft is for.
                org_unit_id = next((l.policy.default_org_unit_id for l in lines
                                    if l.policy_id and l.policy.default_org_unit_id), None)
                budget_id = next((l.policy.default_budget_id for l in lines
                                  if l.policy_id and l.policy.default_budget_id), None)
                lead = max((l.lead_time_days or 0) for l in lines)

                requisition = PurchaseRequisition(
                    tenant=locked.tenant,
                    title=f"Replenishment {locked.number} — {vendor_name}"[:255],
                    requester=requester,
                    org_unit_id=org_unit_id,
                    budget_id=budget_id,
                    required_by=locked.run_date + timedelta(days=lead),
                    status="draft",
                    justification=(
                        f"Raised by replenishment run {locked.number} ({locked.scope_label}, "
                        f"{locked.run_date}). Every line was below its reorder point after netting "
                        f"off stock on hand and incoming supply, and was accepted by a buyer."),
                )
                requisition.save()   # save(), not bulk_create: TenantNumbered mints PR-##### here

                requisition_lines = []
                for line in lines:
                    price = q2(line.unit_cost)
                    requisition_lines.append(PurchaseRequisitionLine(
                        requisition=requisition,
                        item_description=line.item.name,
                        sku_hint=line.item.sku,
                        # Item.uom is NULLABLE (Items.py:96) — an item with no unit of measure is
                        # ordinary, and reaching through it unguarded is an AttributeError 500.
                        uom_hint=(line.item.uom.code if line.item.uom_id else ""),
                        quantity=line.suggested_qty,
                        estimated_unit_price=price,
                        # bulk_create bypasses save(), and PurchaseRequisitionLine.save() is where
                        # line_total is derived (PurchaseRequisitions.py:170-172). Stamping it here
                        # with the identical expression is what keeps recalc_totals() — which SUMS
                        # this column — from totalling a column full of zeros.
                        line_total=q2(line.suggested_qty * price),
                        gl_account_id=(line.policy.default_gl_account_id if line.policy_id else None),
                        needed_by=locked.run_date + timedelta(days=line.lead_time_days or 0),
                    ))
                PurchaseRequisitionLine.objects.bulk_create(requisition_lines)
                requisition.recalc_totals()

                for line in lines:
                    line.requisition = requisition
                ReplenishmentSuggestion.objects.bulk_update(lines, ["requisition"])
                created.append(requisition)

            self.status = "released"
            self.released_at = timezone.now()
            self.save(update_fields=["status", "released_at", "updated_at"])

        write_audit_log(user, self, "release",
                        {"requisitions": [r.number for r in created], "lines": len(accepted)})
        return created

    def cancel(self, user=None):
        """Abandon a proposal. Refused once released — that run raised real requisitions.

        Cancelling a released run would leave draft requisitions with nothing explaining where they
        came from. The correction for an unwanted requisition is to cancel THAT requisition, on its
        own document, where 6.2's amendment trail records who did it.
        """
        with transaction.atomic():
            locked = type(self).objects.select_for_update().get(pk=self.pk)
            if locked.status not in self.CANCELLABLE_STATUSES:
                raise ValidationError(
                    f"{locked.number} is {locked.get_status_display().lower()} and cannot be "
                    f"cancelled. A released run has already raised requisitions — cancel those on "
                    f"their own documents instead.")
            self.status = "cancelled"
            self.save(update_fields=["status", "updated_at"])
        write_audit_log(user, self, "cancel", {"from": locked.status})
        return True

    # ------------------------------------------------------------------ validation
    def clean(self):
        super().clean()
        errors = {}
        tenant_id = getattr(self, "tenant_id", None)
        if tenant_id and self.location_id:
            if getattr(getattr(self, "location", None), "tenant_id", None) != tenant_id:
                errors["location"] = "That location belongs to another workspace."
        if errors:
            raise ValidationError(errors)


class ReplenishmentSuggestion(models.Model):
    """One proposed line on a run: what was short, by how much, and what the buyer decided.

    **Every quantity column is a SNAPSHOT and every one of them is ``editable=False``.** They are
    written once by :meth:`ReplenishmentRun.generate` and never by a form. That is the whole point:
    stock moves constantly, and a proposal that re-read live figures could not explain, a week
    later, why it asked for 40 of something the workspace now has 200 of. Precedent:
    ``CycleCountTaskLine.expected_quantity`` (``CycleCountTasks.py:97-98``).

    **The buyer-editable surface is exactly four fields** — ``decision``, ``snooze_until``,
    ``vendor`` and ``decision_note`` — and ``ReplenishmentSuggestionDecisionForm`` exposes those
    four and nothing else. ``vendor`` is editable because the policy's preferred vendor is a
    default, not a verdict, and the person accepting the line is the one who knows.

    **No tenant column.** Tenant is reached THROUGH the run, and every query in this sub-module
    filters ``run__tenant`` — which is also where the IDOR boundary sits for the decide verb.
    A second tenant FK here would be a second answer to the same question, free to drift.
    """

    DECISION_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("snoozed", "Snoozed"),
        ("dismissed", "Dismissed"),
    ]
    DECISION_CSS = {"pending": "badge-muted", "accepted": "badge-green",
                    "snoozed": "badge-amber", "dismissed": "badge-slate"}

    run = models.ForeignKey(ReplenishmentRun, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT,
                             related_name="procurement_replenishment_suggestions")
    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT,
                                 related_name="procurement_replenishment_suggestions")
    reorder_rule = models.ForeignKey(
        "scm.ReorderRule", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_replenishment_suggestions",
        help_text="The rule this line was computed from. SET_NULL — deleting a rule must not "
                  "delete the record of a decision that was taken while it existed.")
    policy = models.ForeignKey(
        "procurement.ReplenishmentPolicy", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="suggestions",
        help_text="The policy that shaped this line. Null means the item had none and the run used "
                  "plain defaults — which is worth seeing, not worth hiding.")
    vendor = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_replenishment_suggestions",
        help_text="Vendor this line is grouped under at release. Defaulted from the policy and "
                  "overridable per line.")
    requisition = models.ForeignKey(
        "scm.PurchaseRequisition", on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="procurement_replenishment_suggestions",
        help_text="The requisition this line was released into (system-stamped)")

    # --- the snapshot: what the numbers were at the moment the proposal was made ---------------
    on_hand_qty = models.DecimalField(max_digits=16, decimal_places=4, default=0, editable=False)
    allocated_qty = models.DecimalField(max_digits=16, decimal_places=4, default=0, editable=False,
                                        help_text="Sales-order allocations plus inventory reservations")
    on_order_qty = models.DecimalField(max_digits=16, decimal_places=4, default=0, editable=False,
                                       help_text="Outstanding on receivable purchase orders, "
                                                 "network-wide (PO lines carry no location)")
    open_requisition_qty = models.DecimalField(max_digits=16, decimal_places=4, default=0,
                                               editable=False)
    available_qty = models.DecimalField(max_digits=16, decimal_places=4, default=0, editable=False,
                                        help_text="on hand − claims − non-sellable. Recorded for "
                                                  "the reader; the trigger is on-hand plus supply.")
    reorder_point_snapshot = models.DecimalField(max_digits=16, decimal_places=4, default=0,
                                                 editable=False)
    target_level_snapshot = models.DecimalField(max_digits=16, decimal_places=4, default=0,
                                                editable=False)
    raw_suggested_qty = models.DecimalField(max_digits=16, decimal_places=4, default=0,
                                            editable=False,
                                            help_text="The shortfall before rounding — kept so the "
                                                      "rounding is auditable, not just its result")
    suggested_qty = models.DecimalField(max_digits=16, decimal_places=4, default=0, editable=False)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    lead_time_days = models.PositiveIntegerField(default=0, editable=False)

    # --- the decision: the only thing a person edits -------------------------------------------
    decision = models.CharField(max_length=12, choices=DECISION_CHOICES, default="pending")
    snooze_until = models.DateField(null=True, blank=True,
                                    help_text="Required when snoozing, and it has to be in the "
                                              "future — a snooze that has already expired is a "
                                              "dismissal wearing a different label.")
    decision_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["item__sku", "id"]
        indexes = [models.Index(fields=["run", "decision"], name="prc_rsg_run_dec_idx")]
        verbose_name = "Replenishment Suggestion"
        verbose_name_plural = "Replenishment Suggestions"

    def __str__(self):
        if not self.item_id:
            return "Replenishment suggestion"
        return f"{self.item.sku} ×{self.suggested_qty}"

    @property
    def line_value(self):
        """``suggested_qty × unit_cost`` — derived on read, never stored.

        A stored line value is a third number that can disagree with the two it comes from, and
        both of those are already immutable snapshots.
        """
        return (self.suggested_qty or ZERO) * (self.unit_cost or ZERO)

    @property
    def decision_css(self):
        return self.DECISION_CSS.get(self.decision, "badge-muted")

    @property
    def is_released(self):
        return self.requisition_id is not None

    def clean(self):
        super().clean()
        errors = {}
        # Tenant is reached through the RUN — this model has no tenant column of its own, and the
        # run is the only thing that knows which workspace a line belongs to.
        tenant_id = self.run.tenant_id if self.run_id else None
        if tenant_id:
            for field in ("item", "location", "vendor", "policy", "reorder_rule"):
                if not getattr(self, f"{field}_id", None):
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        if self.decision == "snoozed":
            if self.snooze_until is None:
                errors["snooze_until"] = ("Pick the date this comes back. A snooze with no date is "
                                          "a dismissal nobody agreed to.")
            elif self.snooze_until <= timezone.localdate():
                errors["snooze_until"] = ("The snooze date has to be in the future — one already "
                                          "past would hide the line without ever returning it.")

        if errors:
            raise ValidationError(errors)
