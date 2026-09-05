"""Procurement 6.16 Supplier Performance & Evaluation — SupplierFeedback.

**What it is.** The NavERP.md "360-degree feedback collection" bullet, at its natural grain: one
row is ONE respondent's rating of ONE supplier for ONE period, optionally against ONE KPI. Ask
six people about a supplier and you get six rows, not one averaged opinion — because the average
is a computation (``apps.procurement.performance.survey_aggregate``) and the rows are the
evidence it stands on.

**``respondent_kind`` is the whole 360.** ``internal`` is what WE think of the supplier;
``supplier_self`` is what the supplier thinks of itself, filed on its behalf under
``respondent_name``. One CharField, not a second table — and that single column is what makes the
perception-gap board possible: bucket the same period's submitted rows by kind, take each side's
importance-weighted mean, and the delta is the conversation worth having. A second model here
would have bought nothing but a join and two places for the rating scale to drift apart.

**Only ``internal`` responses feed a survey KPI.** ``survey_aggregate`` filters
``respondent_kind="internal"`` deliberately — a supplier's own self-assessment is worth reading
next to our score, never worth folding INTO it.

**``importance`` weights, it does not gate.** A response filed at importance 0 contributes
nothing to the weighted mean and is still counted as a respondent, so a page can honestly say
"eight people answered" while reporting that only six of them moved the number. Silently dropping
the zero-weight rows would make the respondent count a lie.

**Uniqueness lives in :meth:`SupplierFeedback.clean`, NOT in ``unique_together``.** The natural
key is ``(supplier, scorecard, kpi, respondent)`` and three of those four columns are NULLABLE.
SQL compares NULLs as DISTINCT, so a database constraint over them would let a second "ad-hoc, no
KPI, external respondent" row for the same supplier straight through while looking like it was
preventing exactly that (the ``KpiSnapshot`` blank-vs-NULL trap). The explicit ``.exists()``
probe below passes the raw ``*_id`` values — ``None`` included — so Django emits ``IS NULL`` and
the rule actually holds.

**Status is workflow-controlled, never typed.** ``requested`` on create, then ``submitted`` /
``declined`` / ``expired`` through the three POST verbs in
``views/SupplierPerformanceEvaluation/SupplierFeedback.py``. Every choice is reachable — a status
nothing can ever set is a lie in a dropdown.

**Import discipline.** This module imports the shared toolkit from
``apps.procurement.models._base`` and its own sub-module sibling (``SupplierKpi``, from that
entity MODULE rather than from ``apps.procurement.models``) and NOTHING else at module top. The
cross-app reads (``core.Party`` and ``scm.SupplierScorecard`` in ``clean()``) happen inside the
method that needs them — the ``ScorecardKpiScores.py`` precedent — because this sub-package is
not wired into ``models/__init__.py`` until the Integrate phase and a module-level sibling-app
import that runs while ``apps.procurement.models`` is still initialising is exactly how an import
cycle gets shipped.
"""
from apps.procurement.models._base import *  # noqa: F401,F403

# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``apps.procurement.models`` — the package __init__ re-export block lands at Integrate.
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi


#: Which side of the relationship answered. This ONE column is the 360 — see the module
#: docstring. ``survey_aggregate`` reads only ``internal``; the perception-gap board reads both.
RESPONDENT_KIND_CHOICES = [("internal", "Internal"), ("supplier_self", "Supplier self-assessment")]

#: The respondent's function. A buyer, a quality engineer and an AP clerk see different suppliers
#: through the same PO, and being able to slice the survey by function is what stops one loud
#: department speaking for the whole business.
FUNCTION_CHOICES = [
    ("procurement", "Procurement"), ("quality", "Quality"), ("operations", "Operations"),
    ("finance", "Finance"), ("engineering", "Engineering"), ("logistics", "Logistics"),
    ("other", "Other"),
]

#: The 1-5 scale with the label spelled out, so a "3" cannot mean "average" to one respondent and
#: "barely acceptable" to the next. The values are INTEGERS, so this list is not a ``crud_list``
#: filter — it rides the register as a legend only.
RATING_CHOICES = [
    (1, "1 — Poor"), (2, "2 — Below expectations"), (3, "3 — Meets expectations"),
    (4, "4 — Above expectations"), (5, "5 — Excellent"),
]

#: The response lifecycle. ``requested`` is the only value a create can produce; the other three
#: are reachable ONLY through the submit / decline / expire POST verbs. No dead choices.
STATUS_CHOICES = [
    ("requested", "Requested"), ("submitted", "Submitted"),
    ("declined", "Declined"), ("expired", "Expired"),
]

