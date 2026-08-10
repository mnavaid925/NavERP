"""SCM 4.3 Inventory Management — Location (warehouse / zone / bin hierarchy).

A light self-referential hierarchy so a bin can sit under a zone under a warehouse. 4.4 WMS layers
its bin/slotting operations on top of these; Module 5 reuses them. On-hand at a location is derived
from StockMove, never stored here.
"""
from apps.scm.models._base import *  # noqa: F401,F403
# BY NAME, never `import *` — see the identical import in `Items.py` and the docstring of
# `apps/scm/models/_choices.py` for why the vocabulary lives at the models package root instead of
# inside 4.15's folder.
from apps.scm.models._choices import STORAGE_CONDITION_CHOICES


class Location(TenantOwned):
    """A physical (or logical, e.g. in-transit) stock location."""

    LOCATION_TYPES = [
        ("warehouse", "Warehouse"),
        ("zone", "Zone"),
        ("bin", "Bin"),
        ("staging", "Staging"),
        ("transit", "In Transit"),
    ]

    ABC_CHOICES = [
        ("a", "A — fast moving"),
        ("b", "B — medium"),
        ("c", "C — slow moving"),
    ]

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    location_type = models.CharField(max_length=12, choices=LOCATION_TYPES, default="warehouse")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="children")
    is_active = models.BooleanField(default=True)

    # --- 4.4 WMS bin attributes -----------------------------------------------------------
    # Added to the EXISTING location rather than a parallel "Bin" model: a bin IS a location of
    # location_type='bin', and splitting them would fork the StockMove FK and the on-hand aggregate.
    capacity = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                   validators=[MinValueValidator(ZERO)],
                                   help_text="Storage capacity in the bin's own units (blank = unlimited)")
    pick_sequence = models.PositiveIntegerField(null=True, blank=True,
                                                help_text="Walk order for picking; lower is picked first")
    abc_class = models.CharField(max_length=1, choices=ABC_CHOICES, blank=True,
                                 help_text="Velocity class used for slotting and count frequency")
    is_pickable = models.BooleanField(default=True, help_text="Whether stock here can be picked from")

    # --- 4.15 cold-chain attribute ----------------------------------------------------------
    # Same precedent as the 4.4 block above, one sub-module on: a chiller zone IS a location of
    # location_type='zone', and splitting temperature-controlled storage into its own master would
    # fork the StockMove FK and the on-hand aggregate all over again. The user-defined temperature
    # zones every cold-storage WMS ships (Made4net, AEB, Datex, Logimax — chiller / deep freeze /
    # blast / ambient) are exactly this column. Additive, all-default and blank-permitted.
    #
    # It is a CLASSIFICATION, not a measurement: what a zone actually reached is a ColdChainMonitor
    # and its readings. A location claiming to be 'frozen' with no monitor on it is precisely the gap
    # the Cold Storage Inventory report exists to show.
    storage_condition = models.CharField(
        max_length=14, choices=STORAGE_CONDITION_CHOICES, blank=True,
        help_text="Temperature class of this zone or bin; blank = ambient / unclassified")

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
        """Sum of quantity×unit_cost currently at this location — the quick per-location valuation.

        One aggregate, not a Python walk: the ledger is the fastest-growing table in the module, so
        pulling every move at a location into memory to add it up would become a full scan on a page
        anyone can open (perf review).
        """
        value = self.stock_moves.aggregate(
            v=Sum(F("quantity") * F("unit_cost"),
                  output_field=models.DecimalField(max_digits=20, decimal_places=4)))["v"] or ZERO
        return value.quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.code} · {self.name}"
