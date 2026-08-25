"""Procurement 6.5 Sourcing & Tendering — SourcingBid + BidScore models.

**Bid Submission Portal** bullet: "Secure area for suppliers to submit their proposals and
pricing." The BID is the submitted proposal: a whole-package price, lead time, a compliance
self-declaration and the evaluator's shortlist/disqualify decisions. This pass captures bids
through the staff console (as scm's own RFQ quotes are); the supplier-facing gated submission
page is the documented follow-up once 6.4's portal-access binding has landed — ``submitted_by``
is already recorded so the audit trail will carry over unchanged.

The award (**Award Recommendation** bullet) is a fact about a bid, not about the event: exactly
one live compliant bid ends ``won``, every other live bid on the event ends ``lost``. That keeps
the event table free of a reverse FK and makes "who won" readable straight off the register.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class SourcingBid(TenantNumbered):
    """A supplier's whole-package proposal against one sourcing event [BID-]."""

    NUMBER_PREFIX = "BID"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("shortlisted", "Shortlisted"),
        ("disqualified", "Disqualified"),
        ("won", "Won"),
        ("lost", "Lost"),
    ]
    #: Statuses an evaluator still acts on (shortlist / disqualify / award math).
    EVALUABLE_STATUSES = ("submitted", "shortlisted")
    #: Statuses that count as participation when the event is analysed.
    COUNTED_STATUSES = ("submitted", "shortlisted", "disqualified", "won", "lost")
    EDITABLE_STATUSES = ("draft",)
    DECIDABLE_STATUSES = ("submitted", "shortlisted")

    event = models.ForeignKey("procurement.SourcingEvent", on_delete=models.CASCADE,
                              related_name="bids")
    supplier = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT, related_name="procurement_sourcing_bids",
        help_text="Who bid (a Party carrying the supplier or vendor role)")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")

    total_price = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text="Whole-package price quoted for the event scope")
    lead_time_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="Quoted delivery lead time, in days")
    is_compliant = models.BooleanField(
        default=True, help_text="Supplier meets the event's stated compliance requirements")
    compliance_note = models.CharField(max_length=255, blank=True,
                                       help_text="What is missing when not compliant")
    summary = models.TextField(blank=True, help_text="Proposal abstract / exceptions taken")
    contact_ref = models.CharField(max_length=120, blank=True,
                                   help_text="Reference or reply-to captured with the submission")
    decision_note = models.TextField(blank=True,
                                     help_text="Evaluator notes — e.g. why a bid was disqualified")

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_sourcing_bids_submitted", editable=False)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "event"], name="prc_bid_tnt_event_idx"),
            models.Index(fields=["tenant", "status"], name="prc_bid_tnt_status_idx"),
        ]

    # -- lifecycle ---------------------------------------------------------------------------------

    def submit(self, user):
        """draft → submitted. Returns True on success; False (with no side effects) when the
        bid was already sent or its event is no longer accepting submissions."""
        if self.status != "draft" or not self.event.bids_allowed:
            return False
        self.status = "submitted"
        self.submitted_at = timezone.now()
        self.submitted_by = user
        self.save(update_fields=["status", "submitted_at", "submitted_by", "updated_at"])
        return True

    def decide(self, action):
        """Evaluator move on a live bid: 'shortlist' or 'disqualify' (→ status), else None."""
        if self.status not in self.DECIDABLE_STATUSES:
            return None
        mapping = {"shortlist": "shortlisted", "disqualify": "disqualified"}
        target = mapping.get(action)
        if target is None:
            return None
        self.status = target
        self.save(update_fields=["status", "updated_at"])
        return target

    @property
    def is_evaluable(self):
        return self.status in self.EVALUABLE_STATUSES

    # -- scoring -----------------------------------------------------------------------------------

    def weighted_score(self, criteria=None):
        """Weighted evaluation score 0..100, or None when the event defines no criteria.

        Contribution of each scored row is ``(score / max_score) × weight_pct``; unscored rows
        contribute nothing but their weight still counts against the denominator convention —
        the sum is capped at the DEFINED total weight, so partial scoring reads honestly lower
        until evaluators finish, never flattering. One query for scores (criteria may be passed
        pre-fetched by batch surfaces).
        """
        if criteria is None:
            criteria = list(self.event.criteria.all())
        if not criteria:
            return None
        by_criterion = {score.criterion_id: score.score
                        for score in self.scores.all()}
        earned = ZERO
        for criterion in criteria:
            raw = by_criterion.get(criterion.pk)
            if raw is None or not criterion.max_score:
                continue
            earned += Decimal(raw) / criterion.max_score * criterion.weight_pct
        return q2(earned)

    def __str__(self):
        return f"{self.number or 'BID'} · {self.supplier}"


class BidScore(models.Model):
    """One evaluator score for one bid against one matrix row."""

    bid = models.ForeignKey("procurement.SourcingBid", on_delete=models.CASCADE,
                            related_name="scores")
    criterion = models.ForeignKey("procurement.EventCriterion", on_delete=models.CASCADE,
                                  related_name="scores")
    score = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO,
                                validators=[MinValueValidator(ZERO)])
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["criterion_id", "id"]
        unique_together = ("bid", "criterion")

    def clean(self):
        errors = {}
        max_score = self.criterion.max_score if self.criterion_id else None
        if max_score is not None and self.score > max_score:
            errors["score"] = f"Above this criterion's scale (max {max_score})."
        if (self.bid_id and self.criterion_id
                and self.criterion.event_id != self.bid.event_id):
            errors["criterion"] = "That criterion belongs to a different event."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.score} / {self.criterion.max_score}"
