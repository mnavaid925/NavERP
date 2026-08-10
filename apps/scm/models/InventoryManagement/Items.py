"""SCM 4.3 Inventory Management — the item master spine: ItemCategory + UOM + Item.

**Ownership (L29/L36):** SCM 4.3 is the first sub-module to need an inventory spine, so it OWNS these
masters in `apps/scm` — exactly as `apps/accounting` owns the ledger (Currency/GLAccount/JournalEntry)
it shipped first. Later modules (5 Inventory, 8 Sales, 9 eCommerce, 11 Assets, 12 Quality) FK into
`scm.Item`/`scm.Location`/`scm.StockMove` **by string** and EXTEND — they do not re-declare these.
NavERP-ERD.md line 467 (which nominally assigns them to Module 5) is reconciled to reflect this.

**Derived, never stored:** an item's on-hand quantity and its stock value are ALWAYS aggregates over
the append-only `StockMove` ledger — there is no editable quantity field anywhere. `average_cost` is a
cached weighted-average maintained by `apply_receipt()` for fast valuation display, not a source of
truth for quantity.
"""
from apps.scm.models._base import *  # noqa: F401,F403
# BY NAME, never `import *`. `_choices.py` at the models package ROOT imports nothing at all (not
# even `_base`), so the partially-initialised `apps.scm.models` package sitting in `sys.modules`
# while this file is being imported is never asked for a name it has not bound yet. The vocabulary
# lives at the root rather than inside 4.15's folder precisely so this line does not make an older
# sub-module reach into a newer one — see `apps/scm/models/_choices.py`. If this ever does turn
# circular, the fix is to MOVE the constant, never to duplicate the list.
from apps.scm.models._choices import STORAGE_CONDITION_CHOICES


class ItemCategory(TenantOwned):
    """A hierarchical grouping of items (e.g. Electronics › Laptops)."""

    name = models.CharField(max_length=120)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="children")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["tenant", "is_active"], name="scm_itemcat_tnt_active_idx")]

    def __str__(self):
        return self.name


class UOM(TenantOwned):
    """Unit of measure. ``factor`` is the ratio to the item's base unit (1 for a base unit), so a
    'box of 12' is factor=12 against 'each' — enough for simple pack/base conversions without a full
    N:N conversion matrix (deferred)."""

    code = models.CharField(max_length=16)
    name = models.CharField(max_length=60)
    factor = models.DecimalField(max_digits=14, decimal_places=4, default=1,
                                 validators=[MinValueValidator(Decimal("0.0001"))],
                                 help_text="Units of the base UOM per one of this UOM")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        verbose_name = "UOM"
        verbose_name_plural = "UOMs"

    def __str__(self):
        return self.code