#: L33 — theme.css ships COLOUR-NAMED badge classes only. badge-success / -warning / -danger do
#: not exist and render completely unstyled, so every mapping here names a colour.
STATUS_CSS = {"requested": "badge-amber", "submitted": "badge-green",
              "declined": "badge-muted", "expired": "badge-slate"}

#: Rating -> badge colour. 1-2 is a problem, 3 is a warning, 4-5 is fine.
RATING_CSS = {1: "badge-red", 2: "badge-red", 3: "badge-amber",
              4: "badge-green", 5: "badge-green"}

#: Which side answered, as a badge colour. Internal is neutral; a self-assessment is called out.
KIND_CSS = {"internal": "badge-slate", "supplier_self": "badge-info"}

#: rating -> 0-100 for the survey aggregate. The ONE conversion: ``survey_aggregate`` and the
#: perception-gap board both go through :meth:`SupplierFeedback.score_value`, so a 4 can never be
#: worth 75 on one page and 80 on another.
RATING_SCORE_MAP = {1: 0, 2: 25, 3: 50, 4: 75, 5: 100}


class SupplierFeedback(TenantNumbered):
    """One 360 response [SFB-] — who was asked, about what, and what they said."""

    NUMBER_PREFIX = "SFB"

    # Re-exported through the class so templates, forms and views can reach them off the model
    # (``SupplierFeedback.STATUS_CHOICES``), mirroring SupplierKpi and VendorSuspension. The
    # module-level names stay the definition; these are aliases, never a second copy to drift
    # from.
    RESPONDENT_KIND_CHOICES = RESPONDENT_KIND_CHOICES
    FUNCTION_CHOICES = FUNCTION_CHOICES
    RATING_CHOICES = RATING_CHOICES
    STATUS_CHOICES = STATUS_CHOICES
    STATUS_CSS = STATUS_CSS
    RATING_CSS = RATING_CSS
    KIND_CSS = KIND_CSS
    RATING_SCORE_MAP = RATING_SCORE_MAP

    supplier = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT,
        related_name="procurement_supplier_feedback")
    scorecard = models.ForeignKey(
        "scm.SupplierScorecard", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_feedback",
        help_text="The period document this response belongs to. Blank = ad-hoc feedback")
    kpi = models.ForeignKey(
        "procurement.SupplierKpi", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="feedback",
        help_text="Set = this response feeds that survey KPI. Blank = general commentary")
    period_start = models.DateField()
    period_end = models.DateField()
    respondent_kind = models.CharField(
        max_length=16, choices=RESPONDENT_KIND_CHOICES, default="internal")
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_feedback_given")
    respondent_name = models.CharField(
        max_length=160, blank=True,
        help_text="Required for a supplier self-assessment, which has no internal user account")
    respondent_function = models.CharField(
        max_length=16, choices=FUNCTION_CHOICES, default="procurement")
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    importance = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="How much this respondent's rating counts in the survey aggregate, 0-10")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="requested")
    due_date = models.DateField(null=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="procurement_feedback_requested")
    requested_at = models.DateTimeField(default=timezone.now, editable=False)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "supplier"], name="prc_sfb_tnt_supp_idx"),
            models.Index(fields=["tenant", "status"], name="prc_sfb_tnt_status_idx"),
            models.Index(fields=["tenant", "scorecard"], name="prc_sfb_tnt_scr_idx"),
            # The register's DEFAULT SORT, covered. None of the three above matches
            # ``ordering``, so every page of the 360 register was a filesort over the whole
            # tenant partition: measured 113 ms -> 822 ms at 50,028 rows and the perception-gap
            # board 91 ms -> 384 ms, both with the query count FLAT and ``EXPLAIN`` reporting
            # ``Using where; Using filesort``. Same shape, and the same reason, as
            # ``prc_sks_tnt_cat_name_idx`` on SupplierKpiScore.
            models.Index(fields=["tenant", "-period_end", "-id"],
                         name="prc_sfb_tnt_period_idx"),
        ]
        verbose_name = "Supplier Feedback"
        verbose_name_plural = "Supplier Feedback"

    def __str__(self):
        return f"{self.number or 'SFB'} · {self.supplier_id and self.supplier.name}"

    def clean(self):
        """Five rules, collected so a form shows every problem at once rather than the first.

        1. **One response per ``(supplier, scorecard, kpi, respondent)``.** Deliberately NOT a
           ``unique_together``: three of those four columns are nullable and SQL compares NULLs as
           distinct, so the constraint would look like it was preventing duplicates while letting
           every ad-hoc one through. The probe below passes the raw ``*_id`` values, ``None``
           included, so Django emits ``IS NULL`` and the rule actually holds.
        2. **A ``kpi``, when set, must be a SURVEY KPI.** Attaching a response to a derived KPI
           files an opinion somewhere nothing will ever read it — generate computes that KPI from
           the transaction spine and never looks at feedback.
        3. **The period must not end before it starts.**
        4. **A submitted response needs a rating** — "submitted, unrated" is not an answer.
        5. **Same-tenant guards, and the self-assessment conjunction.** A supplier
           self-assessment is filed on the supplier's behalf, so it carries a NAME and no
           internal user account.

        Every FK is resolved with an ``_id`` guard plus an explicit queryset lookup, never
        ``self.kpi.tenant_id`` — the two-arg ``getattr`` form raises
        ``RelatedObjectDoesNotExist`` on an unsaved instance whose FK was not set, which 500'd a
        live add page once already (the ``VendorSuspension.clean()`` precedent). The whole method
        is skipped while ``tenant_id`` is unset: there is nothing to compare against yet.
        """
        super().clean()
        errors = {}

        # Rule 1 — the real uniqueness rule. See the docstring for why it is not a constraint.
        if self.tenant_id and self.supplier_id:
            duplicate = (type(self).objects
                         .exclude(pk=self.pk)
                         .filter(tenant_id=self.tenant_id, supplier_id=self.supplier_id,
                                 scorecard_id=self.scorecard_id, kpi_id=self.kpi_id,
                                 respondent_id=self.respondent_id)
                         .exists())
            if duplicate:
                errors["respondent"] = ("This respondent has already answered for that supplier, "
                                        "period document and KPI.")

        # Rule 2 — a survey response belongs on a survey KPI. Resolved by an explicit values_list
        # rather than ``self.kpi.source``, for the same RelatedObjectDoesNotExist reason.
        if self.tenant_id and self.kpi_id:
            source = (SupplierKpi.objects
                      .filter(pk=self.kpi_id, tenant_id=self.tenant_id)
                      .values_list("source", flat=True).first())
            if source is not None and source != "survey":
                errors["kpi"] = "A derived KPI is not a survey question."

        # Rule 3 — a window has to be a window.
        if (self.period_start is not None and self.period_end is not None
                and self.period_end < self.period_start):
            errors["period_end"] = "The period ends before it starts."

        # Rule 4 — a submitted response with no rating measures nothing.
        if self.status == "submitted" and self.rating is None:
            errors["rating"] = "A submitted response needs a rating."

        # Rule 5a — same-tenant guards on all three FKs into another table.
        if self.tenant_id and self.supplier_id:
            # Cross-app read, local by design — see the module docstring.
            from apps.core.models import Party
            if not Party.objects.filter(pk=self.supplier_id,
                                        tenant_id=self.tenant_id).exists():
                errors["supplier"] = "That record belongs to another workspace."
        if self.tenant_id and self.scorecard_id:
            from apps.scm.models import SupplierScorecard
            if not SupplierScorecard.objects.filter(pk=self.scorecard_id,
                                                    tenant_id=self.tenant_id).exists():
                errors["scorecard"] = "That record belongs to another workspace."
        if self.tenant_id and self.kpi_id:
            if not SupplierKpi.objects.filter(pk=self.kpi_id,
                                              tenant_id=self.tenant_id).exists():
                errors["kpi"] = "That record belongs to another workspace."

        # Rule 5b — the self-assessment conjunction. Stated LAST on purpose: it and rule 1 both
        # key on "respondent", and when both fire the more actionable message should survive.
        if self.respondent_kind == "supplier_self":
            if self.respondent_id:
                errors["respondent"] = ("A supplier self-assessment is not filed by an internal "
                                        "user.")
            if not self.respondent_name:
                errors["respondent_name"] = ("Name the person who answered on the supplier's "
                                             "side.")

        if errors:
            raise ValidationError(errors)

    def score_value(self):
        """``Decimal | None`` — this response on the 0-100 scale the survey aggregate averages.

        ``None`` when there is no rating: an unanswered request is not a zero, and scoring one
        would quietly punish a supplier for somebody's unopened inbox.
        """
        if self.rating is None:
            return None
        return Decimal(RATING_SCORE_MAP[self.rating])

    @property
    def status_css(self):
        """The theme class for this response's status. Colour-named only (L33)."""
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def rating_css(self):
        """The theme class for this response's rating. Colour-named only (L33)."""
        return self.RATING_CSS.get(self.rating, "badge-slate")

    @property
    def kind_css(self):
        """The theme class for which side answered. Colour-named only (L33)."""
        return self.KIND_CSS.get(self.respondent_kind, "badge-slate")

    @property
    def is_overdue(self):
        """True when a still-requested response is past its due date.

        Only ``requested`` can be overdue: a declined or expired request has been answered, in
        the sense that nobody is waiting on it any more. Drives the register's ``overdue`` stat.
        """
        return bool(self.due_date and self.status == "requested"
                    and self.due_date < timezone.localdate())
