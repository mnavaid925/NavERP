"""SCM 4.5 Order Management System — SalesOrderAllocation model.

A SOFT reservation: "this much of this line is spoken for at this location". It deliberately posts
NO ``StockMove``. The append-only ledger stays the single source of physical truth (L37), and stock
only ever physically leaves through 4.4's ``PickTask`` confirm. Inventing a second way for stock to
move is exactly the failure mode the 4.4 cycle-count review turned up — a parallel correction path
that nothing else could see.

So on-hand does NOT drop when an allocation is created. What drops is availability-to-promise, which
the allocation views derive as ``item.on_hand(location) − Σ other active allocations there``.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class SalesOrderAllocation(TenantOwned):
    """A reservation of one order line's quantity against one fulfillment location."""

    STATUS_CHOICES = [
        ("reserved", "Reserved"),
        ("released", "Released"),
        ("cancelled", "Cancelled"),
    ]
    # Both still count toward quantity_allocated() — see the status notes below.
    ACTIVE_STATUSES = ("reserved", "released")

    sales_order_line = models.ForeignKey("scm.SalesOrderLine", on_delete=models.CASCADE,
                                         related_name="allocations")
    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT,
                                 related_name="sales_order_allocations")
    quantity = models.DecimalField(max_digits=16, decimal_places=4,
                                   validators=[MinValueValidator(Decimal("0.0001"))])
    # `reserved`  — a non-physical claim; nothing has been touched on the floor.
    # `released`  — handed off to the warehouse (a pick exists for it). STILL counts as allocated:
    #               it distinguishes "sent to the floor" from "just reserved", it is not a physical
    #               event and it still posts no StockMove.
    # `cancelled` — the claim is dropped without fulfilling. Stops counting, frees the ATP.
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="reserved", editable=False)
    allocated_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-allocated_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_soa_tnt_status_idx"),
            models.Index(fields=["tenant", "location"], name="scm_soa_tnt_loc_idx"),
        ]

    def clean(self):
        """Never promise more of a line than was ordered.

        Counts every OTHER active allocation on the same line plus this one, so it holds on edit as
        well as create. The availability-to-promise check (is the stock actually THERE?) is a
        separate, cross-model question and lives in the view — a model's clean() has no business
        aggregating another model's ledger.
        """
        super().clean()
        if self.sales_order_line_id is None or self.quantity is None:
            return
        line = self.sales_order_line
        others = line.allocations.exclude(status="cancelled")
        if self.pk:
            others = others.exclude(pk=self.pk)
        already = others.aggregate(s=Sum("quantity"))["s"] or ZERO
        room = (line.quantity_ordered or ZERO) - already
        if self.quantity > room:
            raise ValidationError({
                "quantity": (
                    f"Only {room} of {line.quantity_ordered} left to allocate on this line "
                    f"({already} already reserved)."
                )
            })

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def sales_order(self):
        return self.sales_order_line.sales_order

    def __str__(self):
        where = self.location.code if self.location_id else "?"
        return f"{self.quantity} @ {where}"
