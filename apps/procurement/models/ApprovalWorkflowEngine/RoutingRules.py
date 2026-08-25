"""Procurement 6.3 Approval Workflow Engine — Dynamic Routing Rules.

**Dynamic Routing Rules** bullet: "Conditional logic that routes approvals based on
amount, department, or commodity." The requisition DOCUMENT and its status machine
stay SCM 4.1's (``scm.PurchaseRequisition``, whose own single-step approve remains);
this layer decides HOW MANY sign-offs a pending requisition needs before the final
one flips the spine — mirroring how inventory 5.3 wraps purchase orders.

Three match dimensions, all optional, overlapping rules LEGAL (no unique_together):
a ``core.OrgUnit`` pin (the department dimension), a ``commodity`` keyword matched
case-insensitively against the lines' free-text ``sku_hint``/``item_description``
(the L28 stand-in — requisition lines carry no item FK to join), and a HALF-OPEN
amount band ``min_total <= estimated_total < max_total`` so adjacent bands never
both fire (the 5.3 precedent). The deterministic resolver picks specificity DESC,
then the narrowest band, then lowest id; NO matching rule means ONE tier, never
zero — an ungoverned requisition still needs its single sign-off.
"""
from decimal import Decimal

from apps.procurement.models._base import *  # noqa: F401,F403

#: Band edges for open ends — ordering sentinels, never stored. The ceiling mirrors
#: what a DecimalField(18, 2) can hold so even the largest legal requisition falls
#: INSIDE an open-ended band rather than silently outside every one.
_BAND_FLOOR = Decimal("-1")
_BAND_CEILING = Decimal("99999999999999.98")


class ApprovalRoutingRule(TenantOwned):
    """One routing instruction: spend like THIS needs N sequential sign-offs.

    Plain configuration — deliberately NO numbering (the PutawayRule ruling): the
    row is read by the resolver, never referenced by other documents.
    """

    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_routing_rules",
        help_text="Department this rule routes; blank = any department")
    commodity = models.CharField(
        max_length=64, blank=True,
        help_text="Keyword matched against line descriptions/SKUs (e.g. 'safety'); blank = any commodity")
    min_total = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Band floor (inclusive); blank = no lower bound")
    max_total = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Band ceiling (EXCLUSIVE); blank = no upper bound")
    required_tiers = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Sequential sign-offs this spend needs before final approval")
    escalation_hours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Idle hours after which this rule's queue escalates; blank = the tenant policy's window")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="prc_arr_tnt_active_idx"),
        ]

    def __str__(self):
        scope = []
        if self.org_unit_id:
            scope.append(self.org_unit.name)
        if self.commodity:
            scope.append(self.commodity)
        return f"{'+'.join(scope) or 'Any'} · {_band_label(self)} → {self.required_tiers} tier(s)"

    # -- resolution helpers -----------------------------------------------------------------------

    @property
    def specificity(self):
        """How narrowly this rule targets: a department pin beats a commodity keyword
        beats the catch-all band (mirrors 5.3's org-scoped-beats-unscoped ranking)."""
        score = 0
        if self.org_unit_id:
            score += 2
        if self.commodity:
            score += 1
        return score

    @property
    def band_width(self):
        lo = self.min_total if self.min_total is not None else _BAND_FLOOR
        hi = self.max_total if self.max_total is not None else _BAND_CEILING
        return hi - lo

    @property
    def band_label(self):
        """Human reading of the band, e.g. ``[1,000 – 10,000)`` or ``[any – open)``."""
        return _band_label(self)

    def matches_commodity(self, requisition, lines=None):
        """True when the rule names no commodity, or any line's free text carries it.

        Case-insensitive substring over ``sku_hint`` AND ``item_description`` — the
        honest reach of an L28 text stand-in, never pretended into a real join.
        Pass ``lines`` (the requisition's already-fetched line rows) so a page-level
        resolver never pays one query per candidate rule.
        """
        if not self.commodity:
            return True
        keyword = self.commodity.strip().lower()
        if not keyword:
            return True
        if lines is None:
            lines = list(requisition.lines.all())
        for line in lines:
            haystacks = (line.sku_hint or "", line.item_description or "")
            if any(keyword in h.lower() for h in haystacks):
                return True
        return False

    def clean(self):
        super().clean()
        errors = {}
        if (self.min_total is not None and self.max_total is not None
                and self.max_total <= self.min_total):
            errors["max_total"] = "Ceiling must exceed the floor."
        if self.commodity:
            self.commodity = self.commodity.strip().lower()
        if self.org_unit_id and self.org_unit.tenant_id != self.tenant_id:
            errors["org_unit"] = "That record belongs to another workspace."
        if errors:
            raise ValidationError(errors)


def _band_label(rule):
    lo = f"{rule.min_total:,.0f}" if rule.min_total is not None else "any"
    hi = f"{rule.max_total:,.0f}" if rule.max_total is not None else "open"
    return f"[{lo} – {hi})"


def resolve_routing(requisition, *, rules=None, lines_by_req=None):
    """The ONE rule governing this requisition — ``(rule | None, reason)``.

    Deterministic ladder: specificity DESC → narrowest band → lowest id. ``None``
    is a legitimate answer meaning ONE default tier (never zero) and the reason says
    exactly that. Pass ``rules`` (and ``lines_by_req``, a ``{requisition_pk: [rows]}``
    index) to reuse batch-preloaded state so a whole page resolves flat.
    """
    total = requisition.estimated_total or ZERO
    if rules is None:
        rules = ApprovalRoutingRule.objects.filter(
            tenant_id=requisition.tenant_id, is_active=True)
    lines = None
    if lines_by_req is not None:
        lines = lines_by_req.get(requisition.pk)
    candidates = []
    for rule in rules:
        lo = rule.min_total if rule.min_total is not None else _BAND_FLOOR
        hi = rule.max_total if rule.max_total is not None else _BAND_CEILING
        if not (lo <= total < hi):
            continue
        if rule.org_unit_id and rule.org_unit_id != requisition.org_unit_id:
            continue
        if not rule.matches_commodity(requisition, lines=lines):
            continue
        candidates.append(rule)
    if not candidates:
        return None, ("No routing rule matched — default chain of one approval applies.")
    best = sorted(candidates, key=lambda r: (-r.specificity, r.band_width, r.id))[0]
    bits = [f"'{best}' fires"]
    beaten = len(candidates) - 1
    if beaten:
        bits.append(f"(narrower/more specific than {beaten} other candidate(s))")
    return best, " ".join(bits)
