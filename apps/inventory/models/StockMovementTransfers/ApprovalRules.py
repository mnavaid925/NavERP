"""Inventory 5.7 Stock Movement & Transfers — TransferApprovalRule.

**Transfer Approval Workflow bullet:** a request-and-approval process that prevents
unauthorized movements. The movement DOCUMENT is 4.3's ``scm.StockTransfer`` (L36) and
its completion posts the ledger pair; what the spine never had is a POLICY for when a
draft transfer must be signed off before it may be executed. A rule IS that policy:
how many sequential approval tiers a matching movement demands, selected by the move's
scope (between warehouses vs within one) and its total unit count.

Same shape as 5.3's ``PurchaseOrderApprovalRule``: bands are half-open so adjacent
rules never both match at their shared boundary, ``None`` from the resolver is a real
answer (the queue falls back to ONE default tier — never a silent zero-tier bypass),
and nothing here decides an outcome by itself. Who cleared which tier lives on
``TransferApproval``.
"""
from apps.inventory.models._base import *  # noqa: F401,F403

#: Scope values a rule can be narrowed to. These mirror the board's computed
#: classification of a spine transfer (warehouse-root walk), not a column on it.
SCOPE_ALL = "all"
SCOPE_INTER = "inter_warehouse"
SCOPE_INTRA = "intra_warehouse"

APPLIES_TO_CHOICES = [
    (SCOPE_ALL, "All transfers"),
    (SCOPE_INTER, "Inter-warehouse only"),
    (SCOPE_INTRA, "Intra-warehouse only"),
]


class TransferApprovalRule(TenantOwned):
    """A scope + size-band routing policy for transfer approvals."""

    #: Same ceiling 5.3 sets: an approval chain longer than ten signatures is a process
    #: smell, not a policy this table should be asked to store.
    MAX_TIERS = 10

    name = models.CharField(max_length=120)
    applies_to = models.CharField(
        max_length=16, choices=APPLIES_TO_CHOICES, default=SCOPE_ALL,
        help_text="Which kind of movement this rule governs")
    min_units = models.DecimalField(
        max_digits=16, decimal_places=4, default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text="Total units across all lines at which this rule starts to apply (inclusive)")
    max_units = models.DecimalField(
        max_digits=16, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Upper bound, EXCLUSIVE — blank means open-ended above min_units")
    tier_count = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(MAX_TIERS)],
        help_text="Sequential approval sign-offs a matching transfer must clear")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-min_units", "name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "is_active"], name="inv_tar_tnt_active_idx")]

    def clean(self):
        if self.max_units is not None and self.max_units <= self.min_units:
            raise ValidationError({"max_units": "The upper bound must exceed the lower bound."})

    @classmethod
    def resolve_from(cls, active_rules, total_units, scope):
        """:meth:`resolve` over an ALREADY-FETCHED rules iterable — the queue resolves
        every pending transfer against ONE queryset this way.

        Selection is most-specific-wins: a rule scoped to the move's actual scope beats
        an all-transfers rule, then the NARROWEST unit band wins (an open-ended max
        counts as infinitely wide). ``None`` is a real answer — callers fall back to a
        single default tier, never a zero-tier bypass."""
        rules = [
            r for r in active_rules
            if r.min_units <= total_units
            and (r.max_units is None or r.max_units > total_units)
            and r.applies_to in (scope, SCOPE_ALL)
        ]
        for candidates in (
            [r for r in rules if r.applies_to == scope],
            [r for r in rules if r.applies_to == SCOPE_ALL],
        ):
            if candidates:
                return min(candidates,
                           key=lambda r: ((r.max_units if r.max_units is not None
                                           else Decimal("Infinity")) - r.min_units))
        return None

    @classmethod
    def resolve(cls, tenant, total_units, scope):
        """The most-specific active rule covering this move, or ``None``.

        Convenience wrapper over :meth:`resolve_from` that fetches the tenant's active
        rules itself — right for one-off decisions (the decide action), wrong for a
        loop (the queue batches instead)."""
        return cls.resolve_from(
            cls.objects.filter(tenant=tenant, is_active=True), total_units, scope)

    def __str__(self):
        return self.name
