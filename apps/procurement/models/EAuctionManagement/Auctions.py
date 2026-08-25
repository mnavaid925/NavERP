"""Procurement 6.7 E-Auction Management — Eauction + EaucInvite models.

**Auction Setup & Configuration** bullet: a reverse auction (suppliers compete by LOWERING the
price) configured with a start price, a per-bid ``min_decrement``, and the anti-sniping pair
(extension trigger seconds, extension length, cap) that **Bid Extension & Rule Enforcement**
executes at bid time.

Lifecycle: ``draft`` → ``scheduled`` (published with an opens/closes window) → ``closed`` →
``awarded``, or → ``cancelled``. "LIVE" is deliberately DERIVED (scheduled AND now inside the
window) rather than a fifth status: it would need a third writer flipping rows on a timer, and
every status in this codebase has exactly one writer. Closing is allowed any time after
publication (early close = buyer's prerogative); awarding requires closed.

Ownership (L29/L36): suppliers are invited ``core.Party`` rows (the spine), the optional sourcing
link is 4.1's ``scm.PurchaseRequisition``; money columns mirror the scm Decimal(14,2) shape via
the app base's q2/MAX_Q2 contract.
"""
from datetime import timedelta

from django.db.models import Count, Max, Min

from apps.procurement.models._base import *  # noqa: F401,F403


