"""SCM 4.3 Inventory Management — ReorderRule.

A per-item, per-location reorder point + safety stock. The Reorder Alerts report lists rules whose
current on-hand has fallen to or below the reorder point and offers a one-click pre-fill into 4.1's
`requisition_create` — the buyer still reviews and submits the requisition (no silent auto-PO).
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

    def current_on_hand(self):
        return self.item.on_hand(location=self.location)

    def is_below_point(self):
        return self.current_on_hand() <= self.reorder_point

    def suggested_quantity(self):
        """How much to bring back up to the reorder point + safety stock (never negative)."""
        target = (self.reorder_point or ZERO) + (self.safety_stock or ZERO)
        gap = target - self.current_on_hand()
        if self.reorder_quantity and self.reorder_quantity > ZERO:
            return max(self.reorder_quantity, gap) if gap > ZERO else ZERO
        return gap if gap > ZERO else ZERO

    def __str__(self):
        return f"Reorder {self.item_id and self.item.sku} @ {self.location_id and self.location.code}"
