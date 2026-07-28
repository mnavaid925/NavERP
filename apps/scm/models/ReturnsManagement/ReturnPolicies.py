"""SCM 4.10 Returns Management — ReturnPolicy, the published promise (no NUMBER_PREFIX).

Three things live here that nothing else in the codebase can hold, and they are why this table
earns a slot rather than being a handful of fields on the RMA:

1. **The grade → cost write-down.** ``grade_a_cost_pct`` … ``grade_d_cost_pct`` are what turn
   ``ReturnDisposition.condition_grade`` from decoration into money: a B-grade unit comes back into
   stock at 75% of its average cost, so the valuation report and the weighted-average roll reflect
   what the thing is actually worth now. Without this the grade is a dropdown nobody reads.
2. **The return-to address.** ``scm.Location`` has NO address field — verified: code, name,
   location_type, parent, is_active, capacity, pick_sequence, abc_class, is_pickable. There is no
   path from a warehouse to a printable address anywhere in this app, so the return slip's
   return-to block is :attr:`ReturnPolicy.return_to_address`, free text, deliberately.
3. **The window basis.** Whether the clock starts at delivery, at fulfilment or at the order date
   is a policy decision, and ``window_basis`` + ``fallback_days`` is Loop's documented answer to
   the fact that delivery events are unreliable.

**Eligibility is a PURE FUNCTION** — :func:`evaluate_return_eligibility`. It PROPOSES; a human
presses Approve. Its dict is snapshotted into ``ReturnAuthorization.policy_snapshot`` at approval
(the 4.9 ``InspectionResult`` snapshot precedent) so editing a policy next month cannot rewrite
last month's decision.

``auto_approve`` PRE-FILLS the approve form and never auto-acts. An RMA that approves itself is an
RMA nobody looked at, and every approval in this module stamps ``approved_by``.
"""
import datetime

from apps.scm.models._base import *  # noqa: F401,F403

ONE_HUNDRED = Decimal("100")