class Eauction(TenantNumbered):
    """One e-auction event [EAUC-] — configuration, window and award decision."""

    NUMBER_PREFIX = "EAUC"

    AUCTION_TYPES = [
        ("reverse", "Reverse auction (price falls)"),
        ("forward", "Forward auction (price rises)"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("closed", "Closed"),
        ("awarded", "Awarded"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("draft",)
    #: Statuses from which publication/cancellation are legal.
    CANCELLABLE_STATUSES = ("draft", "scheduled")

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True,
                                   help_text="Scope and rules shown to invited suppliers")
    auction_type = models.CharField(max_length=8, choices=AUCTION_TYPES, default="reverse")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="procurement_eauc_auctions")
    requisition = models.ForeignKey("scm.PurchaseRequisition", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="eauctions",
                                    help_text="Sourcing this auction supports (optional)")
    start_price = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text="Opening ceiling for the first bid (reverse auction)")
    reserve_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Internal target — results flag winning bids that land below it")
    min_decrement = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("100.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Each supplier's next bid must undercut their own previous bid "
                  "by at least this much")
    # -- anti-sniping rules (Bid Extension & Rule Enforcement) -----------------------------------
    extension_trigger_seconds = models.PositiveIntegerField(
        default=60,
        help_text="A bid inside this many seconds of the close extends the auction")
    extension_seconds = models.PositiveIntegerField(
        default=120,
        help_text="How long each automatic extension adds to closes_at")
    max_extensions = models.PositiveIntegerField(
        default=3,
        help_text="Hard cap so an auction cannot extend forever")
    extensions_used = models.PositiveIntegerField(default=0, editable=False)
    # -- window / lifecycle ----------------------------------------------------------------------
    opens_at = models.DateTimeField(help_text="When bidding may begin")
    closes_at = models.DateTimeField(help_text="When bidding ends (extensions push this later)")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    # -- award decision (Post-Auction Results) -----------------------------------------------------
    awarded_supplier = models.ForeignKey("core.Party", on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name="procurement_eauc_wins",
                                         help_text="Set once, when the auction is awarded")
    awarded_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                         editable=False)
    award_note = models.TextField(blank=True)
    awarded_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="procurement_eauc_auctions",
                                   editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_eauc_tnt_status_idx"),
            models.Index(fields=["tenant", "opens_at"], name="prc_eauc_tnt_open_idx"),
        ]

    # -- state ------------------------------------------------------------------------------------

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def accepts_bids(self):
        """LIVE = scheduled AND inside the window — derived, never stored."""
        if self.status != "scheduled":
            return False
        now = timezone.now()
        return self.opens_at <= now < self.closes_at

    @property
    def seconds_remaining(self):
        if self.status != "scheduled":
            return None
        return int((self.closes_at - timezone.now()).total_seconds())

    @property
    def time_left_display(self):
        """Server-rendered countdown text ("4m 12s"); negative = window elapsed."""
        remaining = self.seconds_remaining
        if remaining is None:
            return None
        sign = "-" if remaining < 0 else ""
        remaining = abs(remaining)
        minutes, seconds = divmod(remaining, 60)
        return f"{sign}{minutes}m {seconds:02d}s"

    @property
    def in_extension_zone(self):
        """True when a bid placed RIGHT NOW must trigger the anti-snipe extension."""
        remaining = self.seconds_remaining
        return remaining is not None and 0 <= remaining <= self.extension_trigger_seconds

    # -- actions (each returns bool; views translate False into messages) ---------------------------

    def clean(self):
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValidationError({"closes_at": "The close must come after the opening."})

    def publish(self):
        """Draft → scheduled. Refused without a sane window or any invitee."""
        if self.status != "draft":
            return False
        if self.closes_at <= timezone.now():
            return False
        if not self.invites.exists():
            return False
        self.status = "scheduled"
        self.save(update_fields=["status", "updated_at"])
        return True

    def close(self):
        """Scheduled → closed (manual early close is allowed; late bids are refused by accepts_bids)."""
        if self.status != "scheduled":
            return False
        self.status = "closed"
        self.save(update_fields=["status", "updated_at"])
        return True

    def cancel(self):
        if self.status not in self.CANCELLABLE_STATUSES:
            return False
        self.status = "cancelled"
        self.save(update_fields=["status", "updated_at"])
        return True

    def extend_if_needed(self):
        """Anti-snipe rule, called under row lock AFTER a bid lands.

        Returns "extended" | "capped" | "no" so the view can explain what happened.
        """
        if not self.in_extension_zone:
            return "no"
        if self.extensions_used >= self.max_extensions:
            return "capped"
        self.closes_at = self.closes_at + timedelta(seconds=self.extension_seconds)
        self.extensions_used += 1
        self.save(update_fields=["closes_at", "extensions_used", "updated_at"])
        return "extended"

    def award(self, supplier, note=""):
        """Closed → awarded, recording the decision ONCE.

        The ``awarded_supplier_id`` guard is the second line of defence behind the view's
        row lock: two concurrent POSTs can both pass the status check before either saves,
        but only the first save ever lands a winner.
        """
        if self.status != "closed" or self.awarded_supplier_id is not None:
            return False
        best = self.best_bid()
        if best is None or supplier.pk != best.supplier_id:
            return False  # only the current leading supplier can be awarded
        self.status = "awarded"
        self.awarded_supplier = supplier
        self.awarded_amount = best.amount
        self.award_note = note or ""
        self.awarded_at = timezone.now()
        self.save(update_fields=["status", "awarded_supplier", "awarded_amount",
                                 "award_note", "awarded_at", "updated_at"])
        return True

    # -- bid-board aggregates ------------------------------------------------------------------------

    def best_bid(self):
        """Current leader: lowest amount (tie-break earliest)."""
        return self.bids.order_by("amount", "placed_at", "id").first()

    def rankings(self):
        """Per-supplier leaderboard: [{supplier, best, count, last_at}] sorted best-first.

        ONE query over the append-only log; nothing ranked is ever stored.
        """
        rows = (self.bids.values("supplier_id", "supplier__name")
                .annotate(best=Min("amount"), count=Count("id"), last_at=Max("placed_at"))
                .order_by("best", "last_at"))
        return [{"supplier_id": r["supplier_id"], "supplier_name": r["supplier__name"],
                 "best": r["best"], "count": r["count"], "last_at": r["last_at"]} for r in rows]

    def savings_vs_start(self):
        """Realized saving of the leading bid against the opening ceiling (None pre-first-bid)."""
        best = self.best_bid()
        if best is None:
            return None
        return q2(self.start_price - best.amount)

    def __str__(self):
        return f"{self.number or 'EAUC'} · {self.title}"


class EaucInvite(models.Model):
    """A supplier admitted into one auction (mirrors scm.RFQVendor's shape).

    Carries its own tenant column so invite lists filter directly, consistent with how the
    sibling child tables in this app are queried.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="+", db_index=True)
    auction = models.ForeignKey("procurement.Eauction", on_delete=models.CASCADE,
                                related_name="invites")
    supplier = models.ForeignKey("core.Party", on_delete=models.PROTECT,
                                 related_name="procurement_eauc_invites")
    invited_at = models.DateTimeField(default=timezone.now)
    contact_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["supplier__name"]
        unique_together = ("auction", "supplier")

    def __str__(self):
        return f"{self.supplier} on {self.auction_id}"
