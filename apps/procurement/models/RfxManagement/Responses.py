"""Procurement 6.6 RFx Management — RfxResponse + RfxAnswer models.

**Response Collection** bullet: the centralized repository of supplier answers (and the proposal
attachment) for one event. In this pass staff RECORD responses on a supplier's behalf — the
supplier-facing submission surface is 6.4's VendorPortalAccess, which can adopt this model later;
the data shape is already theirs.

**Scoring & Weighting System**: an evaluator rates each answer 0–10 and the response's weighted
total is derived on read — ``Σ score × question weight`` against its event's possible maximum.
Nothing scored is ever stored on the header: like every balance in this codebase, the figure is
computed from its lines so it cannot drift.
"""
from django.db.models import DecimalField, F, Sum

from apps.procurement.models._base import *  # noqa: F401,F403


class RfxResponse(TenantNumbered):
    """One supplier's reply to an RFx event [RXR-] — one per (event, supplier)."""

    NUMBER_PREFIX = "RXR"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("under_review", "Under review"),
        ("scored", "Scored"),
        ("disqualified", "Disqualified"),
    ]
    #: Statuses counted as real submissions (drafts are working copies, disqualified excluded).
    SUBMITTED_STATUSES = ("submitted", "under_review", "scored")
    STATUS_FLOW = {
        # from -> statuses it may legally move to (enforced by rfx_response_set_status).
        "draft": {"submitted", "disqualified"},
        "submitted": {"under_review", "disqualified"},
        "under_review": {"scored", "disqualified"},
        "scored": set(),
        "disqualified": {"under_review"},  # reinstate a mis-flagged response
    }

    event = models.ForeignKey("procurement.RfxEvent", on_delete=models.CASCADE,
                              related_name="responses")
    supplier = models.ForeignKey("core.Party", on_delete=models.PROTECT,
                                 related_name="procurement_rfx_responses",
                                 help_text="The responding supplier (a Party with the supplier role)")
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True,
                             help_text="Cover note / summary of the supplier's submission")
    attachment = models.FileField(
        upload_to="procurement/rfx/%Y/%m/", null=True, blank=True,
        help_text="The supplier's proposal document. Serve with Content-Disposition: attachment "
                  "and keep MEDIA_ROOT outside any executable path.")
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, editable=False,
                                    related_name="+",
                                    help_text="Staff member who recorded this response")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("event", "supplier")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_rxr_tnt_status_idx"),
            models.Index(fields=["tenant", "event"], name="prc_rxr_tnt_event_idx"),
        ]

    # -- state ------------------------------------------------------------------------------------

    @property
    def is_locked(self):
        """Disqualified responses freeze — answers can no longer be edited or scored."""
        return self.status == "disqualified"

    def allowed_transitions(self):
        return self.STATUS_FLOW.get(self.status, set())

    def submit(self):
        """Mark submitted (records the timestamp) — only while the event still accepts replies."""
        if self.status != "draft" or not self.event.accepts_responses:
            return False
        self.status = "submitted"
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at", "updated_at"])
        return True

    def transition(self, to_status):
        """Guarded status move through STATUS_FLOW; returns False when illegal."""
        if to_status not in self.allowed_transitions():
            return False
        if to_status == "submitted" and not self.event.accepts_responses:
            return False
        self.status = to_status
        if to_status == "submitted" and self.submitted_at is None:
            self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at", "updated_at"])
        return True

    # -- scoring aggregates (derived; views may pass precomputed maps to avoid N+1) -----------------

    @property
    def earned_points(self):
        """Σ(score × weight) over answered, scored questions."""
        total = (self.answers.filter(score__isnull=False, question__is_scored=True)
                 .aggregate(t=Sum(F("score") * F("question__weight")))["t"])
        return q2(total) if total is not None else ZERO

    @property
    def score_percent(self):
        """Weighted percentage of the event's possible points — None when nothing is scoreable."""
        possible = self.event.possible_points
        if possible <= ZERO:
            return None
        return (self.earned_points / possible * Decimal("100")).quantize(Decimal("0.1"))

    def __str__(self):
        return f"{self.number or 'RXR'} · {self.supplier} on {self.event_id}"


class RfxAnswer(models.Model):
    """The supplier's answer (and evaluator's 0–10 score) to ONE question of ONE response.

    Answers are PRE-CREATED (one blank row per question) when a response is recorded, so the
    scoring workspace always renders exactly one input per question — no add/remove row plumbing.
    """

    response = models.ForeignKey("procurement.RfxResponse", on_delete=models.CASCADE,
                                 related_name="answers")
    question = models.ForeignKey("procurement.RfxQuestion", on_delete=models.CASCADE,
                                 related_name="answers")
    answer_text = models.TextField(blank=True,
                                   help_text="The supplier's answer (choice answers store the "
                                             "chosen option verbatim)")
    score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("10"))],
                                help_text="Evaluator rating, 0–10")

    class Meta:
        ordering = ["question__order", "question__id"]
        unique_together = ("response", "question")

    @property
    def weighted_points(self):
        """This answer's contribution to the response total (None while unscored)."""
        if self.score is None or not self.question.is_scored:
            return None
        return q2(self.score * self.question.weight)

    def __str__(self):
        return f"{self.response_id} · Q{self.question_id}"


# -- batch scoring helpers ------------------------------------------------------------------------
#
# The per-object properties above cost one aggregate PER ROW — right for a detail page, wrong for
# any list of responses. These map versions compute a whole page in ONE grouped query each, so
# the comparison matrix / leaderboard / registers never fall into an N+1. Callers pass ids they
# already fetched tenant-scoped; the maps add no scoping of their own by design.


def earned_score_map(response_pks):
    """{response_pk: Σ(score × weight) over scored answers} — one grouped query."""
    response_pks = list(response_pks)
    if not response_pks:
        return {}
    rows = (RfxAnswer.objects
            .filter(response_id__in=response_pks, score__isnull=False, question__is_scored=True)
            .values_list("response_id")
            .annotate(t=Sum(F("score") * F("question__weight"),
                            output_field=DecimalField(max_digits=18, decimal_places=2))))
    return {pk: q2(total) for pk, total in rows}


def possible_points_map(event_pks):
    """{event_pk: 10 × Σ scored-question weights} — one grouped query."""
    event_pks = list(event_pks)
    if not event_pks:
        return {}
    from apps.procurement.models.RfxManagement.Events import RfxQuestion

    rows = (RfxQuestion.objects.filter(event_id__in=event_pks, is_scored=True)
            .values_list("event_id").annotate(w=Sum("weight")))
    return {pk: Decimal("10") * (w or ZERO) for pk, w in rows}


def weighted_percent(earned, possible):
    """Earned points as a percentage of possible — None when the event has nothing scoreable
    (a None beats a flattering zero: an unscored questionnaire has no score)."""
    if not possible:
        return None
    return (Decimal(earned or ZERO) / Decimal(possible) * Decimal("100")).quantize(Decimal("0.1"))
