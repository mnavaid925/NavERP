"""SCM 4.3 Inventory Management — ReorderRule.

A per-item, per-location reorder point + safety stock. The Reorder Alerts report lists rules whose
current on-hand has fallen to or below the reorder point and offers a one-click hand-off into 4.1's
`requisition_create` — the buyer still reviews and submits the requisition (no silent auto-PO). The
form is NOT pre-filled today; wiring the suggested quantity through is a documented follow-up.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class ReorderRule(TenantOwned):
    """Reorder point + safety stock for one item at one location."""

    item = models.ForeignKey("scm.Item", on_delete=models.CASCADE, related_name="reorder_rules")
    location = models.ForeignKey("scm.Location", on_delete=models.CASCADE, related_name="reorder_rules")
    reorder_point = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                        validators=[MinValueValidator(ZERO)],
                                        help_text="Reorder when on-hand falls to/below this")
    safety_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                       validators=[MinValueValidator(ZERO)])
    reorder_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                           validators=[MinValueValidator(ZERO)],
                                           help_text="Suggested quantity to reorder")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["item__sku"]
        unique_together = ("tenant", "item", "location")
        indexes = [models.Index(fields=["tenant", "is_active"], name="scm_reorder_tnt_active_idx")]

    @staticmethod
    def on_hand_map(tenant, rules):
        """``{(item_id, location_id): qty}`` for every rule in ONE grouped query.

        Each of current_on_hand/is_below_point/suggested_quantity otherwise costs its own aggregate,
        so a page that walks the rules pays 2-3 queries PER RULE (perf review). Views build this map
        once and hand the figure to the methods below.
        """
        from apps.scm.models import StockMove
        pairs = [(r.item_id, r.location_id) for r in rules]
        if not pairs:
            return {}
        rows = (StockMove.objects
                .filter(tenant=tenant,
                        item_id__in={i for i, _ in pairs},
                        location_id__in={l for _, l in pairs})
                .values("item_id", "location_id")
                .annotate(q=Sum("quantity")))
        return {(r["item_id"], r["location_id"]): (r["q"] or ZERO) for r in rows}

    def current_on_hand(self, on_hand=None):
        """Live on-hand for this rule's item at its location. Pass ``on_hand`` (from on_hand_map)
        to reuse an already-resolved figure instead of paying for another aggregate."""
        if on_hand is not None:
            return on_hand
        return self.item.on_hand(location=self.location)

    def is_below_point(self, on_hand=None):
        return self.current_on_hand(on_hand) <= self.reorder_point

    def suggested_quantity(self, on_hand=None):
        """How much to bring back up to the reorder point + safety stock (never negative)."""
        target = (self.reorder_point or ZERO) + (self.safety_stock or ZERO)
        gap = target - self.current_on_hand(on_hand)
        if self.reorder_quantity and self.reorder_quantity > ZERO:
            return max(self.reorder_quantity, gap) if gap > ZERO else ZERO
        return gap if gap > ZERO else ZERO

    def __str__(self):
        return f"Reorder {self.item_id and self.item.sku} @ {self.location_id and self.location.code}"