class ReturnPolicy(TenantOwned):
    """What we promise a returning customer, per item category."""

    WINDOW_BASIS_CHOICES = [
        ("delivery", "Delivery date"),
        ("fulfilment", "Fulfilment / ship date"),
        ("order_date", "Order date"),
    ]
    REFUND_BASIS_CHOICES = [
        ("full", "Full value"),
        ("percentage", "Percentage of value"),
        ("none", "No refund"),
    ]
    RESTOCKING_FEE_CHOICES = [
        ("none", "No fee"),
        ("flat", "Flat amount"),
        ("percent_of_value", "Percentage of value"),
    ]
    SHIPPING_PAID_BY_CHOICES = [
        ("customer", "Customer"),
        ("merchant", "Us (merchant)"),
        ("by_fault", "Whoever is at fault"),
    ]

    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="The catch-all policy used when no category-specific one matches")
    priority = models.PositiveIntegerField(
        default=100, help_text="Lowest number wins when more than one policy matches")
    item_category = models.ForeignKey(
        "scm.ItemCategory", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_return_policies",
        help_text="Leave blank to apply to every item")

    # --- the window -----------------------------------------------------------------------------
    window_basis = models.CharField(max_length=10, choices=WINDOW_BASIS_CHOICES, default="delivery")
    window_days = models.PositiveIntegerField(default=30)
    require_delivery_confirmation = models.BooleanField(
        default=False,
        help_text="Refuse a return until the order carries a delivery stamp. Note that stamp is a "
                  "MANUAL human action in 4.5 — turning this on will refuse a lot of honest returns")
    fallback_days = models.PositiveIntegerField(
        default=45,
        help_text="Window measured from the ORDER date when the basis event never happened — "
                  "Loop's documented answer to unreliable delivery events")

    # --- what the customer may be offered -------------------------------------------------------
    allow_refund = models.BooleanField(default=True)
    allow_store_credit = models.BooleanField(default=True)
    allow_exchange = models.BooleanField(default=True)
    allow_keep_item = models.BooleanField(
        default=False,
        help_text="Refund without asking for the goods back (returnless refund) — cheap items "
                  "where the freight costs more than the unit")

    refund_basis = models.CharField(max_length=10, choices=REFUND_BASIS_CHOICES, default="full")
    refund_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=ONE_HUNDRED,
        validators=[MinValueValidator(ZERO), MaxValueValidator(ONE_HUNDRED)],
        help_text="Only meaningful when the basis is 'Percentage of value'")
    restocking_fee_type = models.CharField(max_length=18, choices=RESTOCKING_FEE_CHOICES,
                                           default="none")
    restocking_fee_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    return_shipping_paid_by = models.CharField(max_length=10, choices=SHIPPING_PAID_BY_CHOICES,
                                               default="customer")
    auto_approve = models.BooleanField(
        default=False,
        help_text="Pre-tick the approval form for returns matching this policy. It NEVER approves "
                  "on its own — every approval stamps who did it")

    # --- the grade ladder: what a returned unit is worth back in stock ---------------------------
    # The industry split is roughly A 60-70% straight back, B 15-20% refurbish, C 10-15% secondary
    # channel, D 5-10% dispose — so the defaults below are a real curve, not four round numbers.
    grade_a_cost_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=ONE_HUNDRED,
        validators=[MinValueValidator(ZERO), MaxValueValidator(ONE_HUNDRED)])
    grade_b_cost_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("75"),
        validators=[MinValueValidator(ZERO), MaxValueValidator(ONE_HUNDRED)])
    grade_c_cost_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("40"),
        validators=[MinValueValidator(ZERO), MaxValueValidator(ONE_HUNDRED)])
    grade_d_cost_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO), MaxValueValidator(ONE_HUNDRED)])

    warranty_window_days = models.PositiveIntegerField(
        default=365,
        help_text="Supplier/manufacturer warranty length used by WarrantyClaim.is_in_warranty")

    return_to_address = models.TextField(
        blank=True,
        help_text="Printed on the return slip. scm.Location has no address field, so this free "
                  "text IS the return-to block — there is nowhere else to get it from")
    portal_instructions = models.TextField(
        blank=True, help_text="Rendered on the public return-status page for the customer")

    class Meta:
        ordering = ["priority", "name"]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="scm_rtnpolicy_tnt_act_idx"),
            models.Index(fields=["tenant", "item_category"], name="scm_rtnpolicy_tnt_cat_idx"),
        ]
        verbose_name_plural = "return policies"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.refund_basis == "percentage" and (self.refund_pct or ZERO) <= ZERO:
            raise ValidationError(
                {"refund_pct": "A percentage refund of 0% refunds nothing — set a percentage or "
                               "change the basis to 'No refund'."})
        if self.restocking_fee_type != "none" and (self.restocking_fee_value or ZERO) <= ZERO:
            raise ValidationError(
                {"restocking_fee_value": "A restocking fee is configured but its value is zero."})
        if self.restocking_fee_type == "percent_of_value" and (
                self.restocking_fee_value or ZERO) > ONE_HUNDRED:
            raise ValidationError(
                {"restocking_fee_value": "A percentage restocking fee cannot exceed 100%."})
        if self.window_days == 0 and self.fallback_days == 0:
            raise ValidationError(
                {"window_days": "A zero-day window on both the basis and the fallback accepts no "
                                "return at all."})

    # --- derived (nothing below is stored) -----------------------------------------------------
    @property
    def allowed_resolutions(self):
        """The RMA ``resolution`` values this policy permits. Intersected with the reason's own set
        by :func:`evaluate_return_eligibility` — a reason may narrow this, never widen it."""
        out = []
        if self.allow_refund:
            out.append("refund")
        if self.allow_store_credit:
            out.append("store_credit")
        if self.allow_exchange:
            out.append("exchange")
        if self.allow_keep_item:
            out.append("keep_item")
        return tuple(out)

    def grade_cost_pct(self, grade):
        """The write-down percentage for a condition grade. Unknown grade → 0%, deliberately.

        Falling back to 100% would restock an ungraded unit at full cost, which is the expensive
        direction to be wrong in: it overstates inventory value and rolls ``Item.average_cost``
        upward on goods somebody could not even be bothered to grade.
        """
        return {
            "a": self.grade_a_cost_pct,
            "b": self.grade_b_cost_pct,
            "c": self.grade_c_cost_pct,
            "d": self.grade_d_cost_pct,
        }.get((grade or "").lower(), ZERO) or ZERO

    def restock_cost_for(self, grade, base_cost):
        """Seed a ``ReturnDisposition.restock_unit_cost`` from a grade and the item's average cost.

        SEEDS it. Once the row exists the figure is human-owned and nothing recomputes it — the
        ``NonConformance.cost_of_quality`` posture, for the same reason: a refurbisher who spent
        forty pounds on parts knows what the unit is worth better than a percentage table does.
        """
        return q4((base_cost or ZERO) * self.grade_cost_pct(grade) / ONE_HUNDRED)

    def fee_for(self, value):
        """The restocking fee this policy charges against a line value."""
        if self.restocking_fee_type == "flat":
            return q2(self.restocking_fee_value or ZERO)
        if self.restocking_fee_type == "percent_of_value":
            return q2((value or ZERO) * (self.restocking_fee_value or ZERO) / ONE_HUNDRED)
        return ZERO

    def refund_for(self, value):
        """The gross credit this policy allows against a line value, BEFORE any fee is netted."""
        if self.refund_basis == "full":
            return q2(value or ZERO)
        if self.refund_basis == "percentage":
            return q2((value or ZERO) * (self.refund_pct or ZERO) / ONE_HUNDRED)
        return ZERO


