"""Procurement 6.16 Supplier Performance & Evaluation — SupplierImprovementPlan.

**What it is.** The NavERP.md "Performance Improvement Plans (PIP)" bullet: the work that
follows a bad number. A scorecard says *what* happened; this row says what was agreed about it,
by when, who owns it on both sides, and — at the end — whether it actually worked.

**Plan grain only, on purpose.** One row is ONE plan. There is no action list, no milestone
table and — emphatically — no fake action list crammed into a TextField. ``corrective_actions``
is the narrative of what was agreed, not a pretend child table; a real
``SupplierImprovementAction`` child can be added later without reshaping a single column here,
because nothing in this model assumes the actions are text.

**``escalated_suspension`` closes the loop to the EXISTING block register.** When a plan fails,
the supplier gets blocked through :class:`~apps.procurement.models.VendorManagement.VendorSuspensions.VendorSuspension`
— 6.4's register, with its own request → decide → lift lifecycle, its own audit trail and the
enforcement that ``scm.purchaseorder_approve`` / ``_send`` and the vendor portal already consult.
This field is a POINTER to that row, never a second blocking mechanism: a boolean ``is_blocked``
here would be a second source of truth for "may this vendor receive a PO?", and the two would
disagree within a quarter. ``clean()`` therefore insists the suspension is both same-tenant AND
against the same supplier — an escalation that points at somebody else's block is worse than no
pointer at all.

**Two close dates and ONE rule that reads them.** ``target_close_date`` is what was agreed;
``extended_close_date`` is a granted extension and must fall strictly after it. Every "is this
late?" question goes through :attr:`effective_close_date`, so the register's overdue stat, the
row badge and the detail page cannot drift into three different definitions of late. An
extension that could be set on or before the original target would be a way to quietly re-write
history, so it is refused.

**Status is workflow-controlled, never typed; every choice is reachable.** ``draft`` on create,
then ``active`` → ``monitoring`` → ``closed`` through the verbs in
``views/SupplierPerformanceEvaluation/SupplierImprovementPlans.py``, with ``cancelled`` reachable
from any of the three open states. ``outcome`` is written by the close verb alone and covers all
four endings — ``successful``, ``extended``, ``failed`` and ``escalated``. A status or an outcome
nothing can ever set is a lie in a dropdown, so there are none here.

**``acknowledged_*`` and ``verified_*`` are stamps, not fields.** Acknowledgement records that
the supplier was told; verification records who signed off the closure. Both are
``editable=False`` and written only by their verb (L22) — a stamp anybody could type over stops
being evidence of anything, which is the whole reason to keep it.

**Import discipline.** This module imports the shared toolkit from ``apps.procurement.models._base``
and NOTHING else at module top — not even its own sub-module siblings, because it needs none of
them: ``kpi`` and ``scorecard`` are declared as STRING references. The three cross-table reads in
``clean()`` (``core.Party``, ``scm.SupplierScorecard``, ``procurement.VendorSuspension``) happen
inside the method that needs them, so this module imports cleanly on its own and cannot start a
cycle while ``apps.procurement.models`` is still initialising (the ``ScorecardKpiScores`` /
``SupplierFeedback`` precedent).
"""
from apps.procurement.models._base import *  # noqa: F401,F403


#: How bad it is. Drives triage, the register's badge and nothing automatic — a critical plan is
#: not a different workflow, it is the same workflow somebody reads first.
SEVERITY_CHOICES = [("minor", "Minor"), ("major", "Major"), ("critical", "Critical")]

#: The plan lifecycle. ``draft`` is the only value a create can produce; the other four are
#: reachable ONLY through the five POST verbs (activate / monitor / close / cancel — acknowledge
#: leaves the status alone by design). No dead choices.
STATUS_CHOICES = [
    ("draft", "Draft"), ("active", "Active"), ("monitoring", "Monitoring"),
    ("closed", "Closed"), ("cancelled", "Cancelled"),
]

#: How it ended. Written by the close verb from its POST body and required there, so all four
#: are reachable. ``extended`` is an honest ending for a plan that was closed and re-opened as a
#: new one; ``escalated`` is the one that points at a VendorSuspension.
OUTCOME_CHOICES = [
    ("successful", "Successful"), ("extended", "Extended"),
    ("failed", "Failed"), ("escalated", "Escalated to suspension"),
]

