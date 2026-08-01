"""SCM 4.12 Contract & Compliance Management — ``SustainabilityAssessment`` [ESG-].

**What this is.** One dated ESG review of ONE trading partner: the four EcoVadis themes (Environment
· Labor & Human Rights · Ethics · Sustainable Procurement), Carbon on its own separate scorecard, the
auditable declarations a customer's compliance team actually asks a supplier for (REACH, RoHS,
conflict minerals, forced labour, deforestation, code of conduct) and the supplier's **declared**
Scope 1/2/3 figures. It is the ethical-sourcing third of 4.12; the licence register
(``TradeLicense``) and the standing-obligation register (``ComplianceRequirement``) are its siblings.

**This is NOT 4.2's ``SupplierRiskAssessment``, and the detail page deliberately links to it.** Risk
asks "what could this supplier do to *us*" and scores four factors 1-5 where the WORST factor drives
the headline. Sustainability asks "how does this supplier behave", scores 0-100 where the themes are
*averaged*, and a partial scorecard is normal rather than suspicious. Same party, two different
questions, two different arithmetics — merging them would force one scale to lie about the other,
which is why 4.12 adds a table instead of columns and why the two sit side by side on screen.

**``carbon_score`` is deliberately OUTSIDE ``THEMES``.** EcoVadis scores Carbon on a separate
scorecard, and so does this model: a strong carbon page must not be able to lift a supplier's medal
over a weak labour theme, and adding a carbon score to an existing assessment must not silently
re-band every row that already has one. It is stored, shown and filtered — it just does not vote.

**Two columns are stored derivations; everything else derived is a property.** ``overall_score`` and
``rating`` are real columns because the list page *filters and orders* on the medal and there is an
index behind it — you cannot index a property, and "show me every supplier that is bronze or unrated"
is the whole job of that page. They are ``editable=False`` and written **only** by
:meth:`SustainabilityAssessment.recompute_rating`, which ``save()`` calls on every path, so no
seeder, shell session, crafted POST or test can store a hand-set headline and no two assessors can
disagree about the medal (the ``SupplierRiskAssessment.recompute_risk_level`` posture). By contrast
``maturity_level`` and ``total_declared_tco2e`` are **properties**: nothing filters or sorts on them,
so a stored copy would buy no query and would need a writer on every edit path — the day one is
missed the page prints a confident, wrong number that nobody can tell from a right one. A derived
figure earns a column only when the database has to *search* it.

**Unset is not zero.** A real scorecard often covers only some themes, so the theme scores are
nullable and the mean is taken over the themes that were actually scored. Counting an unanswered
theme as 0 would punish a supplier for a question nobody asked; reporting 0 for an assessment with
nothing scored would say "assessed, terrible" when the truth is "not assessed". ``overall_score`` is
therefore ``None`` — not ``ZERO`` — in that case, and so are ``maturity_level`` and
``total_declared_tco2e`` (the 4.11 ``projected_stockout_count`` lesson, applied at model level).

**Why ``party`` CASCADEs while the link-outs are SET_NULL.** The assessment is *about* the party — a
scorecard for a supplier that no longer exists is an orphan nobody can act on, so it goes with it
(the ``SupplierRiskAssessment.party`` precedent, same on-delete). ``document`` and ``assessed_by``
are link-*outs*: deleting the evidence file, or removing the account of the person who recorded the
review, must never delete the dated compliance record itself — that record IS what an auditor asks
for, and it has to survive the housekeeping around it. Hence ``SET_NULL`` for both.

**Why the year is capped.** ``carbon_reporting_year`` is bounded 2000-2100 because a bare
``PositiveIntegerField`` accepts 4294967295 on MariaDB. The carbon report groups the declared scopes
*by* that year, so an absurd value is not a wrong number in one cell — it is a rendering/looping
hazard downstream, and an uncaught one is a 500 rather than a validation error. Same reasoning as
every capped day-count column in this app (the 4.10 finding); this one just happens to count years.

**``status`` stays ON the form** — unlike ``TradeDocument`` / ``TradeLicense``, which are moved by
verb routes and by date-driven rollers. There are no verbs here and nothing rolls this status, so it
is the assessor's own record state (the ``SupplierRiskAssessment.status`` precedent). That means a
row can read ``validated`` while :meth:`is_expired` is already ``True``: the date is the truth, the
status is the human's note about their own work, and the page shows both. 4.12 deliberately does not
grow a third expiry mechanism — anything that needs a recurring proof cycle (an annual code-of-
conduct re-signature, a REACH re-declaration) becomes a ``ComplianceRequirement`` row with the
matching framework, which already owns due dates, recurrence and evidence.
"""
from decimal import ROUND_HALF_UP

from apps.scm.models._base import *  # noqa: F401,F403


