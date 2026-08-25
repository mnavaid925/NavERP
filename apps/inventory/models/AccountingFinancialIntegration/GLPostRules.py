"""Inventory 5.18 Accounting & Financial Integration — GLPostRule.

**Journal Entry Automation** bullet: "Automatically posting inventory adjustments,
cost of goods sold (COGS), and valuation changes." The ledger itself is Module 2's —
``accounting.JournalEntry``/``JournalLine`` (L29: never a parallel one). What the
automation needs before it may touch that ledger is an ACCOUNT MAP: which asset
account carries stock value and which expense/revenue account offsets each event
type. This table is that map — exactly one active mapping per event type per tenant
(``unique_together``), because two mappings for the same event would make every run
ambiguous.

Event semantics (the posting service reads them, the admin page documents them):

* ``adjustment`` — a posted ``scm.StockAdjustment``. Value up → DR inventory /
  CR offset (found-stock gain); value down → DR offset / CR inventory (write-off).
* ``cogs`` — outbound customer ``issue`` moves over a date window. DR offset (the
  COGS expense) / CR inventory, at the unit cost each move was stamped with when
  it left stock.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class GLPostRule(TenantOwned):
    """The account pair one inventory event type posts through."""

    EVENT_TYPES = [
        ("adjustment", "Inventory Adjustment"),
        ("cogs", "Cost of Goods Sold"),
    ]

    event_type = models.CharField(
        max_length=12, choices=EVENT_TYPES,
        help_text="One mapping per event type — a second would make runs ambiguous")
    name = models.CharField(max_length=64)
    inventory_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.PROTECT, related_name="gl_post_rules_as_inventory",
        help_text="The stock asset account (e.g. 1500 Inventory)")
    offset_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.PROTECT, related_name="gl_post_rules_as_offset",
        help_text=("Adjustments: the gain/write-off account · COGS: the COGS expense "
                   "(e.g. 5000 Cost of Goods Sold)"))
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["event_type"]
        unique_together = ("tenant", "event_type")
        indexes = [models.Index(fields=["tenant", "is_active"], name="inv_gpr_tnt_active_idx")]

    @property
    def event_type_label(self):
        return dict(self.EVENT_TYPES).get(self.event_type, self.event_type)

    @property
    def offset_role(self):
        """What the offset account means for this event type — shown on detail/list."""
        return ("Found-stock gain / write-off account" if self.event_type == "adjustment"
                else "COGS expense account")

    def clean(self):
        super().clean()
        errors = {}
        if self.inventory_account_id and self.inventory_account.tenant_id != self.tenant_id:
            errors["inventory_account"] = "That account belongs to another workspace."
        if self.offset_account_id and self.offset_account.tenant_id != self.tenant_id:
            errors["offset_account"] = "That account belongs to another workspace."
        if (self.inventory_account_id and self.offset_account_id
                and self.inventory_account_id == self.offset_account_id):
            errors["offset_account"] = "The offset account must differ from the inventory account."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} ({self.get_event_type_display()})"
