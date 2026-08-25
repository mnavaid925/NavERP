"""Procurement 6.7 E-Auction Management — EaucBid model.

**Live Bidding Interface** data layer: the bid log is APPEND-ONLY (a retracted/edited bid would
rewrite auction history), and every rule in **Bid Extension & Rule Enforcement** is enforced
here at write time — window open, supplier invited, monotone lowering with the per-supplier
``min_decrement`` pace, first bid under the start price. Rankings are derived from this log by
``Eauction.rankings()``; nothing ranked is ever stored.
"""
from django.db.models import Min

from apps.procurement.models._base import *  # noqa: F401,F403


class EaucBid(TenantNumbered):
    """One lowering bid [EBID-] on an e-auction — an append-only log entry."""

    NUMBER_PREFIX = "EBID"

    auction = models.ForeignKey("procurement.Eauction", on_delete=models.CASCADE,
                                related_name="bids")
    supplier = models.ForeignKey("core.Party", on_delete=models.PROTECT,
                                 related_name="procurement_eauc_bids")
    amount = models.DecimalField(max_digits=14, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    note = models.CharField(max_length=255, blank=True,
                            help_text="Optional remark carried with the bid")
    placed_at = models.DateTimeField(default=timezone.now, editable=False)
    placed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                  null=True, blank=True, editable=False, related_name="+",
                                  help_text="Staff recorder, or the vendor-portal user themselves")

    class Meta:
        ordering = ["placed_at", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "auction"], name="prc_ebid_tnt_auction_idx"),
            models.Index(fields=["auction", "amount"], name="prc_ebid_auc_amount_idx"),
        ]

    # -- rule engine (write-time enforcement) ---------------------------------------------------------

    @classmethod
    def next_floor(cls, auction, supplier):
        """The LOWEST amount ``supplier`` may legally bid right now, or None when closed to them.

        House rules (documented verbatim on the rules page):
        * the auction must be live;
        * the supplier must be an invitee;
        * a FIRST bid (theirs) is valid up to the start price — but must still STRICTLY
          improve any standing best (a rival opener equal to the leader moves nothing);
        * afterwards their next bid must undercut THEIR OWN best by >= min_decrement AND
          strictly improve the global best (or stay under it if someone else leads).
        """
        if not auction.accepts_bids:
            return None
        if not auction.invites.filter(supplier=supplier).exists():
            return None
        global_best = auction.best_bid()
        ceiling = auction.start_price if global_best is None else global_best.amount
        # Own best across the WHOLE log — an aggregate, not a slice: an earliest-N cap
        # would quietly weaken the pace rule once a long auction passes N bids.
        own_best = (auction.bids.filter(supplier=supplier)
                    .aggregate(best=Min("amount"))["best"])
        if own_best is None:
            cap = q2(ceiling)
            if global_best is not None:
                cap = min(cap, q2(global_best.amount - Decimal("0.01")))
            return cap if cap > ZERO else None
        pace_cap = q2(own_best - auction.min_decrement)
        # must beat the field too: equal-or-higher than the current best is no improvement.
        if global_best is not None and global_best.supplier_id != supplier.pk:
            cap = min(pace_cap, q2(global_best.amount - Decimal("0.01")))
            return cap if cap > ZERO else None
        return pace_cap if pace_cap > ZERO else None

    def clean(self):
        floor = self.next_floor(self.auction, self.supplier)
        if floor is None:
            # None is overloaded — say WHICH door closed.
            if not self.auction.accepts_bids:
                raise ValidationError("Bidding is not open for this auction.")
            if not self.auction.invites.filter(supplier=self.supplier).exists():
                raise ValidationError("This supplier is not admitted to the auction.")
            raise ValidationError(
                "No legal bid remains for this supplier — the ladder is exhausted "
                "(their best minus the minimum decrement would go below zero).")
        if self.amount > floor:
            raise ValidationError(
                {"amount": f"Bid too high — the next legal amount is {floor} or lower."})

    def save(self, *args, **kwargs):
        if self.placed_at is None:
            self.placed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.supplier} @ {self.amount}"
