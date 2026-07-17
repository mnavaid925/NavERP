"""SCM 4.2 Supplier Relationship Management — SupplierCatalog + SupplierCatalogItem models.

A supplier's standard price list. Items are FREE-TEXT (``item_name``/``sku``/``uom``) — ``core.Item``
does not exist yet (Module 5, lesson L28). When it lands, ``SupplierCatalogItem`` gains an optional
``item`` FK and these become the fallback; a buyer would then pull a catalog line straight onto a
requisition/PO line.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class SupplierCatalog(TenantNumbered):
    """A dated price list published by one supplier [CAT-]."""

    NUMBER_PREFIX = "CAT"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("archived", "Archived"),
    ]

    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="scm_catalogs")
    name = models.CharField(max_length=255)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_catalogs")
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-valid_from", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_cat_tnt_status_idx"),
        ]

    def item_count(self):
        return self.items.count()

    def __str__(self):
        return f"{self.number or 'CAT'} · {self.name}"


class SupplierCatalogItem(models.Model):
    """One priced line in a supplier catalog. Free-text until core.Item exists (L28)."""

    catalog = models.ForeignKey("scm.SupplierCatalog", on_delete=models.CASCADE, related_name="items")
    item_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True, help_text="Supplier's catalog code")
    uom = models.CharField(max_length=32, blank=True, help_text="Unit of measure")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                     validators=[MinValueValidator(ZERO)])
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    min_order_qty = models.DecimalField(max_digits=14, decimal_places=2, default=1,
                                        validators=[MinValueValidator(ZERO)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["item_name", "id"]

    def __str__(self):
        return f"{self.item_name} @ {self.unit_price}"