def select_policy(tenant, item=None):
    """The policy that governs a return of ``item``: most specific first, then ``priority``.

    A category-specific policy beats a blanket one; among equals the lowest ``priority`` wins; the
    ``is_default`` flag is the last resort. Returns ``None`` when the tenant has configured none —
    every caller must cope with that rather than assume a policy exists (a fresh workspace has no
    policies and the RMA form is still usable).
    """
    if tenant is None:
        return None
    qs = ReturnPolicy.objects.filter(tenant=tenant, is_active=True)
    category_id = getattr(item, "category_id", None)
    if category_id:
        match = qs.filter(item_category_id=category_id).order_by("priority", "id").first()
        if match is not None:
            return match
    return (qs.filter(item_category__isnull=True).order_by("-is_default", "priority", "id").first()
            or qs.order_by("-is_default", "priority", "id").first())


def evaluate_return_eligibility(sales_order, item, reason, policy, as_of=None, line_value=ZERO):
    """Decide whether a return may be authorised — a PURE FUNCTION that proposes, never acts.

    Returns a plain dict so it can be JSON-snapshotted into
    ``ReturnAuthorization.policy_snapshot`` verbatim::

        {
          "within_window":       bool,
          "basis_date_used":     "YYYY-MM-DD" or "",
          "basis_used":          "delivery" | "fulfilment" | "order_date" | "fallback" | "none",
          "deadline":            "YYYY-MM-DD" or "",
          "days_remaining":      int,
          "allowed_resolutions": [str, …],
          "proposed_fee":        "0.00",
          "proposed_credit":     "0.00",   # gross, before the fee
          "proposed_net":        "0.00",   # credit − fee, which is what a credit note would total
          "blockers":            [str, …],
          "policy":              "policy name" or "",
          "reason":              "reason code" or "",
        }

    **``basis_date_used`` is returned and DISPLAYED, not just used.** ``window_basis="delivery"``
    falls through to ``fallback_days`` far more often than the policy UI implies:
    ``SalesOrder.delivered_notification_at`` is a manual human stamp (``salesorder_fulfill``'s own
    docstring says it "records a human's statement"), so on most orders it is simply null. A CSR
    staring at "outside the window" has to be able to see WHICH date the clock ran from.

    Everything is stringified because this dict is stored as text and re-read months later, where a
    ``Decimal`` or a ``date`` would not survive the round trip.
    """
    as_of = as_of or timezone.localdate()
    blockers = []

    if policy is None:
        return {
            "within_window": False, "basis_date_used": "", "basis_used": "none", "deadline": "",
            "days_remaining": 0, "allowed_resolutions": [], "proposed_fee": str(ZERO),
            "proposed_credit": str(ZERO), "proposed_net": str(ZERO),
            "blockers": ["No return policy is configured for this workspace — create one first."],
            "policy": "", "reason": getattr(reason, "code", "") or "",
        }
    if not policy.is_active:
        blockers.append(f"Return policy '{policy.name}' is inactive.")
    if reason is not None and not reason.is_active:
        blockers.append(f"Return reason '{reason.code}' is inactive.")

    # --- which date does the clock run from? ---------------------------------------------------
    basis_date, basis_used = None, "none"
    if sales_order is not None:
        delivered = getattr(sales_order, "delivered_notification_at", None)
        shipped = getattr(sales_order, "shipped_notification_at", None)
        if policy.window_basis == "delivery" and delivered:
            basis_date, basis_used = timezone.localtime(delivered).date(), "delivery"
        elif policy.window_basis == "fulfilment" and shipped:
            basis_date, basis_used = timezone.localtime(shipped).date(), "fulfilment"
        elif policy.window_basis == "order_date" and sales_order.order_date:
            basis_date, basis_used = sales_order.order_date, "order_date"
        elif sales_order.order_date:
            # The basis event never happened. Loop's answer: measure from the order date over the
            # longer fallback window rather than refuse a customer for our own missing stamp.
            basis_date, basis_used = sales_order.order_date, "fallback"

        if policy.require_delivery_confirmation and not delivered:
            blockers.append("This policy requires a confirmed delivery and the order has none — "
                            "record the delivery on the sales order first.")
        if sales_order.status == "cancelled":
            blockers.append(f"Sales order {sales_order.number} was cancelled — there is nothing "
                            "to return against it.")

    window = policy.fallback_days if basis_used == "fallback" else policy.window_days
    deadline = basis_date + datetime.timedelta(days=window) if basis_date else None
    within_window = bool(deadline and as_of <= deadline)
    days_remaining = (deadline - as_of).days if deadline else 0

    if basis_date is None:
        # A blind return (no sales order at all) is legitimate — a CSR raising a goodwill RMA has
        # nothing to date it from. It is NOT auto-eligible, though: it needs a human to look.
        blockers.append("No order date is available, so the return window cannot be measured — "
                        "approve this on judgement, not on the policy.")
    elif not within_window:
        blockers.append(
            f"Outside the {window}-day window: the clock ran from {basis_date:%d %b %Y} "
            f"({basis_used}) and closed on {deadline:%d %b %Y}.")

    # --- what may be offered -------------------------------------------------------------------
    allowed = set(policy.allowed_resolutions)
    if reason is not None:
        # The reason NARROWS the policy — never widens it. "Changed my mind" cannot unlock a repair
        # the policy does not offer, and a policy that forbids exchanges is not overruled by a
        # reason that allows them.
        allowed &= set(reason.allowed_resolutions) | {"keep_item"}
    if not allowed:
        blockers.append("The policy and the reason between them allow no outcome at all.")

    # --- the money -----------------------------------------------------------------------------
    gross = policy.refund_for(line_value)
    fee = ZERO if (reason is not None and reason.waives_return_fee) else policy.fee_for(line_value)

    return {
        "within_window": within_window,
        "basis_date_used": basis_date.isoformat() if basis_date else "",
        "basis_used": basis_used,
        "deadline": deadline.isoformat() if deadline else "",
        "days_remaining": days_remaining,
        "allowed_resolutions": sorted(allowed),
        "proposed_fee": str(fee),
        "proposed_credit": str(gross),
        "proposed_net": str(q2(gross - fee)),
        "blockers": blockers,
        "policy": policy.name,
        "reason": getattr(reason, "code", "") or "",
    }
