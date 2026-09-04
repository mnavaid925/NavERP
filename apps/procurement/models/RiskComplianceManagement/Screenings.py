"""Procurement 6.17 Risk & Compliance Management — ComplianceScreening + ScreeningHit.

**NavERP.md bullet 1, "Regulatory Compliance Checks".** One row per sanctions / denied-party
lookup run against one supplier, plus one child row per potential match that lookup returned.

**Two verdicts, deliberately two columns.** ``result`` is what the LOOKUP returned (clear /
potential match / confirmed match / error); ``status`` is what a HUMAN decided (pending review /
cleared / escalated / blocked). Collapsing them would lose the only interesting case — a lookup
that returned three potential matches which a compliance officer then adjudicated as false
positives — and that case is precisely the one a regulator asks to see.

**The disposition guard is the point of the model.** :meth:`ComplianceScreening.clear` refuses
while ANY child hit is still ``open``, and it asks the DATABASE
(``self.hits.filter(disposition="open").exists()``), never the cached ``open_hit_count``. The two
counters exist to render a badge; a stale badge must never be able to unlock the gate. They are
recomputed by :meth:`ComplianceScreening.recount_hits`, which the hit views call — so a plain
``.save()`` in a seeder or a test has no hidden side effect.

**Detection suggests; a human decides.** Nothing in this module writes to the scm document spine
or to ``apps.accounting`` (L29): no auto-suspension, no invoice block, no PO hold.
:meth:`ComplianceScreening.block` RECORDS the decision and stamps an existing
``procurement.VendorSuspension`` (6.4) when the operator picked one — 6.17 never invents a second
block flag and never mints the suspension itself.

**No un-clear, no re-open.** A decided screening is evidence. A correction is a NEW screening.

**Retention.** ``RETENTION_YEARS`` keeps a screening for ten years, comfortably past the five-year
floor of OFAC's recordkeeping rule (31 CFR 501.601); :attr:`ComplianceScreening.retention_until`
derives the date and every page states ``RETENTION_NOTE``. There is no purge job by design —
removing compliance evidence is a deliberate act, not a cron.

**Import discipline.** Every cross-app FK is a STRING; ``VendorSuspension`` is only ever imported
inside a method, mirroring the 6.14/6.15 rule.
"""
from datetime import timedelta

from apps.procurement.models._base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------------------------
# The list vocabulary — shared by the screening and by each of its hits
# ---------------------------------------------------------------------------------------------

#: Which list was screened. The ITA Consolidated Screening List (CSL) merges eleven US lists but
#: deliberately EXCLUDES SAM.gov exclusions, so "csl_consolidated" and "sam_exclusions" are two
#: separate values and not a duplication.
LIST_SOURCE_CHOICES = [
    ("ofac_sdn", "OFAC - Specially Designated Nationals (SDN)"),
    ("ofac_other", "OFAC - other lists (SSI / FSE / PLC / CAP)"),
    ("bis_dpl", "BIS - Denied Persons List"),
    ("bis_entity", "BIS - Entity List"),
    ("bis_uvl", "BIS - Unverified List"),
    ("state_isn", "State - ISN sanctions"),
    ("state_debarred", "State - AECA/ITAR debarred parties"),
    ("csl_consolidated", "ITA Consolidated Screening List (CSL)"),
    ("sam_exclusions", "SAM.gov Exclusions (federal debarment)"),
    ("eu_consolidated", "EU consolidated sanctions list"),
    ("un_consolidated", "UN consolidated sanctions list"),
    ("internal_watchlist", "Internal watchlist"),
    ("other", "Other list"),
]

#: WHEN in the buying lifecycle the check was run. The first four are the minimum set a supplier
#: has to clear before money can move.
CHECKPOINT_CHOICES = [
    ("onboarding", "Supplier onboarding"),
    ("pre_award", "Pre-award / before contract"),
    ("pre_po", "Before raising a purchase order"),
    ("pre_payment", "Before payment"),
    ("periodic", "Periodic re-screen"),
    ("ad_hoc", "Ad hoc"),
]

