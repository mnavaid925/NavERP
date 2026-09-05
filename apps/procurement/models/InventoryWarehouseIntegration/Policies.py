"""Procurement 6.18 Inventory & Warehouse Integration — ReplenishmentPolicy.

**What it is.** The procurement-side overlay on ``scm.ReorderRule``. The rule (4.3, extended by
4.7) already owns the *planning* numbers — reorder point, safety stock, lead time, ABC class — and
4.7 owns the calculation that proposes them. What it does NOT say is anything procurement needs to
turn a "you are below the point" signal into a purchase: **who** to buy from, **how much** to round
the quantity to, and **what defaults** the generated requisition should carry. That glue is
procurement's to own, and it is exactly the NavERP.md "Reorder Point Automation" bullet.

**What it is NOT.** It is not a second reorder rule (L36 — link out, never restate). No column here
holds a reorder point, a safety stock or an ABC class: those stay on ``scm.ReorderRule`` and the
detail page reads them through. The two columns that look like duplicates are deliberately
*overrides*, and are documented as such on the fields themselves:

* :attr:`target_level` — an order-up-to level. Blank falls back to
  ``rule.reorder_point + rule.safety_stock``, so a workspace that never sets one behaves exactly as
  it did before this model existed.
* :attr:`lead_time_days_override` — blank falls back to ``rule.lead_time_days``.

**The behavioural gap it closes.** ``ReorderRule.is_below_point()``
(``apps/scm/models/InventoryManagement/ReorderRules.py:133``) tests **on-hand only**. A workspace
with a purchase order already in flight is therefore told to order again, every time the page is
opened. :attr:`include_on_order` and :attr:`include_open_requisitions` are what let a 6.18
replenishment run net incoming supply off the shortfall before it proposes anything.

**Configuration master, not a document.** ``TenantOwned``, not ``TenantNumbered`` — the
``ReceiptTolerancePolicy`` / ``SpendClassificationRule`` / ``inventory.PutawayRule`` precedent. It
gets no sidebar entry either: it is configuration reached from the run register, not somewhere
anybody navigates to first.

**Nullable-unique honesty.** ``unique_together = ("tenant", "item", "location")`` is the right
grain (the same one ``ReorderRule.Meta`` uses), but ``location`` is nullable — *null means "any
location"* — and **SQL compares NULLs as distinct**, so the database constraint will happily accept
a second catch-all row for the same item, after which :meth:`resolve` would have two equally valid
answers. The constraint cannot be made to cover that portably, so :meth:`clean` probes for the one
case explicitly and rejects it as a field error. (Same reasoning as ``BudgetMapping``'s note that
"a nullable-column unique would not be portable anyway",
``apps/procurement/models/BudgetCostManagement/BudgetMappings.py:14-17``.) :meth:`resolve_map` is
additionally written to be deterministic — oldest row wins — so even a row that predates this probe
cannot make the resolver flip its answer between requests.

**Import discipline.** Every cross-app FK is a STRING; ``core.PartyRole`` is imported INSIDE
:meth:`clean` rather than at module scope, mirroring the rest of this app.
"""
from decimal import ROUND_CEILING

from apps.procurement.models._base import *  # noqa: F401,F403


