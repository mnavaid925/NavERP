"""Inventory 5.7 Stock Movement & Transfers — TransferApproval.

One row per cleared approval tier on one ``scm.StockTransfer``. The spine's status
columns can only remember where a movement stands; this table remembers how it got
there — every tier, who signed it, when, and under which routing rule.

Rows are written ONLY by the transfer queue's tier actions (never a generic create
form), so ``decided_by`` is stamped from the request, not typed. A REJECTION does not
delete the earlier approvals: :meth:`TransferApproval.cleared_tier_count` replays the
decisions in order and restarts the count after the latest rejection, so history
survives while progress honestly resets — and a resubmitted movement re-decides its
tiers as fresh rows rather than colliding with the previous run's (there is
deliberately NO ``(tenant, transfer, tier)`` uniqueness: it would brick every
rejected-then-resubmitted chain with an IntegrityError). Sequential integrity instead
comes from the decide view locking the TRANSFER row (``select_for_update``), which
also stops two admins clearing the same next tier.
"""
from django.conf import settings

from apps.inventory.models._base import *  # noqa: F401,F403


class TransferApproval(TenantNumbered):
    """One sequential sign-off on one stock transfer [TA-]."""

    NUMBER_PREFIX = "TA"

    DECISION_CHOICES = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    #: Badge colour per decision — theme.css ships colour-named modifiers only (L33).
    DECISION_CSS = {
        "approved": "badge-green",
        "rejected": "badge-red",
    }

    #: CASCADE, not PROTECT: the chain is meaningless without its movement, and scm's
    #: transfer delete refuses non-drafts anyway. Provenance survives in core.AuditLog.
    transfer = models.ForeignKey(
        "scm.StockTransfer", on_delete=models.CASCADE, related_name="approval_decisions")
    #: The routing rule that demanded this tier — snapshotted at decision time; SET_NULL
    #: so deleting a policy never rewrites what actually governed a past movement.
    rule = models.ForeignKey(
        "inventory.TransferApprovalRule", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="transfer_decisions")
    tier = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="1-based position in the approval sequence")
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES, default="approved")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_transfer_tier_decisions", editable=False)
    decided_at = models.DateTimeField(default=timezone.now, editable=False)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["transfer_id", "tier"]
        indexes = [
            models.Index(fields=["tenant", "transfer"], name="inv_ta_tnt_trf_idx"),
        ]

    @staticmethod
    def cleared_tier_count(decisions):
        """Approved tiers in the CURRENT run, replaying decisions oldest-first.

        A rejection resets the count to zero — earlier signatures do not carry across a
        rejected run — and approvals after it rebuild from tier 1. Takes an iterable of
        decision rows (or bare decision strings) rather than querying, so callers that
        already fetched the chain pay nothing extra."""
        cleared = 0
        for row in decisions:
            decision = row if isinstance(row, str) else row.decision
            cleared = 0 if decision == "rejected" else cleared + 1
        return cleared

    @property
    def decision_css(self):
        return self.DECISION_CSS.get(self.decision, "badge-muted")

    def __str__(self):
        trf = self.transfer.number if self.transfer_id else "TRF"
        return f"{self.number or 'TA'} · {trf} · tier {self.tier} {self.get_decision_display()}"