#: ONE ladder, read by both the stored medal and the derived maturity level: (floor, medal,
#: maturity). EcoVadis publishes its medals and its maturity ladder on the same cut points, and
#: holding them in a single table is what stops a platinum row from printing "advanced" after
#: somebody edits one of two parallel if-chains and forgets the other.
_SCORE_BANDS = (
    (85, "platinum", "leader"),
    (65, "gold", "advanced"),
    (45, "silver", "intermediate"),
    (25, "bronze", "beginner"),
)

#: Below the lowest band — and also the answer when NOTHING was scored. "none" is the absence of a
#: medal rather than a bad one, which is why its badge is muted and not red.
_UNRATED = ("none", "insufficient")


def _band_for(score):
    """``(medal, maturity)`` for a 0-100 overall score; :data:`_UNRATED` when ``score`` is ``None``.

    Kept module-private and stateless so ``recompute_rating`` (which writes a column) and
    ``maturity_level`` (which writes nothing) cannot drift apart.
    """
    if score is None:
        return _UNRATED
    for floor, medal, maturity in _SCORE_BANDS:
        if score >= floor:
            return medal, maturity
    return _UNRATED


class SustainabilityAssessment(TenantNumbered):
    """A dated ESG / ethical-sourcing assessment of one trading partner [ESG-]."""

    NUMBER_PREFIX = "ESG"

    # The four have different evidentiary weight and the page says so: a supplier's own
    # questionnaire (IntegrityNext) is not an EcoVadis rating and neither is an on-site audit.
    SOURCE_CHOICES = [
        ("self_assessment", "Self-assessment"),
        ("third_party_rating", "Third-party rating"),
        ("desk_review", "Desk review"),
        ("onsite_audit", "On-site audit"),
    ]
    RATING_CHOICES = [
        ("none", "Not rated"),
        ("bronze", "Bronze"),
        ("silver", "Silver"),
        ("gold", "Gold"),
        ("platinum", "Platinum"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("validated", "Validated"),
        ("expired", "Expired"),
    ]

    #: Colour-named badge classes — ``theme.css`` has NO ``badge-success`` / ``-warning`` /
    #: ``-danger`` (L33). Kept beside the choices so every page renders the same colour and a badge
    #: colour is decided in exactly one place (the ``SupplyChainAlert.STATUS_CSS`` precedent).
    RATING_CSS = {"platinum": "badge-info", "gold": "badge-green", "silver": "badge-slate",
                  "bronze": "badge-amber", "none": "badge-muted"}
    STATUS_CSS = {"draft": "badge-slate", "submitted": "badge-amber", "validated": "badge-green",
                  "expired": "badge-muted"}

    #: The four EcoVadis themes, and the ONLY inputs to the overall score. ``carbon_score`` is
    #: absent on purpose — see the module docstring.
    THEMES = ("environment_score", "labor_human_rights_score", "ethics_score",
              "sustainable_procurement_score")

    # --- who was assessed, when ----------------------------------------------------------------
    party = models.ForeignKey(
        "core.Party", on_delete=models.CASCADE, related_name="scm_sustainability_assessments",
        help_text="The supplier or carrier this assessment is about")
    assessment_date = models.DateField(help_text="The date the assessment reflects")
    valid_until = models.DateField(
        null=True, blank=True,
        help_text="Ratings are re-issued annually — blank means no stated validity period")

    # --- where the finding came from -------------------------------------------------------------
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default="self_assessment",
        help_text="How this was established — the four carry very different evidentiary weight")
    # Free text on purpose: there is no rating-agency master in this repo and inventing one would be
    # a fake reference table. clean() still insists it is filled for a third-party rating.
    provider = models.CharField(
        max_length=120, blank=True,
        help_text="EcoVadis, IntegrityNext, our own audit team")
    # ON the form, unlike TradeDocument.status / TradeLicense.status: no verb route and no roller
    # moves this, so it is the assessor's note about their own work rather than a workflow the
    # system drives (the SupplierRiskAssessment.status precedent). See the module docstring for why
    # `expired` here can legitimately disagree with is_expired().
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="draft",
        help_text="Where this record stands — the validity date is what actually expires it")

    # --- the scorecard ---------------------------------------------------------------------------
    # All nullable: a real scorecard routinely covers only some themes, and an unanswered theme is
    # not a zero. Bounded 0-100 at the field so a crafted POST cannot store a 900-point theme that
    # would drag the derived medal off the ladder.
    environment_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="0-100 — energy, emissions, water, waste, biodiversity")
    labor_human_rights_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="0-100 — working conditions, health & safety, human rights")
    ethics_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="0-100 — corruption, anti-competitive practice, information security")
    sustainable_procurement_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="0-100 — how this supplier assesses ITS own suppliers")
    carbon_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="0-100 on the separate Carbon scorecard — shown next to the medal, but it does "
                  "not vote on it")

    # DERIVED, never hand-set — written only by recompute_rating(), which save() always calls. Both
    # are columns rather than properties because the list page filters and orders on the medal.
    overall_score = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    rating = models.CharField(max_length=8, choices=RATING_CHOICES, default="none", editable=False)

    strengths = models.TextField(blank=True, help_text="What this supplier does well, per theme")
    improvement_areas = models.TextField(
        blank=True, help_text="What was asked for, per theme — the basis of the next review")

    # --- declarations ----------------------------------------------------------------------------
    # Flags, not dated certificates. This records THAT a declaration is on file; anything that needs
    # a recurring proof cycle becomes a ComplianceRequirement row with the matching framework, which
    # already owns due dates, recurrence and evidence. 4.12 does not build a third expiry mechanism.
    conflict_minerals_declared = models.BooleanField(
        default=False, help_text="3TG / CMRT declaration on file")
    reach_declared = models.BooleanField(default=False, help_text="EU REACH / SVHC declaration")
    rohs_declared = models.BooleanField(default=False, help_text="EU RoHS declaration")
    forced_labor_attested = models.BooleanField(
        default=False, help_text="UFLPA / modern-slavery attestation")
    deforestation_declared = models.BooleanField(
        default=False, help_text="EUDR / deforestation-free declaration")
    code_of_conduct_signed = models.BooleanField(
        default=False, help_text="Our supplier code of conduct is signed")

    # --- supplier-DECLARED carbon ----------------------------------------------------------------
    # Reported by the supplier, never computed by us: the carbon report renders these clearly
    # labelled as declared and keeps them apart from the freight emissions it works out itself from
    # 4.6's shipments. Non-negative, and to 3dp because tCO2e is quoted in tonnes.
    scope1_tco2e = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(ZERO)],
        help_text="Declared direct emissions, tonnes CO2e")
    scope2_tco2e = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(ZERO)],
        help_text="Declared purchased-energy emissions, tonnes CO2e")
    scope3_tco2e = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(ZERO)],
        help_text="Declared value-chain emissions, tonnes CO2e")
    # Capped: a bare PositiveIntegerField accepts 4294967295, and the carbon report groups BY this
    # column — see the module docstring.
    carbon_reporting_year = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(2000), MaxValueValidator(2100)],
        help_text="The reporting year those three figures cover")

    # --- provenance ------------------------------------------------------------------------------
    # System stamp (L22): written from request.user by the create view, never offered on the form.
    # SET_NULL so retiring the assessor's account cannot delete the assessment.
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="scm_sustainability_assessments_recorded",
        help_text="Who recorded this assessment")
    document = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scm_sustainability_assessments",
        help_text="The scorecard, certificate or audit report behind this row")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-assessment_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # The party page and the 4.2 risk cross-link both enter by (tenant, party).
            models.Index(fields=["tenant", "party"], name="scm_esg_tnt_party_idx"),
            models.Index(fields=["tenant", "status"], name="scm_esg_tnt_status_idx"),
            # The reason `rating` is a column and not a property: the list page filters on it.
            models.Index(fields=["tenant", "rating"], name="scm_esg_tnt_rating_idx"),
            models.Index(fields=["tenant", "valid_until"], name="scm_esg_tnt_valid_idx"),
        ]

    def __str__(self):
        party = self.party.name if self.party_id else "unassigned"
        return f"{self.number or 'ESG'} · {party} ({self.get_rating_display()})"

    def save(self, *args, **kwargs):
        """Derive the headline before every write — this is what makes ``recompute_rating`` the
        ONLY writer of ``overall_score`` / ``rating`` on EVERY path (form, seeder, shell, test).

        The recursion is one level deep and terminates: ``recompute_rating(save=True)`` calls back
        into here, and that inner pass runs ``recompute_rating(save=False)``, which touches nothing
        else. Recomputing twice is free — the derivation is pure and idempotent.
        """
        self.recompute_rating(save=False)
        # A caller passing update_fields=["environment_score"] would otherwise persist the new theme
        # and leave the stale medal behind — the derived pair has to ride along with its inputs (the
        # ProductionTimeLog.duration_minutes precedent). An EMPTY list stays empty: Django reads that
        # as "skip the write entirely", and widening it would resurrect a save the caller cancelled.
        update_fields = kwargs.get("update_fields")
        if update_fields:
            kwargs["update_fields"] = list(dict.fromkeys(
                list(update_fields) + ["overall_score", "rating"]))
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        # THE GUARD. The form's querysets are tenant-scoped, but that is UX: a narrowed dropdown has
        # never held against a crafted POST (L39 §2). Skipped while the instance has no tenant yet —
        # `self.tenant` would raise RelatedObjectDoesNotExist on the non-nullable FK rather than
        # return None. The defaulted getattr below does the same for a pointer whose row went away:
        # RelatedObjectDoesNotExist subclasses AttributeError, so it degrades to None here instead
        # of 500-ing inside validation.
        if self.tenant_id is not None:
            for field in ("party", "document"):
                if getattr(self, f"{field}_id", None) is None:
                    continue
                related = getattr(self, field, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({field: "That record belongs to another workspace."})

        # A validity window that closes before it opens makes is_expired() true from the day the row
        # is created, which reads as "this supplier's rating lapsed" when it never began.
        if self.valid_until and self.assessment_date and self.valid_until < self.assessment_date:
            raise ValidationError(
                {"valid_until": "The validity date cannot fall before the assessment date."})

        # An unattributed third-party rating is not evidence: the whole reason that source outranks
        # a self-assessment is that somebody independent put their name to it.
        if self.source == "third_party_rating" and not (self.provider or "").strip():
            raise ValidationError(
                {"provider": "A third-party rating has to say whose rating it is — name the "
                             "provider."})

    # ---------------------------------------------------------------------------------------------
    # Behaviour
    # ---------------------------------------------------------------------------------------------
    def recompute_rating(self, save=True):
        """Derive ``overall_score`` (mean of the themes that were SCORED) and the medal from it.

        Only the set themes take part, and ``None`` — never ``ZERO`` — is the answer when none of
        them is. A partial scorecard is the normal case, so averaging in an unanswered theme as 0
        would quietly convert "we did not ask" into "they failed", and a blanket 0 would hand a
        never-scored supplier a confident bad number that looks exactly like a measured one.

        Rounding is explicit half-up rather than ``Decimal``'s default banker's rounding, because
        the medal cut-offs are hard edges: with ROUND_HALF_EVEN a mean of 64.5 lands on gold and
        65.5 lands on gold too, while 84.5 quietly does not become platinum. Half-up makes the
        boundary one rule the whole way up the ladder.
        """
        scored = [value for value in (getattr(self, theme) for theme in self.THEMES)
                  if value is not None]
        if scored:
            mean = Decimal(sum(scored)) / Decimal(len(scored))
            self.overall_score = int(mean.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        else:
            self.overall_score = None
        self.rating = _band_for(self.overall_score)[0]
        if save:
            self.save(update_fields=["overall_score", "rating", "updated_at"])

    def is_expired(self, today=None):
        """Has the stated validity period run out? ``today`` defaults to the local date.

        Deliberately a method with a default rather than a stored flag: nothing here rolls statuses
        (there is no ``refresh_status`` on this model), so a persisted "expired" boolean would be
        wrong from the morning after it was written until somebody happened to save the row again.
        A Django template calls a zero-argument callable for you, so ``{{ obj.is_expired }}`` works;
        the parameter exists so the report and the tests can ask about a date that is not today.

        An assessment with no ``valid_until`` never expires — that is a rating with no stated
        validity period, not one that lapsed.
        """
        if self.valid_until is None:
            return False
        return self.valid_until < (today or timezone.localdate())

    # ---------------------------------------------------------------------------------------------
    # Derived — nothing below is stored.
    # ---------------------------------------------------------------------------------------------
    @property
    def maturity_level(self):
        """EcoVadis' own ladder — ``insufficient | beginner | intermediate | advanced | leader``.

        ``None`` when no theme was scored. "Insufficient" is a *verdict* (the bottom rung, 0-24) and
        an assessment that measured nothing has not earned one, so the page prints "—" instead. The
        stored ``rating`` cannot make that distinction: it is a non-null column whose "none" value
        has to serve both "no medal" and "not measured".
        """
        if self.overall_score is None:
            return None
        return _band_for(self.overall_score)[1]

    @property
    def total_declared_tco2e(self):
        """The declared scopes that are set, added up — ``None`` when none of the three is.

        A property, not a column: nothing filters or sorts on this total, so storing it would buy no
        query and would need a writer on every path that touches a scope figure. ``None`` rather
        than ``ZERO`` keeps "this supplier reported nothing" visibly different from "this supplier
        reported zero emissions", which is the one distinction a carbon page cannot afford to lose.
        """
        declared = [value for value in (self.scope1_tco2e, self.scope2_tco2e, self.scope3_tco2e)
                    if value is not None]
        if not declared:
            return None
        return sum(declared, ZERO)

    @property
    def rating_css(self):
        """Colour-named badge class for ``rating`` — ``theme.css`` has no semantic badge names."""
        return self.RATING_CSS.get(self.rating, "badge-muted")

    @property
    def status_css(self):
        """Colour-named badge class for ``status``."""
        return self.STATUS_CSS.get(self.status, "badge-slate")
