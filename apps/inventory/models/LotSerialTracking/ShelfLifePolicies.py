"""Inventory 5.8 Lot & Serial Number Tracking — ShelfLifePolicy (+ the FEFO classifier).

**Shelf-Life & Expiry Management** bullet: "Tracking expiration dates and enforcing
FEFO (First Expired, First Out)." Expiry dates themselves live on 4.3's ``scm.LotSerial``
(L36); what nothing else records is the POLICY that turns a date into a decision: how
much remaining shelf life a lot must still have before it may leave stock again
(``min_remaining_days`` — customer contracts and regulated goods demand this), when to
start flagging it amber (`warning_days`), and whether the pick order is FEFO at all.

The policy is per item (a OneToOne — one shelf-life regime per SKU). The board that
APPLIES it is computed over the append-only ledger in
``apps/inventory/views/LotSerialTracking/FefoBoard.py``; :func:`classify_lot` below is
the single shared definition of what a lot's date means under its policy, so the board,
the trace page and any future consumer cannot drift apart.
"""
from django.utils import timezone

from apps.inventory.models._base import *  # noqa: F401,F403

#: Flag codes → badge classes, decided in ONE place. theme.css ships colour-named badge
#: modifiers only (green/red/amber/info/muted/slate) — the semantic -success/-warning/
#: -danger variants do not exist and render unstyled (lesson L33).
FLAG_CSS = {
    "expired": "badge-red",
    "blocked": "badge-red",
    "warning": "badge-amber",
    "ok": "badge-green",
    "none": "badge-muted",
}


def classify_lot(lot, policy, today=None):
    """What this lot's expiry date means under ``policy`` — ``(code, css, label)``.

    Codes: ``expired`` (past date — write-off territory), ``blocked`` (still in date but
    inside the minimum-remaining-shelf-life gate — do not promise or pick outbound),
    ``warning`` (inside the amber window — move it first, FEFO does this naturally),
    ``ok``, and ``none`` (no expiry recorded — lots of goods simply don't expire).
    A lot without a policy falls back to plain expired/not-expired.
    """
    if lot.expiry_date is None:
        return ("none", FLAG_CSS["none"], "No expiry")
    today = today or timezone.localdate()
    remaining = (lot.expiry_date - today).days
    if remaining < 0:
        return ("expired", FLAG_CSS["expired"], f"Expired {-remaining}d ago")
    if policy is not None and remaining <= policy.min_remaining_days:
        return ("blocked", FLAG_CSS["blocked"], f"Do not ship · {remaining}d left")
    if policy is not None and remaining <= policy.warning_days:
        return ("warning", FLAG_CSS["warning"], f"Expiring in {remaining}d")
    return ("ok", FLAG_CSS["ok"], f"{remaining}d left")


class ShelfLifePolicy(TenantOwned):
    """Per-SKU shelf-life regime applied by the FEFO board [of 5.8]."""

    item = models.OneToOneField(
        "scm.Item", on_delete=models.CASCADE, related_name="shelf_life_policy",
        help_text="One shelf-life regime per tracked SKU")
    shelf_life_days = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Total expected shelf life in days — informational context for the board")
    min_remaining_days = models.PositiveSmallIntegerField(
        default=0,
        help_text="Outbound gate: lots with less remaining life than this are flagged "
                  "do-not-ship")
    warning_days = models.PositiveSmallIntegerField(
        default=30, help_text="Amber window: lots expiring within this many days are "
                              "flagged for first-out picking")
    fefo_enforced = models.BooleanField(
        default=True, help_text="Pick strictly earliest-expiry-first for this item")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["item__sku"]

    @property
    def status_css(self):
        """Whether this regime's gate is armed at all — list-page chip."""
        return "badge-info" if self.min_remaining_days > 0 else "badge-muted"

    def clean(self):
        super().clean()
        if self.item_id and self.item.tenant_id != self.tenant_id:
            raise ValidationError({"item": "That item belongs to another workspace."})
        # The red line must sit INSIDE the amber window, or the amber band can never be
        # seen before the block fires and the warning column lies about the sequence.
        if self.warning_days < self.min_remaining_days:
            raise ValidationError(
                {"warning_days": "The warning window must start at or beyond the "
                                 "minimum-remaining gate."})

    def __str__(self):
        return f"{self.item_id and self.item.sku} shelf life"
