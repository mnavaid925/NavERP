"""SCM 4.3 Inventory Management — Location (warehouse / zone / bin hierarchy).

A light self-referential hierarchy so a bin can sit under a zone under a warehouse. 4.4 WMS layers
its bin/slotting operations on top of these; Module 5 reuses them. On-hand at a location is derived
from StockMove, never stored here.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class Location(TenantOwned):
    """A physical (or logical, e.g. in-transit) stock location."""

    LOCATION_TYPES = [
        ("warehouse", "Warehouse"),
        ("zone", "Zone"),
        ("bin", "Bin"),
        ("staging", "Staging"),
        ("transit", "In Transit"),
    ]

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    location_type = models.CharField(max_length=12, choices=LOCATION_TYPES, default="warehouse")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="children")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        indexes = [models.Index(fields=["tenant", "location_type"], name="scm_loc_tnt_type_idx")]

    @property
    def is_leaf(self):
        return not self.children.exists()

    def path(self):
        """Human-readable ancestry, e.g. 'WH1 › ZONE-A › BIN-01'. Bounded to a few hops; guards a
        malformed self-parent cycle so a bad row can't hang the page."""
        parts, node, seen = [], self, set()
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            parts.append(node.code)
            node = node.parent
        return " › ".join(reversed(parts))

    def on_hand_value(self):
        """Sum of quantity×unit_cost currently at this location — the quick per-location valuation."""
        total = ZERO
        for move in self.stock_moves.all():
            total += (move.quantity or ZERO) * (move.unit_cost or ZERO)
        return total.quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.code} · {self.name}"
