"""Inventory 5.3 Purchase Order (PO) Management — PurchaseOrderApprovalRule model.

The PO DOCUMENT is 4.1's ``scm.PurchaseOrder`` (L36 — extend the spine, never re-declare it):
manual creation/drafting and status tracking stay on the spine's own pages. This app adds the
management layer AROUND that document, and its first piece is approval ROUTING policy.

SCM's built-in approve action is a single tenant-admin sign-off. Real purchase orders route by
VALUE and DEPARTMENT — a small order needs one signature, a large one needs several. A rule IS
that policy for one value band (optionally narrowed to one org unit): how many sequential
approval tiers a pending order requires. Who cleared which tier is recorded per order on
``PurchaseOrderApproval``; nothing here decides an outcome by itself.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class PurchaseOrderApprovalRule(TenantOwned):
    """A value-band (+ optional department) routing policy for PO approvals."""

    #: Hard ceiling on tiers — an approval chain longer than ten signatures is a process
    #: smell, not a policy this table should be asked to store.
    MAX_TIERS = 10

    name = models.CharField(max_length=120)
    min_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text="Band lower bound, inclusive")
    max_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Band upper bound, EXCLUSIVE — blank means open-ended above min_amount")
    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_po_approval_rules",
        help_text="Restrict this rule to one department/site — blank matches every order")
    tier_count = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(MAX_TIERS)],
        help_text="Sequential approval sign-offs a matching order must clear")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-min_amount", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="inv_par_tnt_active_idx"),
        ]

    def clean(self):
        if self.max_amount is not None and self.max_amount <= self.min_amount:
            raise ValidationError({"max_amount": "The upper bound must exceed the lower bound."})

    @classmethod
    def resolve(cls, tenant, total, org_unit_id=None):
        """The most-specific active rule whose band covers ``total``, or ``None``.

        Convenience wrapper over :meth:`resolve_from` that fetches this tenant's active
        rules itself — right for one-off decisions (the decide action), wrong for a loop
        (the queue batches instead).
        """
        return cls.resolve_from(
            cls.objects.filter(tenant=tenant, is_active=True), total, org_unit_id)

    @classmethod
    def resolve_from(cls, active_rules, total, org_unit_id=None):
        """:meth:`resolve` over an ALREADY-FETCHED rules iterable — the queue resolves P
        pending orders against ONE queryset this way. Selection is most-specific-wins: a
        rule scoped to the order's org unit beats an unscoped one, then the NARROWEST band
        wins (an open-ended max counts as infinitely wide). ``None`` is a real answer — the
        queue falls back to a single default tier — never a silent zero-tier bypass. Bands
        are half-open (``min <= total < max``) so two adjacent rules can never both match at
        their shared boundary."""
        rules = [
            r for r in active_rules
            if r.min_amount <= total and (r.max_amount is None or r.max_amount > total)
        ]
        for candidates in (
            [r for r in rules if r.org_unit_id and r.org_unit_id == org_unit_id],
            [r for r in rules if not r.org_unit_id],
        ):
            if candidates:
                return min(candidates,
                           key=lambda r: ((r.max_amount if r.max_amount is not None
                                           else Decimal("Infinity")) - r.min_amount))
        return None

    def __str__(self):
        return self.name