class ReplenishmentPolicy(TenantOwned):
    """How this workspace replenishes one item — at one location, or anywhere (``location`` null)."""

    SOURCE_METHOD_CHOICES = [
        ("buy", "Buy"),
        ("transfer", "Transfer"),
        ("manufacture", "Manufacture"),
    ]
    TRIGGER_MODE_CHOICES = [
        ("review", "Review then release"),
        ("auto", "Automatic"),
    ]

    #: The source methods a replenishment run may raise a requisition for. ``transfer`` and
    #: ``manufacture`` are recognised, stored and reported on, but they are not purchases: a
    #: transfer is scm's stock-transfer document and a manufacture is 4.8's work order. A run skips
    #: them and the pages link out, instead of quietly buying something that should have been
    #: moved. Read this tuple rather than hard-coding ``"buy"`` anywhere.
    REQUISITIONABLE_SOURCE_METHODS = ("buy",)

    #: theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
    #: badge-slate (L33) — a semantic badge-success renders unstyled.
    ACTIVE_CSS = {True: "badge-green", False: "badge-muted"}
    SOURCE_CSS = {"buy": "badge-info", "transfer": "badge-amber", "manufacture": "badge-slate"}
    #: ``auto`` is the amber one on purpose: it is the mode that proposes without a person asking.
    TRIGGER_CSS = {"review": "badge-slate", "auto": "badge-amber"}

    # --- scope: which item, and where ---------------------------------------------------------
    # PROTECT, mirroring BudgetMapping.budget: deleting an item a policy still governs would
    # silently un-configure its replenishment. The policy has to be removed or re-pointed first.
    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT,
        related_name="procurement_replenishment_policies",
        help_text="The item this policy replenishes")
    location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_replenishment_policies",
        help_text="Location this policy applies to. Blank = any location — the catch-all that a "
                  "location-specific policy overrides.")

    # --- sourcing -----------------------------------------------------------------------------
    source_method = models.CharField(
        max_length=12, choices=SOURCE_METHOD_CHOICES, default="buy",
        help_text="How the shortfall is covered. Only 'Buy' raises a requisition; 'Transfer' and "
                  "'Manufacture' are recorded and reported but never purchased automatically.")
    trigger_mode = models.CharField(
        max_length=8, choices=TRIGGER_MODE_CHOICES, default="review",
        help_text="'Review then release' proposes and waits for a person. 'Automatic' marks the "
                  "policy as one a scheduled run may propose for — releasing the money is still a "
                  "human action either way.")
    preferred_vendor = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_replenishment_policies",
        help_text="Vendor the generated requisition is grouped under (blank = decided at release)")

    # --- quantity shaping: the ONE place rounding is configured -------------------------------
    target_level = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Order-up-to level. Blank falls back to the reorder rule's reorder point plus "
                  "safety stock — this is an OVERRIDE, never a copy of the rule.")
    order_multiple = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Round the suggested quantity UP to a multiple of this (case or pallet size)")
    min_order_qty = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Vendor minimum order quantity — a smaller shortfall is raised to this")
    max_order_qty = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Hard ceiling on one suggested line. Applied LAST, so it wins over the multiple.")

    # --- what counts as supply already on its way ---------------------------------------------
    include_on_order = models.BooleanField(
        default=True,
        help_text="Net open purchase-order quantity off the shortfall before proposing. The scm "
                  "reorder alert tests on-hand alone, which is why it keeps re-proposing what has "
                  "already been ordered.")
    include_open_requisitions = models.BooleanField(
        default=True,
        help_text="Also net off quantity already sitting on un-converted requisitions")
    lead_time_days_override = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(3650)],
        help_text="Replenishment lead time in days. Blank falls back to the reorder rule's own "
                  "lead time — this is an OVERRIDE, never a copy.")

    # --- defaults stamped onto the requisition a run raises -----------------------------------
    default_org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_replenishment_policies",
        help_text="Department / cost centre to stamp on the generated requisition")
    default_budget = models.ForeignKey(
        "accounting.Budget", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_replenishment_policies",
        help_text="Budget to stamp on the generated requisition (the amounts stay in accounting)")
    default_gl_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_replenishment_policies",
        help_text="Expense account to pre-fill on the generated requisition line")

    is_active = models.BooleanField(
        default=True,
        help_text="Inactive policies are never resolved. Prefer deactivating over deleting when an "
                  "item is phased out — the history stays readable.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["item__sku", "location__code", "id"]
        # The same grain as ReorderRule.Meta — one policy per item per location. See the module
        # docstring for the catch-all row this constraint provably CANNOT cover.
        unique_together = ("tenant", "item", "location")
        indexes = [
            # Backs resolve_map()'s hot query: tenant + is_active + item is exactly the filter it
            # issues, so the resolver is served from the index rather than from a scan.
            models.Index(fields=["tenant", "is_active", "item"], name="prc_rpol_tnt_active_idx"),
            # Backs the register's default ORDER BY, and the (item, location) lookups the detail
            # page and the clean() catch-all probe both make.
            models.Index(fields=["tenant", "item", "location"], name="prc_rpol_tnt_item_loc_idx"),
        ]
        verbose_name = "Replenishment Policy"
        verbose_name_plural = "Replenishment Policies"

    def __str__(self):
        # Guarded on the id: on an UNSAVED instance (a ModelForm rendering its own errors)
        # ``self.item`` raises RelatedObjectDoesNotExist, and a validation page must never 500.
        if not self.item_id:
            return "Replenishment policy"
        return f"{self.item.sku} @ {self.scope_label}"

    # ------------------------------------------------------------------ display helpers
    @property
    def scope_label(self):
        """Where this policy applies, as one readable phrase."""
        return self.location.code if self.location_id else "Any location"

    @property
    def status_css(self):
        return self.ACTIVE_CSS.get(bool(self.is_active), "badge-muted")

    @property
    def status_label(self):
        return "Active" if self.is_active else "Inactive"

    @property
    def source_css(self):
        return self.SOURCE_CSS.get(self.source_method, "badge-muted")

    @property
    def trigger_css(self):
        return self.TRIGGER_CSS.get(self.trigger_mode, "badge-muted")

    @property
    def raises_requisitions(self):
        """True when a replenishment run may turn this policy's shortfall into a requisition."""
        return self.source_method in self.REQUISITIONABLE_SOURCE_METHODS

    # ------------------------------------------------------------------ quantity shaping
    def round_quantity(self, raw):
        """The SINGLE rounding implementation in this sub-module. Nothing else re-implements it.

        Applied in this order, and the order IS the contract:

        1. **Never negative.** A non-positive shortfall is not an order — it comes back as ``0``.
        2. **Floor at** :attr:`min_order_qty` — the vendor's minimum.
        3. **Round UP to the next** :attr:`order_multiple` — you cannot buy two thirds of a pallet.
        4. **Cap at** :attr:`max_order_qty`.

        The cap is applied LAST and therefore wins over the multiple: with a multiple of 30 and a
        cap of 100, a shortfall of 95 comes back as 100, not 120. That is deliberate — a ceiling a
        caller can exceed is not a ceiling — and it is why :meth:`clean` refuses a ``max`` below a
        ``min`` rather than leaving the two rules to fight over the answer.

        ``> ZERO`` rather than plain truthiness on the multiple and the cap: a stored ``0`` would
        divide by zero / clamp everything to nothing, and a seeded row never went through the
        form's validators.

        Accepts anything ``Decimal`` can be built from (int / float / str / ``None``) and returns a
        ``Decimal`` quantized to 4dp — the shape of the suggestion column that stores it.
        """
        qty = raw if isinstance(raw, Decimal) else Decimal(str(raw or 0))
        if qty <= ZERO:
            return ZERO

        floor = self.min_order_qty
        if floor and floor > ZERO and qty < floor:
            qty = floor

        multiple = self.order_multiple
        if multiple and multiple > ZERO:
            qty = (qty / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple

        ceiling = self.max_order_qty
        if ceiling is not None and ceiling > ZERO and qty > ceiling:
            qty = ceiling

        return qty.quantize(Decimal("0.0001")) if qty > ZERO else ZERO

    # ------------------------------------------------------------------ planning figures
    def effective_numbers(self, rule):
        """The four planning figures a run would actually use, each labelled with its source.

        The SINGLE place the override-versus-fallback rule is written down, and it matches this
        model's own docstring exactly:

        * ``reorder_point`` / ``safety_stock`` are the rule's, always — no column on this policy
          holds either, and adding one would be the second reorder rule L36 forbids.
        * ``target_level`` is the policy's when set, else ``reorder_point + safety_stock``.
        * ``lead_time_days`` is the policy's override when set, else the rule's own lead time.

        ``lead_time_days_override`` is tested with ``is not None`` rather than truthiness: a
        genuine override of ``0`` (an item collected the same day) is falsy and would otherwise
        silently fall back to the rule's figure.

        Takes anything with the four ``ReorderRule`` columns, or ``None`` when this item has no
        rule. Returns ``{name: {"value": ..., "source": ...}}``. ``value`` is ``None`` exactly when
        nothing supplies the figure, and ``source`` then reads "not configured" — a blank cell with
        no explanation is how a reader concludes the number is zero.

        **It lives HERE, on the model, and not on the detail view that needed it first.** It takes
        no request, touches no template and renders nothing: it is pure override-versus-fallback
        arithmetic over this policy's own columns. Parked in the views layer it forced
        ``ReplenishmentRun.generate()`` to import UPWARD into ``apps.procurement.views`` at call
        time — the only model→views import in the repo — which dragged the whole views + forms +
        ``apps.core.crud`` import graph in behind it and made the obvious tidy-up (promoting that
        import to module scope) a circular import. The goal was always right: one written-down
        definition so the detail page and the run cannot disagree about what a policy means. Only
        the placement was upside down.
        """
        POLICY, RULE, NONE = "policy override", "reorder rule", "not configured"

        def entry(value, source):
            return {"value": value, "source": NONE if value is None else source}

        reorder_point = rule.reorder_point if rule else None
        safety_stock = rule.safety_stock if rule else None

        if self.target_level is not None:
            target = entry(self.target_level, POLICY)
        elif reorder_point is not None:
            target = entry((reorder_point or 0) + (safety_stock or 0), RULE)
        else:
            target = entry(None, NONE)

        if self.lead_time_days_override is not None:
            lead_time = entry(self.lead_time_days_override, POLICY)
        else:
            lead_time = entry(rule.lead_time_days if rule else None, RULE)

        return {
            "reorder_point": entry(reorder_point, RULE),
            "safety_stock": entry(safety_stock, RULE),
            "target_level": target,
            "lead_time_days": lead_time,
        }

    # ------------------------------------------------------------------ resolution
    @classmethod
    def resolve(cls, tenant, item, location=None):
        """The ACTIVE policy governing this item at this location, or ``None``.

        Specificity first: an exact ``(item, location)`` row wins, then the ``(item, null)``
        catch-all, else nothing. Accepts model instances or raw pks for both arguments.

        **Costs one query.** A caller resolving a whole batch must use :meth:`resolve_map` instead
        — a per-row ``resolve()`` inside a loop is exactly the N+1 that ``ReorderRule.on_hand_map``
        exists to avoid.
        """
        item_id = getattr(item, "pk", item)
        location_id = getattr(location, "pk", location)
        return cls.resolve_map(tenant, [(item_id, location_id)]).get((item_id, location_id))

    @classmethod
    def resolve_map(cls, tenant, pairs):
        """``{(item_id, location_id): policy | None}`` for every pair, in ONE query.

        The single definition of "which policy wins" — :meth:`resolve` is a one-pair door onto this
        method, so a batch and a single lookup can never disagree.

        Determinism note: candidates are read in ``id`` order and folded with ``setdefault``, so the
        OLDEST row wins whenever two could match. The unique constraint already makes that
        impossible for a located policy and :meth:`clean` closes the catch-all hole — but a resolver
        that flipped its answer between requests because of a row predating that probe would be far
        worse than one that is merely opinionated.
        """
        if tenant is None or not pairs:
            return {}

        normalized = [(getattr(item, "pk", item), getattr(location, "pk", location))
                      for item, location in pairs]
        item_ids = {item_id for item_id, _ in normalized if item_id}
        if not item_ids:
            return {}

        rows = (cls.objects
                .filter(tenant=tenant, is_active=True, item_id__in=item_ids)
                .select_related("item", "item__uom", "location", "preferred_vendor",
                                "default_org_unit", "default_budget", "default_gl_account")
                .order_by("id"))

        located, catch_all = {}, {}
        for policy in rows:
            if policy.location_id is None:
                catch_all.setdefault(policy.item_id, policy)
            else:
                located.setdefault((policy.item_id, policy.location_id), policy)

        return {key: located.get(key) or catch_all.get(key[0]) for key in normalized}

    # ------------------------------------------------------------------ validation
    def clean(self):
        super().clean()
        errors = {}
        tenant_id = getattr(self, "tenant_id", None)

        # Cross-tenant guard on every FK. The same tenant is not the same subject: a narrowed
        # <select> is UX, and this is the model-level backstop behind the form's own re-check.
        # ``item`` is validated too — a crafted POST could point a policy at another workspace's
        # item even though the dropdown never offered it.
        if tenant_id:
            for field in ("item", "location", "preferred_vendor", "default_org_unit",
                          "default_budget", "default_gl_account"):
                fk_id = getattr(self, f"{field}_id", None)
                if not fk_id:
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        # The nullable-unique probe (see the module docstring). unique_together cannot catch a
        # second catch-all row, because SQL compares NULLs as distinct — so it is caught here, as a
        # field error on the field that actually causes it.
        if tenant_id and self.item_id and self.location_id is None and "item" not in errors:
            clash = type(self).objects.filter(
                tenant_id=tenant_id, item_id=self.item_id, location__isnull=True)
            if self.pk:
                clash = clash.exclude(pk=self.pk)
            if clash.exists():
                errors["location"] = ("This item already has an any-location policy. Pick a "
                                      "location, or edit the existing catch-all instead — two of "
                                      "them would make the resolved policy ambiguous.")

        if (self.min_order_qty is not None and self.max_order_qty is not None
                and self.max_order_qty < self.min_order_qty):
            errors["max_order_qty"] = ("The maximum order quantity cannot be below the minimum — "
                                       "the cap is applied last and would silently undo it.")

        if self.target_level is not None and self.target_level <= ZERO:
            errors["target_level"] = ("An order-up-to level has to be above zero. Leave it blank "
                                      "to fall back to the reorder rule's point plus safety stock.")

        # A preferred vendor has to be a party this workspace can actually buy from. BOTH roles are
        # accepted — core.PartyRole distinguishes 'supplier' from 'vendor', and hiding half the
        # counterparties would be a worse bug than the one this check prevents.
        if self.preferred_vendor_id and "preferred_vendor" not in errors:
            from apps.core.models import PartyRole

            is_supplier = PartyRole.objects.filter(
                party_id=self.preferred_vendor_id, role__in=("supplier", "vendor")).exists()
            if not is_supplier:
                errors["preferred_vendor"] = ("That party is not a supplier or vendor. Give it a "
                                              "supplier role first, or leave the preferred vendor "
                                              "blank and decide at release.")

        if errors:
            raise ValidationError(errors)
