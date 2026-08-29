"""Procurement 6.12 Goods Receipt & Inspection — ReceiptTolerancePolicy + its resolver.

**Receipt Tolerances** bullet: the standing configuration that says how much MORE (or less, or
earlier, or later) than the purchase order a delivery may be before the receiving desk should
argue about it. Every serious P2P suite carries this table — SAP calls it the over/under-delivery
tolerance on the info record, Coupa and Ariba call it a receipt tolerance — and it is what turns
"the driver brought 105 of the 100 we ordered" from a judgement call into a policy answer.

**This policy is ADVISORY, deliberately and permanently.** It colours the receiving console, it
populates the tolerance-exceptions board, and it pre-fills a discrepancy claim. It NEVER blocks
``scm:goodsreceipt_receive`` — booking stock is SCM's verb and SCM keeps it (L36), so a second
gate here would give the workspace two answers to "can this be received?". ``action="block_flag"``
therefore FLAGS a line as blocking-severity; it does not stop the receipt. ``price_variance_pct``
is likewise an advisory mirror of the hardcoded ``GoodsReceiptNote.PRICE_TOLERANCE_PCT`` (2%);
wiring it into ``recompute_match()`` would be an SCM write and is parked for 6.13.

**No number, no status.** This is a configuration master in the shape inventory 5.15's
``QcRoutingRule`` and 6.3's ``ApprovalRoutingRule`` already proved — ``TenantOwned``, not
``TenantNumbered``, because nobody quotes a tolerance rule by reference in a conversation with a
supplier. And there is **no unique_together**: overlapping rules are LEGAL. The resolver below
decides which one wins, exactly as ``resolve_qc_routing`` does, so a uniqueness constraint would
only brick legitimate configurations (a workspace-wide 2% rule PLUS a 10% exception for one
vendor is the normal case, not a mistake).

Zero stock effect, zero ledger effect: a tolerance is advice about a movement, never a movement.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


def _trim(value):
    """A Decimal as the shortest exact text: ``105.00`` -> ``105``, ``2.50`` -> ``2.5``.

    Band labels are read by a buyer, not parsed by anything, and a DB-loaded ``Decimal("5.00")``
    printing as "5.00% (max 105.00 on 100)" reads like precision that isn't there.
    """
    value = Decimal(value)
    if not value.is_finite():
        # NaN/Infinity have a STRING exponent ('n'/'F'), so the comparison below would raise
        # TypeError. Nothing here should ever produce one — hand it back untouched rather than
        # 500 a page over a display helper.
        return value
    normalized = value.normalize()
    # normalize() renders large integers in exponent form (1E+2); quantize back for those.
    return normalized if normalized.as_tuple().exponent <= 0 else normalized.quantize(Decimal("1"))


def _days(count):
    return f"{count} day" if count == 1 else f"{count} days"


class ReceiptTolerancePolicy(TenantOwned):
    """One standing over/under/early/late receipt tolerance band."""

    ACTION_CHOICES = [
        ("none", "No Action"),
        ("warn", "Warn"),
        ("block_flag", "Flag as Blocking"),
    ]
    #: Scope vocabulary for the ``?scope=`` filter widget. NOT a column — scope is derived from
    #: which of ``item`` / ``category`` is populated, so it can never drift out of step with them.
    SCOPE_CHOICES = [
        ("item", "Item"),
        ("category", "Category"),
        ("catchall", "Catch-all"),
    ]
    #: Verdict vocabulary returned by :func:`evaluate_receipt_tolerance` and rendered as a badge on
    #: the console, the exceptions board and this policy's own detail page.
    VERDICT_CHOICES = [
        ("ok", "Within tolerance"),
        ("over", "Over-receipt"),
        ("short", "Under-receipt"),
        ("early", "Early"),
        ("late", "Late"),
        ("no_rule", "No policy"),
    ]

    #: Badge class per verdict. Colour-NAMED theme classes only (L33) — a semantic
    #: ``badge-success``/``badge-danger`` renders completely unstyled in this theme.
    VERDICT_CSS = {
        "ok": "badge-green",
        "over": "badge-amber",
        "short": "badge-amber",
        "early": "badge-info",
        "late": "badge-red",
        "no_rule": "badge-muted",
    }

    name = models.CharField(
        max_length=100,
        help_text="e.g. 'ACME 5% over-receipt', 'Spares strict'")
    item = models.ForeignKey(
        "scm.Item", on_delete=models.CASCADE, null=True, blank=True,
        related_name="procurement_receipt_tolerances",
        help_text="Specific product (blank for a category or workspace-wide rule)")
    category = models.ForeignKey(
        "scm.ItemCategory", on_delete=models.CASCADE, null=True, blank=True,
        related_name="procurement_receipt_tolerances",
        help_text="Item category this rule applies to (blank if item-pinned or workspace-wide)")
    vendor = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_receipt_tolerances",
        help_text="Only receipts from this supplier match; blank = any vendor")
    over_receipt_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Percent of the ordered quantity that may be over-delivered")
    under_receipt_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))],
        help_text="Percent short a delivery may fall and still close the line")
    over_receipt_qty = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Absolute alternative to the percentage — when BOTH are set the MORE "
                  "RESTRICTIVE wins")
    allow_unlimited_over_receipt = models.BooleanField(
        default=False,
        help_text="SAP escape flag — when on, over_receipt_pct and over_receipt_qty are IGNORED")
    early_receipt_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Days a receipt may arrive BEFORE the expected date")
    late_receipt_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Days a receipt may arrive AFTER the expected date")
    action = models.CharField(
        max_length=11, choices=ACTION_CHOICES, default="warn",
        help_text="block_flag FLAGS the line — it never blocks scm:goodsreceipt_receive")
    price_variance_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Advisory mirror of GoodsReceiptNote.PRICE_TOLERANCE_PCT (2%). Wiring it into "
                  "recompute_match() is an SCM write, parked for 6.13.")
    priority = models.PositiveIntegerField(default=10, help_text="Tie-breaker — lower numbers win")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["priority", "id"]
        indexes = [
            # Covers the resolver's hot query (tenant + is_active, ordered by priority) and the
            # list page's default ORDER BY.
            models.Index(fields=["tenant", "is_active", "priority"],
                         name="prc_rtp_tnt_act_pri_idx"),
            models.Index(fields=["tenant", "action"], name="prc_rtp_tnt_action_idx"),
        ]
        verbose_name = "Receipt Tolerance Policy"
        verbose_name_plural = "Receipt Tolerance Policies"

    def __str__(self):
        return f"{self.name} ({self.get_action_display()})"

    def clean(self):
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        errors = {}
        # Both scopes at once is ambiguous: the resolver would score it as an item rule and the
        # category would silently never apply. Refuse it where the user can see it, keyed on the
        # SECOND field so the message lands next to the one to clear (QcRoutingRule.clean() shape).
        if self.item_id and self.category_id:
            errors["category"] = "Pin the rule to an item OR a category, not both."
        if tenant_id:
            if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
                errors["item"] = "That item belongs to another workspace."
            if self.category_id and getattr(self.category, "tenant_id", None) != tenant_id:
                errors["category"] = "That category belongs to another workspace."
            if self.vendor_id and getattr(self.vendor, "tenant_id", None) != tenant_id:
                errors["vendor"] = "That vendor belongs to another workspace."
        # A rule that declares no band at all judges nothing: it would win the resolution race
        # against a real rule and then always answer "ok". The unlimited escape flag IS a band
        # (it says "never flag an over-receipt"), so it satisfies the requirement on its own.
        if not self.allow_unlimited_over_receipt and not any([
            self.over_receipt_pct is not None,
            self.over_receipt_qty is not None,
            self.under_receipt_pct is not None,
            self.early_receipt_days is not None,
            self.late_receipt_days is not None,
        ]):
            errors["over_receipt_pct"] = (
                "Give this rule at least one band (quantity or date), or tick "
                "'allow unlimited over receipt'.")
        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------ derived, never stored
    @property
    def scope_key(self):
        """``item`` / ``category`` / ``catchall`` — derived from the FKs, never a column."""
        if self.item_id:
            return "item"
        return "category" if self.category_id else "catchall"

    @property
    def scope_label(self):
        return {"item": "Item", "category": "Category"}.get(self.scope_key, "Catch-all")

    @property
    def specificity_tier(self):
        """3 = item, 2 = category, 1 = catch-all. The same tiers the resolver scores on."""
        return {"item": 3, "category": 2}.get(self.scope_key, 1)

    @property
    def over_band_text(self):
        if self.allow_unlimited_over_receipt:
            return "Unlimited"
        parts = []
        if self.over_receipt_pct is not None:
            ceiling = _trim(Decimal("100") + self.over_receipt_pct)
            parts.append(f"{_trim(self.over_receipt_pct)}% (max {ceiling} on 100)")
        if self.over_receipt_qty is not None:
            parts.append(f"{_trim(self.over_receipt_qty)} units")
        return " / ".join(parts) if parts else "—"

    @property
    def under_band_text(self):
        if self.under_receipt_pct is None:
            return "—"
        floor = _trim(Decimal("100") - self.under_receipt_pct)
        return f"{_trim(self.under_receipt_pct)}% (min {floor} on 100)"

    @property
    def date_band_text(self):
        parts = []
        if self.early_receipt_days is not None:
            parts.append(f"{_days(self.early_receipt_days)} early")
        if self.late_receipt_days is not None:
            parts.append(f"{_days(self.late_receipt_days)} late")
        return " / ".join(parts) if parts else "—"

    def worked_example(self, ordered=Decimal("100")):
        """This rule's bands applied to a 100-unit order, for the detail page.

        Derived at read time from the columns — nothing here is stored. ``max_accept`` and
        ``min_accept`` are ``None`` when the rule places no ceiling / no floor, which is what lets
        the page say "unlimited" or "not judged" instead of printing a misleading number.
        """
        ordered = Decimal(ordered)
        if self.allow_unlimited_over_receipt:
            max_accept = None
        else:
            allowances = []
            if self.over_receipt_pct is not None:
                allowances.append(ordered * self.over_receipt_pct / Decimal("100"))
            if self.over_receipt_qty is not None:
                allowances.append(Decimal(self.over_receipt_qty))
            # Both set -> the MORE RESTRICTIVE wins. Neither -> zero tolerance, ceiling == ordered.
            max_accept = _trim(ordered + (min(allowances) if allowances else ZERO))
        return {
            "ordered": _trim(ordered),
            "max_accept": max_accept,
            "min_accept": (_trim(ordered - ordered * self.under_receipt_pct / Decimal("100"))
                           if self.under_receipt_pct is not None else None),
            "over_text": self.over_band_text,
            "under_text": self.under_band_text,
            "date_text": self.date_band_text,
            "unlimited": self.allow_unlimited_over_receipt,
        }

    @property
    def action_css(self):
        return {"none": "badge-muted", "warn": "badge-amber",
                "block_flag": "badge-red"}.get(self.action, "badge-muted")

    @property
    def scope_css(self):
        return {"item": "badge-info", "category": "badge-slate"}.get(self.scope_key, "badge-muted")


def resolve_receipt_tolerance(item=None, vendor=None, *, tenant=None, category=None, rules=None):
    """Resolve which tolerance policy governs one receipt line.

    Structural clone of ``inventory.resolve_qc_routing`` — same hierarchy, same tie-breaks, same
    "No Rule Matched" refusal vocabulary — with ONE deliberate difference: ``item`` may be
    ``None``. GRN and PO lines in this codebase are FREE TEXT (no item FK, verified), so a line
    whose ``sku_hint`` resolves to nothing must still be judged by a category or catch-all rule.
    That is why ``tenant`` is an explicit keyword: without an item there is no other way to know
    whose rules to read.

    Hierarchy: specificity tier DESC (item=3 > category=2 > catch-all=1) → vendor-specific beats
    vendor-agnostic → priority ASC → id ASC. A rule pinned to vendor V matches ONLY when
    ``vendor`` is that party — a vendor rule must never fire blind on an unknown supplier.

    ``rules`` is the caller's pre-fetched list (the console and the exceptions board fetch it once
    and pass it for every line rather than issuing a query per row). It is trusted for ORDER,
    never for TENANCY: it is re-filtered by tenant here.

    Returns ``(rule|None, reason:str)``.
    """
    effective_tenant = tenant if tenant is not None else getattr(item, "tenant", None)
    tenant_pk = getattr(effective_tenant, "pk", effective_tenant)
    vendor_id = getattr(vendor, "pk", vendor)

    # No tenant context = no way to prove any rule belongs to this workspace. Refuse BEFORE
    # looking at a caller-supplied list: trusting it here is exactly how one workspace's policy
    # would end up judging another's receipt.
    if tenant_pk is None:
        return None, "No Rule Matched — no tenant context available."

    if rules is None:
        rules = list(
            ReceiptTolerancePolicy.objects.filter(tenant_id=tenant_pk, is_active=True)
            .select_related("item", "category", "vendor")
            .order_by("priority", "id")
        )
    else:
        # A caller-supplied list is trusted for ORDER, never for TENANCY.
        rules = [r for r in rules if r.tenant_id == tenant_pk]

    item_id = getattr(item, "pk", item)
    cat_id = getattr(category, "pk", getattr(item, "category_id", None))

    scored = []
    for rule in rules:
        if not rule.is_active:
            continue
        if rule.vendor_id and rule.vendor_id != vendor_id:
            continue  # a vendor-pinned rule never fires for other/unknown suppliers
        if rule.item_id:
            if not item_id or rule.item_id != item_id:
                continue
            tier = 3
        elif rule.category_id:
            if not cat_id or rule.category_id != cat_id:
                continue
            tier = 2
        else:
            tier = 1
        vendor_specificity = 2 if rule.vendor_id else 1
        scored.append((tier, vendor_specificity, rule.priority, rule.id, rule))

    if not scored:
        return None, "No Rule Matched — no active tolerance policy covers this line."

    scored.sort(key=lambda x: (-x[0], -x[1], x[2], x[3]))
    best = scored[0][4]
    pin = ", vendor-pinned" if best.vendor_id else ""
    return best, (f"Matched {best.scope_label.lower()} rule '{best.name}' "
                  f"(priority {best.priority}){pin}")


def evaluate_receipt_tolerance(rule, *, ordered_quantity, received_quantity,
                               expected_date=None, receipt_date=None):
    """Judge ONE line against an already-resolved policy.

    Split from :func:`resolve_receipt_tolerance` on purpose: selection and judgement are
    independently testable, and the exceptions board needs a verdict for lines whose governing
    rule it has already resolved (it resolves once per line, then judges the same line against
    four buckets without re-running the hierarchy).

    Quantity breaches outrank date breaches — a short shipment that also arrived late is reported
    as short, because that is the one somebody has to chase the supplier about.

    Returns ``(verdict, reason)`` with verdict in ``ok|over|short|early|late|no_rule``.
    """
    if rule is None:
        return "no_rule", "No policy covers this line."

    ordered = Decimal(ordered_quantity or ZERO)
    received = Decimal(received_quantity or ZERO)

    if received > ordered:
        if rule.allow_unlimited_over_receipt:
            pass  # the SAP escape flag: over-receipt is never a breach for this rule
        else:
            allowances = []
            if rule.over_receipt_pct is not None:
                allowances.append(ordered * rule.over_receipt_pct / Decimal("100"))
            if rule.over_receipt_qty is not None:
                allowances.append(Decimal(rule.over_receipt_qty))
            # BOTH set -> the MORE RESTRICTIVE (smaller) allowance wins. NEITHER set -> zero
            # tolerance, so any over-delivery breaches.
            allowance = min(allowances) if allowances else ZERO
            ceiling = ordered + allowance
            if received > ceiling:
                return "over", (f"Received {_trim(received)} against {_trim(ordered)} ordered — "
                                f"over the {_trim(ceiling)} ceiling allowed by '{rule.name}'.")
    elif received < ordered and rule.under_receipt_pct is not None:
        floor = ordered - (ordered * rule.under_receipt_pct / Decimal("100"))
        if received < floor:
            return "short", (f"Received {_trim(received)} against {_trim(ordered)} ordered — "
                             f"below the {_trim(floor)} floor allowed by '{rule.name}'.")

    if expected_date and receipt_date:
        drift = (receipt_date - expected_date).days
        if drift < 0 and rule.early_receipt_days is not None and -drift > rule.early_receipt_days:
            return "early", (f"Arrived {_days(-drift)} early — '{rule.name}' allows "
                             f"{_days(rule.early_receipt_days)}.")
        if drift > 0 and rule.late_receipt_days is not None and drift > rule.late_receipt_days:
            return "late", (f"Arrived {_days(drift)} late — '{rule.name}' allows "
                            f"{_days(rule.late_receipt_days)}.")

    return "ok", f"Within the bands set by '{rule.name}'."


def resolve_line_item(tenant, po_line):
    """Best-effort ``scm.Item`` behind a free-text PO line, or ``None``.

    ``scm.PurchaseOrderLine`` and ``scm.GoodsReceiptLine`` carry NO item FK — they carry
    ``sku_hint`` free text (verified: PurchaseOrders.py:174-176) — so every item-level feature in
    6.12 has to go through this hint. A LOCAL MIRROR of ``apps/scm/views/_helpers.py``'s private
    ``_resolve_grn_item``: peer apps don't import each other's internals, and a missing match is
    reported, never raised (the ``_post_grn_receipt`` posture).
    """
    from apps.scm.models import Item

    if tenant is None or po_line is None:
        return None
    sku = (getattr(po_line, "sku_hint", "") or "").strip()
    if not sku:
        return None
    return Item.objects.filter(tenant=tenant, sku__iexact=sku).first()
