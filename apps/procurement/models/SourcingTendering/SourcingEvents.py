"""Procurement 6.5 Sourcing & Tendering — SourcingEvent + EventCriterion models.

**Event Creation & Scheduling** bullet: "Setup of sourcing events, timelines, and rules." A
sourcing event is the strategic container — a tender, RFP or restricted RFQ run as one
competitive exercise with its own timeline, rules and budget expectation, against which
suppliers submit whole-package bids (``Bids.py``) and evaluators score them against the
weighted criteria defined here.

**Ownership (L29/L36):** ``scm.RFQ``/``RFQQuote`` own OPERATIONAL line-by-line quote requests;
this layer is the competitive process above them and shares nothing with those tables. The only
spine link is an OPTIONAL traceability FK to the requisition that triggered the event — never a
duplicate of it.

The event deliberately carries NO FK to its bids: the award is a fact about a BID (its status
becomes ``won``), so the two entity modules of this sub-module reference each other in exactly
one direction (bid → event) and neither imports the other's class.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class SourcingEvent(TenantNumbered):
    """A competitive sourcing exercise [SEV-] — tender / RFP / restricted RFQ.

    Lifecycle: draft → open (bids may be submitted) → closed (evaluation) → awarded, or
    cancelled from any live state. Editing the header/rules stays possible while draft or
    open; once closed the record freezes apart from the award decision itself.
    """

    NUMBER_PREFIX = "SEV"

    TYPE_CHOICES = [
        ("tender", "Open Tender"),
        ("rfp", "RFP"),
        ("rfq", "Restricted RFQ"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("closed", "Closed"),
        ("awarded", "Awarded"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("draft", "open")
    #: Only an OPEN event accepts new bids; everything else has missed its window.
    LIVE_STATUS = "open"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True,
                                   help_text="Scope of the requirement suppliers are bidding on")
    event_type = models.CharField(max_length=12, choices=TYPE_CHOICES, default="tender")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")

    requisition = models.ForeignKey(
        "scm.PurchaseRequisition", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sourcing_events",
        help_text="Requisition that triggered this event (traceability only)")
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_sourcing_events")
    budget_estimate = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Internal expectation for this spend — blank when genuinely unknown")

    opens_at = models.DateTimeField(null=True, blank=True,
                                    help_text="When suppliers may start submitting bids")
    closes_at = models.DateTimeField(null=True, blank=True,
                                     help_text="Submission deadline — the evaluation window opens")
    rules = models.TextField(blank=True,
                             help_text="Rules sent to suppliers: terms, compliance requirements,"
                                       " how bids will be evaluated")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_sourcing_events_created", editable=False)
    opened_at = models.DateTimeField(null=True, blank=True, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    awarded_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_sev_tnt_status_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def bids_allowed(self):
        return self.status == self.LIVE_STATUS

    @property
    def is_evaluating(self):
        """Closed-but-not-yet-awarded: the evaluation/award surface is live."""
        return self.status == "closed"

    def award(self, bid, at=None):
        """Record the award (**Award Recommendation** bullet) — the ONE writer of won/lost.

        The chosen bid becomes ``won``; every other still-evaluable bid on the event becomes
        ``lost``; the event itself closes out as ``awarded``. Returns True on success; False
        (no side effects) when the state machine disagrees — the view has already produced the
        human-readable reason, this re-check guards crafted or racing POSTs.

        Callers wrap in ``transaction.atomic()`` and write the audit rows.
        """
        # Local import keeps this module free of an import-time edge to Bids.py (the FK graph
        # already runs bid → event one way; the lifecycle logic here is the only back-reference).
        from apps.procurement.models.SourcingTendering.Bids import SourcingBid

        if not self.is_evaluating:
            return False
        if bid.event_id != self.pk or not bid.is_evaluable or not bid.is_compliant:
            return False
        at = at or timezone.now()
        (type(bid).objects
         .filter(event=self, status__in=SourcingBid.EVALUABLE_STATUSES)
         .exclude(pk=bid.pk)
         .update(status="lost"))
        bid.status = "won"
        bid.save(update_fields=["status", "updated_at"])
        self.status = "awarded"
        self.awarded_at = at
        self.save(update_fields=["status", "awarded_at", "updated_at"])
        return True

    def __str__(self):
        return f"{self.number or 'SEV'} · {self.title}"


class EventCriterion(models.Model):
    """One weighted row of the event's evaluation matrix (**Bid Evaluation Matrix** bullet).

    Scores are recorded per bid on ``BidScore``; this table only DEFINES what evaluators score.
    Weights are per-event percentages: the formset refuses a combined weight above 100 (below
    100 renders as visible coverage on the event page rather than being silently topped up).
    """

    event = models.ForeignKey("procurement.SourcingEvent", on_delete=models.CASCADE,
                              related_name="criteria")
    name = models.CharField(max_length=120, help_text="e.g. 'Total cost', 'Delivery lead time',"
                                                      " 'Compliance & certifications'")
    weight_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
        help_text="Share of the overall score, 0-100")
    max_score = models.PositiveIntegerField(
        default=10, validators=[MinValueValidator(1)],
        help_text="Scale an evaluator scores this criterion on, e.g. 1-10")
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]
        unique_together = ("event", "name")

    @property
    def weight_fraction(self):
        """Weight as a 0..1 fraction — the exact unit the weighted-score math consumes."""
        return (self.weight_pct or ZERO) / Decimal("100")

    def clean(self):
        if self.event_id and self.max_score and self.max_score < 1:
            raise ValidationError({"max_score": "Score scale must allow at least 1 point."})

    def __str__(self):
        return f"{self.name} ({self.weight_pct}%)"
