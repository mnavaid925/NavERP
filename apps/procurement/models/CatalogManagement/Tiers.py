"""Procurement 6.9 Catalog Management — CatalogPriceTier model.

**Pricing & Tier Management**: one row is a volume price break on a ``CatalogItem`` —
"buy ≥ N units at this price". A tier enters as *Proposed* (draft), is approved into the
single *Active* break quoting uses, and leaves the stage as *Superseded* (replaced by a
newer break) or *Cancelled*. Exactly ONE active tier may cover a given (item, min_quantity)
break — enforced here in ``clean()`` against the tenant-scoped siblings, excluding self so
re-saving a row never collides with itself.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class CatalogPriceTier(TenantOwned):
    """One volume price break on a catalogue item.

    Money shape mirrors the catalogue: Decimal(14, 2) clamped through ``q2`` where derived.
    Lifecycle moves ONLY through the guarded actions (``approve`` / ``retire`` / ``cancel``);
    ``status`` is never a form field, same rule as every workflow status in this app.
    """

    STATUS_CHOICES = [
        ("draft", "Proposed"),
        ("active", "Active"),
        ("superseded", "Superseded"),
        ("cancelled", "Cancelled"),
    ]
    #: The one status quoting treats as the live break for its quantity step.
    ACTIVE_STATUS = "active"

    catalog_item = models.ForeignKey("procurement.CatalogItem", on_delete=models.CASCADE,
                                     related_name="price_tiers")
    min_quantity = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("1"),
        validators=[MinValueValidator(ZERO)],
        help_text="Quantity from which this price applies")
    unit_price = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text="Used when no discount percentage is given")
    discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Percent off the item's base price — leave blank to price at unit_price "
                  "(capped at 100)")
    valid_from = models.DateField(null=True, blank=True,
                                  help_text="Optional start of the validity window")
    valid_until = models.DateField(null=True, blank=True,
                                   help_text="Open-ended when left blank")
    contract = models.ForeignKey("scm.SupplierContract", on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name="procurement_contract_price_tiers",
                                 help_text="Supplier agreement this break honours (optional)")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name="procurement_price_tiers_submitted")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name="procurement_price_tiers_approved")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["catalog_item_id", "min_quantity"]
        unique_together = ("tenant", "catalog_item", "min_quantity", "valid_from")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_cattier_tnt_status_idx"),
        ]

    # -- validation --------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError({"valid_until": "Valid-until cannot precede valid-from."})
        if self.discount_pct is not None and self.discount_pct > Decimal("100"):
            raise ValidationError({"discount_pct": "A discount cannot exceed 100%."})
        # Overlap guard: among ACTIVE rows of this tenant, an (item, min_quantity) break is
        # single-occupancy. Query the siblings excluding self so editing a row never trips on
        # its own record; runs on EVERY save path that validates (forms), not just approvals.
        if self.catalog_item_id and self.tenant_id:
            clash = (CatalogPriceTier.objects
                     .filter(tenant_id=self.tenant_id,
                             catalog_item_id=self.catalog_item_id,
                             min_quantity=self.min_quantity,
                             status=self.ACTIVE_STATUS)
                     .exclude(pk=self.pk))
            if clash.exists():
                raise ValidationError({
                    "min_quantity": "An active tier already covers this quantity break for "
                                    "this item.",
                })

    # -- derivation ----------------------------------------------------------------------------------

    def effective_price(self, base):
        """The price this break yields against the item's ``base``: the unit price verbatim,
        or the base less the discount percentage."""
        if self.discount_pct is None:
            return self.unit_price
        return q2(base * (Decimal("1") - self.discount_pct / Decimal("100")))

    # -- actions -------------------------------------------------------------------------------------

    def approve(self, user):
        """Proposed → active, stamping who approved and when. Returns False otherwise."""
        if self.status != "draft":
            return False
        self.status = "active"
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return True

    def retire(self):
        """Active → superseded: the break no longer quotes, history keeps it visible."""
        if self.status != "active":
            return False
        self.status = "superseded"
        self.save(update_fields=["status", "updated_at"])
        return True

    def cancel(self):
        """Proposed or superseded → cancelled. An active break must retire instead."""
        if self.status not in ("draft", "superseded"):
            return False
        self.status = "cancelled"
        self.save(update_fields=["status", "updated_at"])
        return True

    def __str__(self):
        return f"Tier ≥{self.min_quantity} on item #{self.catalog_item_id} ({self.status})"