#: L33 — theme.css ships COLOUR-NAMED badge classes only. badge-success / -warning / -danger do
#: not exist and render completely unstyled, so every mapping here names a colour.
SEVERITY_CSS = {"minor": "badge-slate", "major": "badge-amber", "critical": "badge-red"}
STATUS_CSS = {"draft": "badge-slate", "active": "badge-amber", "monitoring": "badge-info",
              "closed": "badge-green", "cancelled": "badge-muted"}
OUTCOME_CSS = {"successful": "badge-green", "extended": "badge-amber",
               "failed": "badge-red", "escalated": "badge-red"}

#: Statuses a plan is still being worked in — the register's stats and the overdue calculation
#: read this ONE tuple, so "still open" cannot mean one thing on the list page and another on the
#: row. A closed or cancelled plan is never overdue: nobody is waiting on it any more.
OPEN_STATUSES = ("draft", "active", "monitoring")


class SupplierImprovementPlan(TenantNumbered):
    """One supplier performance improvement plan [SIP-] — the work that followed a bad number."""

    NUMBER_PREFIX = "SIP"

    # Re-exported through the class so templates, forms and views can reach them off the model
    # (``SupplierImprovementPlan.STATUS_CHOICES``), mirroring SupplierKpi, SupplierFeedback and
    # VendorSuspension. The module-level names stay the definition; these are aliases, never a
    # second copy to drift from.
    SEVERITY_CHOICES = SEVERITY_CHOICES
    STATUS_CHOICES = STATUS_CHOICES
    OUTCOME_CHOICES = OUTCOME_CHOICES
    SEVERITY_CSS = SEVERITY_CSS
    STATUS_CSS = STATUS_CSS
    OUTCOME_CSS = OUTCOME_CSS
    OPEN_STATUSES = OPEN_STATUSES

    title = models.CharField(max_length=200)
    supplier = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT,
        related_name="procurement_improvement_plans")
    scorecard = models.ForeignKey(
        "scm.SupplierScorecard", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_improvement_plans",
        help_text="The triggering evidence — the period whose performance opened this plan")
    kpi = models.ForeignKey(
        "procurement.SupplierKpi", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="improvement_plans",
        help_text="The failing KPI, when one metric drove it")
    severity = models.CharField(max_length=8, choices=SEVERITY_CHOICES, default="major")
    finding = models.TextField(help_text="What was observed")
    root_cause = models.TextField(blank=True)
    corrective_actions = models.TextField(blank=True)
    support_provided = models.TextField(
        blank=True, help_text="What the buyer is doing to help")
    success_criteria = models.TextField(
        blank=True, help_text="What 'fixed' looks like, in measurable terms")
    start_date = models.DateField()
    target_close_date = models.DateField()
    next_review_date = models.DateField(
        null=True, blank=True, help_text="When the next check-in falls due")
    extended_close_date = models.DateField(
        null=True, blank=True,
        help_text="A granted extension — must fall after the original target")
    actual_close_date = models.DateField(null=True, blank=True, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    outcome = models.CharField(max_length=12, choices=OUTCOME_CHOICES, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_improvement_plans",
        help_text="The internal owner of this plan")
    supplier_owner_name = models.CharField(max_length=160, blank=True)
    supplier_owner_email = models.EmailField(blank=True)
    escalated_suspension = models.ForeignKey(
        "procurement.VendorSuspension", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="improvement_plans",
        help_text="The block register entry this plan escalated to — never a second blocking "
                  "mechanism")
    evidence = models.FileField(
        upload_to="procurement/improvement_evidence/%Y/%m/", null=True, blank=True)
    evidence_url = models.URLField(blank=True, help_text="Link to evidence held elsewhere")
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="procurement_pip_acknowledged")
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="procurement_pip_verified")
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    closure_note = models.TextField(blank=True, editable=False)

    class Meta:
        ordering = ["-start_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_sip_tnt_status_idx"),
            models.Index(fields=["tenant", "supplier"], name="prc_sip_tnt_supp_idx"),
            models.Index(fields=["tenant", "severity"], name="prc_sip_tnt_sev_idx"),
        ]
        verbose_name = "Supplier Improvement Plan"
        verbose_name_plural = "Supplier Improvement Plans"

    def __str__(self):
        return f"{self.number or 'SIP'} · {self.title}"

    def clean(self):
        """Five rules, collected so a form shows every problem at once rather than the first.

        1. **A plan cannot close before it starts.**
        2. **An extension must fall STRICTLY AFTER the original target.** An extension granted on
           or before the agreed date is not an extension; allowing it would be a way to quietly
           re-write what was agreed and make :attr:`is_overdue` read clean.
        3. **``outcome`` is exactly as long-lived as ``closed``.** A closed plan must record how
           it ended, and an open one must not claim to have ended — an outcome sitting on an
           active plan is a result nobody signed off.
        4. **An escalation must point at THIS supplier's block.** Same tenant AND same supplier:
           a pointer at another supplier's suspension would show a block on this plan's page that
           does not block this supplier at all.
        5. **Same-tenant guards on the three cross-table FKs.**

        Every FK is resolved with an ``_id`` guard plus an explicit queryset lookup, never
        ``self.kpi.tenant_id`` — the two-arg ``getattr`` form raises ``RelatedObjectDoesNotExist``
        on an unsaved instance whose FK was not set, which 500'd a live add page once already
        (the ``VendorSuspension.clean()`` precedent, which Entity 3 follows too). The tenant
        comparisons are skipped while ``tenant_id`` is unset: there is nothing to compare against
        yet.
        """
        super().clean()
        errors = {}

        # Rule 1 — a window has to be a window.
        if (self.start_date is not None and self.target_close_date is not None
                and self.target_close_date < self.start_date):
            errors["target_close_date"] = "The plan closes before it starts."

        # Rule 2 — an extension moves the date FORWARD or it is not an extension.
        if (self.extended_close_date is not None and self.target_close_date is not None
                and self.extended_close_date <= self.target_close_date):
            errors["extended_close_date"] = ("An extension has to fall after the original target "
                                             "date.")

        # Rule 3 — outcome and "closed" live and die together.
        if self.status == "closed":
            if not self.outcome:
                errors["outcome"] = "A closed plan has to record its outcome."
        elif self.outcome:
            errors["outcome"] = "Only a closed plan carries an outcome — clear it."

        # Rule 4 — the escalation pointer, checked for tenant AND supplier in ONE lookup. A
        # cross-table read, imported locally — see the module docstring.
        if self.tenant_id and self.escalated_suspension_id:
            from apps.procurement.models.VendorManagement.VendorSuspensions import (
                VendorSuspension)
            blocked_supplier_id = (VendorSuspension.objects
                                   .filter(pk=self.escalated_suspension_id,
                                           tenant_id=self.tenant_id)
                                   .values_list("supplier_id", flat=True).first())
            if blocked_supplier_id is None:
                errors["escalated_suspension"] = "That record belongs to another workspace."
            elif self.supplier_id and blocked_supplier_id != self.supplier_id:
                errors["escalated_suspension"] = ("That suspension is against a different "
                                                  "supplier.")

        # Rule 5 — same-tenant guards on the three FKs into another table.
        if self.tenant_id and self.supplier_id:
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
            from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import (
                SupplierKpi)
            if not SupplierKpi.objects.filter(pk=self.kpi_id,
                                              tenant_id=self.tenant_id).exists():
                errors["kpi"] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)

    @property
    def has_evidence(self):
        """True when something backs this plan up — an upload or a link to one held elsewhere.

        Either satisfies it: plenty of evidence lives in a shared drive or a QMS and is better
        linked than re-uploaded, and a plan whose proof is a URL is not less evidenced than one
        whose proof is a PDF.
        """
        return bool(self.evidence) or bool(self.evidence_url)

    @property
    def effective_close_date(self):
        """The date this plan is actually due — the extension when one was granted.

        THE one place the deadline is resolved. The overdue rule below, the register's overdue
        stat and every "due" reading on a page all come through here, so a granted extension can
        never be honoured on one surface and ignored on another.
        """
        return self.extended_close_date or self.target_close_date

    @property
    def is_overdue(self):
        """True when a still-open plan is past :attr:`effective_close_date`.

        Only an OPEN plan can be overdue: a closed or cancelled one has stopped being work
        anybody is waiting on, and colouring it red forever would bury the plans that still need
        chasing.
        """
        return bool(self.effective_close_date and self.status in self.OPEN_STATUSES
                    and self.effective_close_date < timezone.localdate())

    @property
    def severity_css(self):
        """The theme class for this plan's severity. Colour-named only (L33)."""
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def status_css(self):
        """The theme class for this plan's status. Colour-named only (L33)."""
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def outcome_css(self):
        """The theme class for how this plan ended. Colour-named only (L33)."""
        return self.OUTCOME_CSS.get(self.outcome, "badge-slate")