#: HOW the lookup was performed. ``api_feed`` is in the vocabulary but is NOT offered by the form
#: (see ``SELECTABLE_METHODS``): a future list connector writes the same rows with no migration
#: and no second table, while a hand-crafted POST claiming an automated feed ran is refused.
METHOD_CHOICES = [
    ("manual_lookup", "Manual lookup on the official search page"),
    ("file_upload", "List file / CSV compared offline"),
    ("api_feed", "Automated list feed (not yet connected)"),
]

#: The subset a human may choose. The form builds its ``method`` field from exactly this.
SELECTABLE_METHODS = ("manual_lookup", "file_upload")

#: What the LOOKUP returned — machine output, not a decision.
RESULT_CHOICES = [
    ("clear", "Clear - no potential match"),
    ("potential_match", "Potential match(es) returned"),
    ("confirmed_match", "Confirmed match"),
    ("error", "Lookup failed / not completed"),
]

#: What a HUMAN decided — the workflow column. Never on a form; only the three verbs move it.
STATUS_CHOICES = [
    ("pending_review", "Pending review"),
    ("cleared", "Cleared"),
    ("escalated", "Escalated"),
    ("blocked", "Blocked"),
]

#: Still awaiting a decision, in one shape or another.
OPEN_STATUSES = ("pending_review", "escalated")

#: Decided. A terminal screening is evidence: it cannot be edited, deleted or re-opened.
TERMINAL_STATUSES = ("cleared", "blocked")

#: How a hit was adjudicated. "Cleared under licence" is a genuine third outcome and not a fudge:
#: an SDN name is a hard stop, an Entity List name is a licence application, and an Unverified
#: List name is a red flag to resolve — three different lists, three different right answers.
DISPOSITION_CHOICES = [
    ("open", "Open - not yet adjudicated"),
    ("false_positive", "False positive"),
    ("true_match", "True match"),
    ("cleared_with_licence", "Cleared under licence / authorisation"),
]

#: Every disposition that closes a hit. ``open`` is not one of them — that is the whole point.
TERMINAL_DISPOSITIONS = ("false_positive", "true_match", "cleared_with_licence")

#: Which attribute of the supplier the list entry matched on.
MATCH_TYPE_CHOICES = [
    ("name", "Name"),
    ("alias", "Alias / AKA"),
    ("address", "Address"),
    ("tax_id", "Tax / registration ID"),
    ("other", "Other"),
]

#: theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
#: badge-slate (L33). A semantic badge-success / badge-danger renders completely unstyled and
#: passes every test, so the mapping lives here rather than in template {% if %} ladders.
STATUS_CSS = {
    "pending_review": "badge-amber",
    "cleared": "badge-green",
    "escalated": "badge-red",
    "blocked": "badge-red",
}
RESULT_CSS = {
    "clear": "badge-green",
    "potential_match": "badge-amber",
    "confirmed_match": "badge-red",
    "error": "badge-muted",
}
DISPOSITION_CSS = {
    "open": "badge-red",
    "false_positive": "badge-green",
    "true_match": "badge-red",
    "cleared_with_licence": "badge-info",
}

#: How long a screening record is kept. Ten years, comfortably past the five-year floor of OFAC's
#: recordkeeping rule (31 CFR 501.601).
RETENTION_YEARS = 10

#: The fuzzy-match score at or above which a returned entry is worth adjudicating. OFAC's own
#: search tool exposes a score and expects the screener to pick — and to justify — a threshold.
DEFAULT_MATCH_THRESHOLD = 85

#: How long a clear screening stays good for before the supplier is due a re-screen.
DEFAULT_RESCREEN_DAYS = 365

#: Ceiling on one batch re-screen run, so a large workspace cannot mint an unbounded write.
BATCH_PARTY_LIMIT = 500

