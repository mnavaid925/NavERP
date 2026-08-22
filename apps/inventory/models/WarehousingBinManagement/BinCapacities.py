"""Inventory 5.5 Warehousing & Bin Management — BinCapacity.

**Bin Capacity Management** bullet: weight, volume and quantity limits per bin. The
location spine already carries ONE generic ``Location.capacity`` number (added in 4.4),
but a real capacity envelope is three-dimensional — a bin can be full by weight long
before it is full by count. This is a PROFILE keyed to the existing location, not a
second location master (L36): the bin itself, its tree position and its on-hand all
stay 4.3's; only the limits live here.

**Derived, never stored:** how full a bin actually IS comes from the same append-only
``StockMove`` ledger every other figure reads — one aggregate over the reverse of the
FK, so nothing here can drift from the ledger. Utilisation answers ``None`` when no
limit was set rather than a flattering 0% (the 4.15 honesty rule), because "no limit
declared" and "0% used" are different facts.

Weight/volume limits are stored but NOT converted into percentages: ``scm.Item``
carries no structured unit-weight/volume columns (its attributes are free-form
name/value spec rows), so any such percentage would be invented. The page says what
the limits are and derives only what the data supports.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class BinCapacity(TenantOwned):
    """The declared capacity envelope of one storage location [of 5.5]."""

    location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="bin_capacity",
        help_text="The bin (or dock/staging area) these limits apply to")
    max_weight_kg = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Maximum gross weight the bin may hold, kg (blank = not limited)")
    max_volume_m3 = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Maximum volume the bin may hold, m³ (blank = not limited)")
    max_quantity = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Maximum units the bin may hold (blank = not limited)")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["location__code"]
        # One envelope per bin: a second profile for the same location would leave two
        # sources of truth for "how much fits here" (L37). The constraint also gives the
        # column pair its index for free.
        unique_together = ("tenant", "location")

    def clean(self):
        """A crafted POST must not hang this profile on another workspace's location."""
        if self.location_id and self.location.tenant_id != self.tenant_id:
            raise ValidationError({"location": "That location belongs to another workspace."})

    @property
    def on_hand(self):
        """Units currently at this location — the live StockMove aggregate, never stored."""
        total = self.location.stock_moves.aggregate(q=Sum("quantity"))["q"]
        return total or ZERO

    @property
    def quantity_utilisation(self):
        """On-hand as a percentage of ``max_quantity``, or ``None`` when no limit applies.

        Deliberately un-clamped: a value over 100 is the interesting case — the bin is
        over its declared limit — and the template turns it red rather than hiding it.
        ``None`` means "no quantity limit declared", which must stay visually distinct
        from 0%.
        """
        if not self.max_quantity:
            return None
        return ((self.on_hand / self.max_quantity) * Decimal("100")).quantize(Decimal("0.1"))

    def __str__(self):
        code = self.location.code if self.location_id else "?"
        limits = []
        if self.max_weight_kg:
            limits.append(f"{self.max_weight_kg} kg")
        if self.max_volume_m3:
            limits.append(f"{self.max_volume_m3} m³")
        if self.max_quantity:
            limits.append(f"{self.max_quantity} units")
        return f"{code} · {' / '.join(limits) or 'no limits set'}"