class Item(TenantOwned):
    """A stock-keeping item master. On-hand + value are DERIVED from StockMove (see below)."""

    ITEM_TYPES = [
        ("stock", "Stock"),          # tracked in inventory
        ("consumable", "Consumable"),
        ("service", "Service"),      # not stocked
    ]
    TRACKING_CHOICES = [
        ("none", "None"),
        ("lot", "Lot / Batch"),
        ("serial", "Serial"),
    ]
    COSTING_CHOICES = [
        ("weighted_avg", "Weighted Average"),
        ("fifo", "FIFO"),
        ("lifo", "LIFO"),
    ]

    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    category = models.ForeignKey("scm.ItemCategory", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="items")
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="items")
    item_type = models.CharField(max_length=12, choices=ITEM_TYPES, default="stock")
    tracking = models.CharField(max_length=8, choices=TRACKING_CHOICES, default="none")
    costing_method = models.CharField(max_length=12, choices=COSTING_CHOICES, default="weighted_avg")
    standard_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                        validators=[MinValueValidator(ZERO)])
    # Cached weighted-average unit cost for fast valuation display. Maintained by apply_receipt();
    # NOT the source of truth for quantity (that is always the StockMove aggregate).
    average_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    reorder_point = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                        validators=[MinValueValidator(ZERO)],
                                        help_text="Item-wide default; a ReorderRule can override per location")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    # 4.13 Asset Management. A one-column marker, NOT a SparePart table: UoM, category, costing
    # method, average cost, reorder point and the derived on-hand all already live here, and a
    # parallel parts master would fork every one of them and then need reconciling with the very
    # stock ledger a maintenance issue posts into (L29). An MRO part is an Item that happens to be
    # fitted to a machine. Additive and all-default — the 4.4 precedent that added the bin
    # attributes to Location — so no existing row changes meaning and nothing needs backfilling.
    is_spare_part = models.BooleanField(
        default=False,
        help_text="MRO part held for maintenance; shown on the spare-parts storeroom page")
    # 4.15 Cold Chain Management. One column on the EXISTING item master, exactly as `is_spare_part`
    # above and the 4.4 bin attributes on Location: a temperature class is an attribute of a product,
    # not a reason for a parallel "cold item" master that would fork the UoM, the costing method, the
    # reorder point and the derived on-hand. Together with the same column on Location it turns Cold
    # Storage Inventory from a table into a QUERY. Additive, all-default and blank-permitted — no
    # existing row changes meaning and nothing needs backfilling.
    #
    # A `StorageCondition` master carrying per-item numeric limits is what to add the day a bullet
    # needs one; none does. The numbers that decide in-range live on `ColdChainMonitor`, which is the
    # thing that actually measures.
    storage_condition = models.CharField(
        max_length=14, choices=STORAGE_CONDITION_CHOICES, blank=True,
        help_text="Temperature class this item must be kept at; blank = not temperature-controlled")

    class Meta:
        ordering = ["sku"]
        unique_together = ("tenant", "sku")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="scm_item_tnt_active_idx"),
            models.Index(fields=["tenant", "category"], name="scm_item_tnt_cat_idx"),
        ]

    @property
    def is_stocked(self):
        return self.item_type == "stock"

    def on_hand(self, location=None):
        """Current quantity — the SUM of every StockMove for this item (append-only ledger).

        Optionally scoped to one location. This is the ONLY source of truth for quantity; there is
        deliberately no stored on-hand field to drift from it.
        """
        qs = self.stock_moves.all()
        if location is not None:
            qs = qs.filter(location=location)
        return qs.aggregate(q=Sum("quantity"))["q"] or ZERO

    def total_value(self, on_hand=None):
        """On-hand × cached average cost — the quick valuation figure. The Stock Valuation report
        does the exact FIFO/LIFO/WAC cost-layer walk over StockMove for the authoritative number.

        Pass ``on_hand`` when the caller already resolved it, so the detail page doesn't pay for the
        same aggregate twice (perf review)."""
        qty = self.on_hand() if on_hand is None else on_hand
        return (qty * (self.average_cost or ZERO)).quantize(Decimal("0.01"))

    def apply_receipt(self, quantity, unit_cost):
        """Roll the cached weighted-average cost forward for an inbound quantity at ``unit_cost``.

        Weighted average is computed against the PRE-receipt on-hand, so callers must invoke this
        BEFORE the receiving StockMove is aggregated in (the posting helper does exactly that). A
        non-positive quantity is a no-op. Does not touch quantity — that lives in StockMove.
        """
        quantity = quantity or ZERO
        if quantity <= ZERO:
            return
        prior_qty = self.on_hand()
        prior_val = prior_qty * (self.average_cost or ZERO)
        new_qty = prior_qty + quantity
        if new_qty > ZERO:
            self.average_cost = ((prior_val + quantity * (unit_cost or ZERO)) / new_qty).quantize(
                Decimal("0.0001"))
            self.save(update_fields=["average_cost", "updated_at"])

    def __str__(self):
        return f"{self.sku} · {self.name}"