#: Rendered on the register and on every screening. Stated, never enforced by a job.
RETENTION_NOTE = (
    f"Screening records - the lookup, its hits and every disposition - are retained for "
    f"{RETENTION_YEARS} years (OFAC recordkeeping, 31 CFR 501.601). Nothing here is purged "
    f"automatically: removing compliance evidence is a deliberate act, not a scheduled job."
)

#: Largest value a PositiveSmallIntegerField holds. The two counters are clamped to it so an
#: absurd number of hits degrades a badge rather than raising a driver error on save.
_COUNTER_MAX = 32767


class ComplianceScreening(TenantNumbered):
    """One sanctions / denied-party lookup run against one supplier, and what was decided."""

    NUMBER_PREFIX = "SCR"

    # Re-exposed on the class so views, templates and tests reach the vocabulary through the
    # model rather than importing the module constants a second time.
    LIST_SOURCE_CHOICES = LIST_SOURCE_CHOICES
    CHECKPOINT_CHOICES = CHECKPOINT_CHOICES
    METHOD_CHOICES = METHOD_CHOICES
    SELECTABLE_METHODS = SELECTABLE_METHODS
    RESULT_CHOICES = RESULT_CHOICES
    STATUS_CHOICES = STATUS_CHOICES
    OPEN_STATUSES = OPEN_STATUSES
    TERMINAL_STATUSES = TERMINAL_STATUSES
    STATUS_CSS = STATUS_CSS
    RESULT_CSS = RESULT_CSS
    RETENTION_YEARS = RETENTION_YEARS
    DEFAULT_MATCH_THRESHOLD = DEFAULT_MATCH_THRESHOLD
    DEFAULT_RESCREEN_DAYS = DEFAULT_RESCREEN_DAYS
    BATCH_PARTY_LIMIT = BATCH_PARTY_LIMIT
    RETENTION_NOTE = RETENTION_NOTE

    # PROTECT: deleting a party that carries screening history would erase the evidence that the
    # checks were ever performed. The party must be dealt with, not silently orphaned.
    party = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT, related_name="procurement_screenings",
        help_text="The supplier that was screened")
    list_source = models.CharField(max_length=20, choices=LIST_SOURCE_CHOICES,
                                   default="csl_consolidated",
                                   help_text="Which list the supplier was checked against")
    checkpoint = models.CharField(max_length=16, choices=CHECKPOINT_CHOICES, default="onboarding",
                                  help_text="Where in the buying lifecycle this check was run")
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default="manual_lookup",
                              help_text="How the lookup was performed")
    screened_on = models.DateField(default=timezone.localdate)
    list_as_of = models.DateField(
        null=True, blank=True,
        help_text="The DATA date of the list screened against - a clear result is only as fresh "
                  "as the list behind it")
    reference = models.CharField(
        max_length=120, blank=True,
        help_text="The provider's search / case id, so the lookup can be reproduced")
    result = models.CharField(max_length=16, choices=RESULT_CHOICES, default="clear",
                              help_text="What the lookup returned")
    # editable=False: the workflow column belongs to clear() / escalate() / block(), never to a
    # form. A status that a POST can set is not a decision, it is a text field.
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending_review",
                              editable=False)
    match_threshold = models.PositiveSmallIntegerField(
        default=DEFAULT_MATCH_THRESHOLD,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Fuzzy-match score at or above which an entry was treated as a potential match")
    threshold_rationale = models.CharField(
        max_length=255, blank=True,
        help_text="Why this threshold - a screening standard asks for the rationale, not just "
                  "the number")

    # -- DERIVED display counters. Recomputed by recount_hits(); never a gate. -----------------
    hit_count = models.PositiveSmallIntegerField(default=0, editable=False)
    open_hit_count = models.PositiveSmallIntegerField(default=0, editable=False)

    next_rescreen_on = models.DateField(
        null=True, blank=True,
        help_text="When this supplier is due to be screened again (blank = set on clearing)")
    evidence = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_screenings",
        help_text="The saved search result / list extract this screening rests on")
    # Stamped by block() from an EXISTING 6.4 suspension. 6.17 never creates one and never adds a
    # second block flag - the suspension register is the only place a vendor is blocked.
    suspension = models.ForeignKey(
        "procurement.VendorSuspension", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="screenings", editable=False,
        help_text="The vendor suspension this screening was recorded against, if any")

    screened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_screenings_run", editable=False)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_screenings_decided", editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-screened_on", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_scr_tnt_status_idx"),
            models.Index(fields=["tenant", "party"], name="prc_scr_tnt_party_idx"),
            models.Index(fields=["tenant", "screened_on"], name="prc_scr_tnt_screened_idx"),
            models.Index(fields=["tenant", "next_rescreen_on"], name="prc_scr_tnt_rescreen_idx"),
            models.Index(fields=["tenant", "result"], name="prc_scr_tnt_result_idx"),
        ]
        verbose_name = "Compliance Screening"
        verbose_name_plural = "Compliance Screenings"

    def __str__(self):
        # Guarded on the id: on an UNSAVED instance (a ModelForm re-rendering its own errors)
        # ``self.party`` raises RelatedObjectDoesNotExist, and a validation page must never 500.
        party = self.party if self.party_id else "-"
        return f"{self.number or 'SCR'} · {party} · {self.get_list_source_display()}"

    # -- derived ------------------------------------------------------------------------------

    @property
    def status_css(self):
        return STATUS_CSS.get(self.status, "badge-muted")

    @property
    def result_css(self):
        return RESULT_CSS.get(self.result, "badge-muted")

    @property
    def is_open(self):
        """Still awaiting a decision — the only state in which this row may be amended."""
        return self.status in OPEN_STATUSES

    @property
    def is_terminal(self):
        """Decided. Evidence: no edit, no delete, no re-open."""
        return self.status in TERMINAL_STATUSES

    @property
    def retention_until(self):
        """The date this record may first be considered for removal. No job acts on it."""
        if not self.screened_on:
            return None
        screened_on = self.screened_on
        try:
            return screened_on.replace(year=screened_on.year + RETENTION_YEARS)
        except ValueError:
            # 29 February in a leap year whose target year is not one.
            return screened_on.replace(year=screened_on.year + RETENTION_YEARS, day=28)

    @property
    def has_open_hits(self):
        """LIVE, not the cached counter — the same question :meth:`clear` asks."""
        if not self.pk:
            return False
        return self.hits.filter(disposition="open").exists()

    # -- counters -----------------------------------------------------------------------------

    def recount_hits(self):
        """Recompute the two DISPLAY counters from the child rows.

        Called by the hit views after every create / edit / delete / dispose. These counters
        render a badge and nothing else: :meth:`clear` deliberately re-asks the database rather
        than trusting them, so a counter that drifts costs a wrong number on a page and can never
        unlock the disposition gate.
        """
        if not self.pk:
            return
        # Clamped: PositiveSmallIntegerField tops out at 32767, and a wrong badge is worth less
        # damage than a driver error on save.
        self.hit_count = min(self.hits.count(), _COUNTER_MAX)
        self.open_hit_count = min(self.hits.filter(disposition="open").count(), _COUNTER_MAX)
        self.save(update_fields=["hit_count", "open_hit_count", "updated_at"])

    # -- the three decision verbs ---------------------------------------------------------------
    #
    # Each returns a bool and re-checks its own guard, so a direct POST is as safe as a click.
    # None of them creates, blocks or holds anything on the spine: they record what a human
    # decided. There is deliberately NO un-clear and NO re-open verb — a correction is a new
    # screening, which is what leaves an honest trail.

    @staticmethod
    def _actor(user):
        """The user to stamp, or ``None`` for an anonymous / absent one."""
        return user if getattr(user, "is_authenticated", False) else None

    def clear(self, user, note=""):
        """Record that this screening was cleared. Refuses while ANY hit is undisposed.

        The guard runs a LIVE query rather than reading ``open_hit_count``: the counter is a
        display value maintained by another view, and a stale display value must not be able to
        clear a supplier that still has an unadjudicated sanctions match against it.
        """
        if self.is_terminal:
            return False
        if self.has_open_hits:
            return False
        self.status = "cleared"
        self.decided_by = self._actor(user)
        self.decided_at = timezone.now()
        self.decision_note = (note or "").strip()
        fields = ["status", "decided_by", "decided_at", "decision_note", "updated_at"]
        if self.next_rescreen_on is None and self.screened_on:
            # A clear result is only good for a year; setting the date here is what puts the
            # supplier on the re-screening board instead of quietly out of scope.
            self.next_rescreen_on = self.screened_on + timedelta(days=DEFAULT_RESCREEN_DAYS)
            fields.append("next_rescreen_on")
        self.save(update_fields=fields)
        return True

    def escalate(self, user, note):
        """Send this screening up for a compliance decision. Note required."""
        if self.status != "pending_review":
            return False
        note = (note or "").strip()
        if not note:
            # An escalation with no stated reason is a ticket nobody can action.
            return False
        self.status = "escalated"
        self.decided_by = self._actor(user)
        self.decided_at = timezone.now()
        self.decision_note = note
        self.save(update_fields=["status", "decided_by", "decided_at", "decision_note",
                                 "updated_at"])
        return True

    def block(self, user, note, suspension=None):
        """Record that this supplier was blocked on the strength of this screening. Note required.

        Stamps an EXISTING ``procurement.VendorSuspension`` when the operator picked one. It
        never creates a suspension and never touches the spine: the detail page links out to the
        6.4 register, which is the single place a vendor is actually blocked.
        """
        if self.status not in OPEN_STATUSES:
            return False
        note = (note or "").strip()
        if not note:
            return False
        self.status = "blocked"
        self.decided_by = self._actor(user)
        self.decided_at = timezone.now()
        self.decision_note = note
        fields = ["status", "decided_by", "decided_at", "decision_note", "updated_at"]
        if suspension is not None:
            self.suspension = suspension
            fields.append("suspension")
        self.save(update_fields=fields)
        return True

    def blocking_suspension(self, today=None):
        """The 6.4 register row currently blocking this supplier, or ``None``.

        Imported inside the method (the 6.14/6.15 import-discipline rule) and delegated whole to
        ``VendorSuspension.blocking_for`` so this page and the enforcement point can never
        disagree about whether a vendor is blocked.
        """
        if not self.tenant_id or not self.party_id:
            return None
        from apps.procurement.models.VendorManagement.VendorSuspensions import VendorSuspension

        return VendorSuspension.blocking_for(self.tenant, self.party_id, today=today)

    # -- hygiene ------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}
        tenant_id = getattr(self, "tenant_id", None)

        # Cross-tenant guard on every FK. A narrowed <select> is UX; this is the model-level
        # backstop behind the form's own re-check, and it covers ``suspension`` too — that one is
        # editable=False, so a form never offers it, but block() is handed an object.
        if tenant_id:
            for field in ("party", "evidence", "suspension"):
                fk_id = getattr(self, f"{field}_id", None)
                if not fk_id:
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        if self.list_as_of and self.screened_on and self.list_as_of > self.screened_on:
            # A list cannot have been published after the search that used it.
            errors["list_as_of"] = "The list's data date cannot be after the day it was screened."

        if errors:
            raise ValidationError(errors)


