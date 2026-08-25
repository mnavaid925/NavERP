"""Procurement 6.6 RFx Management — RfxEvent + RfxQuestion models.

**RFx Management (RFI, RFP, RFQ)** bullet: structured information requests sent to suppliers,
scored against weighted questionnaires. An ``RfxEvent`` is ONE request (RFI/RFP/RFQ) with its
questionnaire; a supplier's reply is an ``RfxResponse`` (see Responses.py).

The **RFx Template Library** bullet is the same table with ``is_template=True``: a draft event
kept as a reusable questionnaire blueprint that *Use* clones into a fresh event — copies, never
links, for the same reason requisition templates copy (a later template edit must not rewrite
issued requests).

Ownership (L29/L36): suppliers are ``core.Party`` rows (the unified spine) and the sourcing link
is an optional FK to 4.1's ``scm.PurchaseRequisition`` — this app declares no vendor master and
no second requisition. scm's own ``RFQ`` [RFQ-] prices LINES; an RFx event asks QUESTIONS —
complementary layers, not duplicates, so the two coexist by design.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class RfxEvent(TenantNumbered):
    """One RFx document — a questionnaire event issued to suppliers [RFX-].

    Lifecycle: ``draft`` (builder open) → ``issued`` (responses collected) → ``closed``
    (evaluation only) or → ``cancelled``. Only drafts edit; that is what makes an issued
    event a stable artifact its responses can be compared against.
    """

    NUMBER_PREFIX = "RFX"

    RFX_TYPES = [
        ("rfi", "RFI — Request for Information"),
        ("rfp", "RFP — Request for Proposal"),
        ("rfq", "RFQ — Request for Quotation"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    #: Header/questionnaire edits are a DRAFT-stage activity; issued events are frozen artifacts.
    EDITABLE_STATUSES = ("draft",)
    #: Events that may still receive recorded responses.
    LIVE_STATUSES = ("draft", "issued")

    rfx_type = models.CharField(max_length=3, choices=RFX_TYPES, default="rfp",
                                help_text="Information (RFI), proposal (RFP) or quotation (RFQ)")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True,
                                   help_text="Instructions shown to suppliers alongside the questions")
    requisition = models.ForeignKey("scm.PurchaseRequisition", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="rfx_events",
                                    help_text="Sourcing this event supports (optional)")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    response_due = models.DateTimeField(null=True, blank=True,
                                        help_text="Deadline for supplier responses")
    issued_at = models.DateTimeField(null=True, blank=True, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="procurement_rfx_events",
                                   editable=False)
    is_template = models.BooleanField(
        default=False,
        help_text="Template-library row: a reusable questionnaire kept in draft and cloned "
                  "into real events via Use")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_rfx_tnt_status_idx"),
            models.Index(fields=["tenant", "is_template"], name="prc_rfx_tnt_tmpl_idx"),
        ]

    # -- state ------------------------------------------------------------------------------------

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def accepts_responses(self):
        return self.status in self.LIVE_STATUSES

    # -- scoring aggregates (derived on read — never stored, never editable) ----------------------

    @property
    def total_weight(self):
        """Sum of scored-question weights — the denominator every response of this event shares."""
        total = self.questions.filter(is_scored=True).aggregate(t=Sum("weight"))["t"]
        return total if total is not None else ZERO

    @property
    def possible_points(self):
        """Maximum weighted score: each scored question contributes up to 10 points × weight."""
        return Decimal("10") * self.total_weight

    # -- actions ----------------------------------------------------------------------------------

    def issue(self):
        """Draft → issued. Returns False (and changes nothing) when not issuable."""
        if self.status != "draft":
            return False
        if not self.questions.exists():
            return False
        self.status = "issued"
        self.issued_at = timezone.now()
        self.save(update_fields=["status", "issued_at", "updated_at"])
        return True

    def close(self):
        """Issued → closed: no further submissions; evaluation continues."""
        if self.status != "issued":
            return False
        self.status = "closed"
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at", "updated_at"])
        return True

    def cancel(self):
        """Draft/issued → cancelled."""
        if self.status not in ("draft", "issued"):
            return False
        self.status = "cancelled"
        self.save(update_fields=["status", "updated_at"])
        return True

    def clone_as(self, user):
        """Clone this template into a fresh REAL draft event (copies, never links)."""
        with transaction.atomic():
            clone = RfxEvent.objects.create(
                tenant=self.tenant,
                rfx_type=self.rfx_type,
                title=self.title,
                description=self.description,
                requisition_id=self.requisition_id,
                status="draft",
                created_by=user,
                is_template=False,
            )
            RfxQuestion.objects.bulk_create([
                RfxQuestion(
                    event=clone,
                    section=q.section,
                    prompt=q.prompt,
                    help_text=q.help_text,
                    answer_type=q.answer_type,
                    options=q.options,
                    weight=q.weight,
                    is_scored=q.is_scored,
                    order=q.order,
                )
                for q in self.questions.all()
            ])
        return clone

    def __str__(self):
        return f"{self.number or 'RFX'} · {self.title}"


class RfxQuestion(models.Model):
    """One questionnaire line on an RFx event.

    ``weight`` drives the scoring system: a response's earned score per question is
    ``score (0–10) × weight``, so heavier questions move the ranking more. Questions have no
    tenant column of their own — they are children whose scope rides the event.
    """

    ANSWER_TYPES = [
        ("text", "Short text"),
        ("longtext", "Long text"),
        ("number", "Number"),
        ("date", "Date"),
        ("choice", "Choice (single select)"),
    ]

    event = models.ForeignKey("procurement.RfxEvent", on_delete=models.CASCADE,
                              related_name="questions")
    section = models.CharField(max_length=120, blank=True,
                               help_text="Optional grouping, e.g. 'Technical' / 'Commercial'")
    prompt = models.TextField(help_text="The question asked of every supplier")
    help_text = models.CharField(max_length=255, blank=True,
                                 help_text="Clarification rendered under the prompt")
    answer_type = models.CharField(max_length=10, choices=ANSWER_TYPES, default="text")
    options = models.TextField(blank=True,
                               help_text="For choice questions: one option per line")
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"),
                                 validators=[MinValueValidator(ZERO)],
                                 help_text="Scoring weight — 0 excludes from the score, higher moves the ranking more")
    is_scored = models.BooleanField(default=True,
                                    help_text="Unscored questions collect answers but never affect totals")
    order = models.PositiveIntegerField(default=0, help_text="Display position (builder reorders)")

    class Meta:
        ordering = ["order", "id"]

    def clean(self):
        if self.answer_type == "choice" and not self.ordered_options():
            raise ValidationError({"options": "A choice question needs at least one option "
                                              "(one per line)."})

    def ordered_options(self):
        """The choice options as a clean list (whitespace-stripped, blanks dropped)."""
        return [line.strip() for line in (self.options or "").splitlines() if line.strip()]

    @property
    def max_points(self):
        """What a perfect answer to this question is worth toward the response's total."""
        return q2(Decimal("10") * self.weight) if self.is_scored else ZERO

    def __str__(self):
        return f"Q{self.order} · {self.prompt[:60]}"
