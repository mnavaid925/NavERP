"""Procurement 6.9 Catalog Management — CatalogItem model.

**Catalog Item Creation / Management** bullet: ONE purchasable catalogue row per tenant,
either an ``internal`` mirror of a stock item (``scm.Item`` — the spine this app never
re-declares) or a ``supplier_product`` line from a supplier's paper catalogue. Price breaks
live on ``CatalogPriceTier`` rows under ``price_tiers`` (see Tiers.py); punch-out endpoints
and upload batches feed the same table from the outside.

Lifecycle: ``draft`` → ``pending_approval`` → ``approved``, with ``rejected`` returning to
the maintainer, and ``blocked``/``archived`` retiring an approved row without deleting its
price history. Only ``draft``/``rejected`` rows edit — an approved price is an artifact the
requisition flow can be held to.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class CatalogItem(TenantNumbered):
    """One tenant catalogue entry — internal stock mirror or supplier product [PCI-]."""

    NUMBER_PREFIX = "PCI"

    SOURCE_TYPES = [
        ("internal", "Internal stock item"),
        ("supplier_product", "Supplier product"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("blocked", "Blocked"),
        ("archived", "Archived"),
    ]
    #: Header edits are a DRAFT-stage activity; a rejected entry returns to the maintainer.
    EDITABLE_STATUSES = ("draft", "rejected")

    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, default="internal")
    item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="procurement_catalog_items",
                             help_text="Stock item mirrored into the catalogue (internal entries)")
    supplier = models.ForeignKey("core.Party", on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name="procurement_catalog_supplier_items",
                                 help_text="Supplier offering this entry")
    contract = models.ForeignKey("scm.SupplierContract", on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name="procurement_contract_catalog_items",
                                 help_text="Agreement this catalogue entry prices against (optional)")
    name = models.CharField(max_length=255)
    supplier_part_no = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    manufacturer = models.CharField(max_length=120, blank=True)
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL,
                            null=True, blank=True, related_name="procurement_catalog_item_uoms")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name="procurement_catalog_item_currencies",
                                 help_text="Price currency (global ISO master)")
    base_price = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                     validators=[MinValueValidator(ZERO)],
                                     help_text="List price the tiers discount from")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name="procurement_catalog_items_submitted",
                                     editable=False)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name="procurement_catalog_items_approved",
                                    editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejection_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name="procurement_catalog_items_created",
                                   editable=False)
    is_preferred = models.BooleanField(default=False,
                                       help_text="Preferred source when requisitions match this entry")
    is_active = models.BooleanField(default=True)
    category_text = models.CharField(max_length=120, blank=True,
                                     help_text="Free-text category for filtering, e.g. 'Safety wear'")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = [("tenant", "number")]
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_catitem_tnt_status_idx"),
            models.Index(fields=["tenant", "item"], name="prc_catitem_tnt_item_idx"),
        ]

    def clean(self):
        if self.source_type == "internal":
            if not self.item_id:
                raise ValidationError({"item": "An internal catalog entry must point at a "
                                               "stock item."})
            if self.item.tenant_id != self.tenant_id:
                raise ValidationError({"item": "That stock item belongs to another workspace."})
        elif self.source_type == "supplier_product" and not (self.name or "").strip():
            raise ValidationError({"name": "A supplier product needs a catalogue name."})

    # -- state ------------------------------------------------------------------------------------

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_purchasable(self):
        """True only when an approved entry is also active — what requisition matching picks."""
        return self.status == "approved" and self.is_active

    # -- actions ----------------------------------------------------------------------------------

    def submit(self, user):
        """Draft/rejected → pending approval. Returns False (and changes nothing) otherwise."""
        if self.status not in ("draft", "rejected"):
            return False
        self.status = "pending_approval"
        self.submitted_by = user
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        return True

    def approve(self, user):
        """Pending approval → approved: purchasable once active."""
        if self.status != "pending_approval":
            return False
        self.status = "approved"
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return True

    def reject(self, user, reason):
        """Pending approval → rejected, carrying the reason back to the maintainer."""
        if self.status != "pending_approval":
            return False
        self.status = "rejected"
        self.rejection_reason = reason or ""
        self.save(update_fields=["status", "rejection_reason", "updated_at"])
        return True

    def block(self):
        """Approved → blocked: kept for history but never picked onto purchase documents."""
        if self.status != "approved":
            return False
        self.status = "blocked"
        self.save(update_fields=["status", "updated_at"])
        return True

    def archive(self):
        """Approved/rejected/blocked → archived: retired without deleting price history."""
        if self.status not in ("approved", "rejected", "blocked"):
            return False
        self.status = "archived"
        self.save(update_fields=["status", "updated_at"])
        return True

    def __str__(self):
        return f"{self.number or 'PCI'} · {self.name}"