class ScreeningHit(models.Model):
    """One potential match a screening returned, and how it was adjudicated.

    **Tenant-LESS by design** (the ``scm.ComplianceCheck`` / ``AsnLine`` precedent): the parent
    FK IS the scope, so every view resolves a hit as
    ``get_object_or_404(ScreeningHit, pk=pk, screening__tenant=request.tenant)`` and never by pk
    alone. A second tenant column here would be a second answer to the same question.
    """

    DISPOSITION_CHOICES = DISPOSITION_CHOICES
    TERMINAL_DISPOSITIONS = TERMINAL_DISPOSITIONS
    MATCH_TYPE_CHOICES = MATCH_TYPE_CHOICES
    LIST_SOURCE_CHOICES = LIST_SOURCE_CHOICES
    DISPOSITION_CSS = DISPOSITION_CSS

    screening = models.ForeignKey(
        "procurement.ComplianceScreening", on_delete=models.CASCADE, related_name="hits")
    matched_name = models.CharField(max_length=255,
                                    help_text="The name as it appears on the list entry")
    # A CSL search returns entries drawn from eleven different lists, so a hit carries its own
    # source rather than inheriting the parent's.
    matched_list = models.CharField(max_length=20, choices=LIST_SOURCE_CHOICES,
                                    help_text="The list this entry actually came from")
    match_score = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Fuzzy-match score the provider returned, 0-100")
    match_type = models.CharField(max_length=12, choices=MATCH_TYPE_CHOICES, default="name")
    entry_reference = models.CharField(max_length=120, blank=True,
                                       help_text="The list's own entry id")
    program = models.CharField(max_length=120, blank=True,
                               help_text="The sanctions programme the entry sits under")
    country = models.CharField(max_length=120, blank=True,
                               help_text="Adjudication asks whether the geography lines up")
    remarks = models.TextField(blank=True)

    # editable=False: the adjudication belongs to dispose(), never to a form.
    disposition = models.CharField(max_length=24, choices=DISPOSITION_CHOICES, default="open",
                                   editable=False)
    disposition_note = models.TextField(blank=True, editable=False)
    disposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_screening_hits_disposed", editable=False)
    disposed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-match_score", "id"]
        indexes = [
            models.Index(fields=["screening", "disposition"], name="prc_schit_scr_disp_idx"),
        ]
        verbose_name = "Screening Hit"
        verbose_name_plural = "Screening Hits"

    def __str__(self):
        return f"{self.matched_name} ({self.match_score}%)"

    # -- derived ------------------------------------------------------------------------------

    @property
    def disposition_css(self):
        return DISPOSITION_CSS.get(self.disposition, "badge-muted")

    @property
    def is_open(self):
        return self.disposition == "open"

    @property
    def is_above_threshold(self):
        """Whether this entry scored at or above the threshold its screening declared."""
        if not self.screening_id:
            return False
        return self.match_score >= (self.screening.match_threshold or 0)

    # -- adjudication ---------------------------------------------------------------------------

    def dispose(self, user, disposition, note):
        """Adjudicate this hit. From ``open`` only, to a TERMINAL disposition only, note required.

        The note is required for EVERY disposition, ``false_positive`` included: a cleared false
        positive with no recorded reasoning is indistinguishable from a check that was never
        performed, which is the finding a recordkeeping examination actually writes up.
        """
        if not self.is_open:
            return False
        if disposition not in TERMINAL_DISPOSITIONS:
            return False
        note = (note or "").strip()
        if not note:
            return False
        self.disposition = disposition
        self.disposition_note = note
        self.disposed_by = (user if getattr(user, "is_authenticated", False) else None)
        self.disposed_at = timezone.now()
        self.save(update_fields=["disposition", "disposition_note", "disposed_by", "disposed_at"])
        return True

    # -- hygiene ------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}
        # No cross-tenant check is needed or possible here: the parent FK is the scope, and the
        # VIEW is what enforces it (screening__tenant=request.tenant).
        if not (self.matched_name or "").strip():
            errors["matched_name"] = "A hit must name the list entry it matched."
        if errors:
            raise ValidationError(errors)
