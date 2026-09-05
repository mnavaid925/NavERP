"""Procurement 6.19 Document & Knowledge Management — ProcurementPolicy.

**What it is.** The procurement policy library [PPOL-]: one row per written rule — the purchasing
rule, the competitive-bidding threshold, the supplier code of conduct, the ethics and
conflict-of-interest statement — with a version number, a supersession chain back to the version
it replaces, an effective date, a review date and an optional link to the controlled PDF in the
6.19 repository. Bullet **3 Procurement Policy Library**. Modelled on ``hrm.HRPolicy``.

**What it is NOT — and this is the whole point of the model.** A policy DOCUMENTS a rule. It does
not ENFORCE one. Nothing in 6.19 reads ``threshold_amount``, ``threshold_basis`` or
``threshold_currency`` to gate, block, route or approve anything; those three columns exist so a
buyer can read "purchases over 25,000 USD per purchase order need three quotes" on the page that
also carries the policy text. **Approval bands are enforced by 6.3 Approval Workflow Engine's
``ApprovalRoutingRule`` rows** (department x commodity x half-open amount band -> tier count, with
a most-specific-wins resolver), and that is the only place a number decides who has to sign. If a
future change wants a threshold here to bite, the change belongs in 6.3's routing rules — not in
this model, and not in a view that reads these columns.

The single sentence that says so lives in :data:`ADVISORY_NOTE` and is printed on the register,
the form and the detail page, so the three surfaces cannot describe the same number differently.

**``requires_acknowledgment`` is a bare flag with no machinery behind it.** *Policy Management &
Acknowledgment* is 6.17's sub-module, and it owns the acknowledgement ledger: who was assigned
the policy, who signed it off, when, and what happens to the people who did not. 6.19 stores and
displays the flag and builds none of that — there is no sign-off model here, no "who has
acknowledged" panel and no assignment. Reading the flag as "this policy HAS been acknowledged"
would be false; it means "6.17 should collect acknowledgements for this one when it ships".

**The supersession chain is a one-hop pointer, deliberately.** ``previous_version`` points at the
version this row replaces; ``superseded_by`` is its reverse. Every surface in 6.19 walks exactly
ONE hop in each direction (the detail page renders ``obj.previous_version`` and
``obj.superseded_by.all()[:10]``), so no page can be made to walk a loop. The write path is where
loops are actually prevented — see :func:`supersession_conflict` — because a cycle in the data
would be a hang waiting for the first piece of code that decided to walk the whole chain.

**Publishing retires the predecessor.** A policy library whose register shows v1.0 and v2.0 of
the same rule both marked "Published" is worse than no library at all: it states two rules and
does not say which is in force. So the publish verb archives the predecessor when the predecessor
is itself published — see ``ppolicy_publish`` in the views module, where the transaction, the
tenant re-check and the audit rows live.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------------------------
# Vocabulary. Defined at module level so the seeder, the views and the templates can read it,
# and ALSO re-exposed on the class below — which is how templates and tests reach it, since the
# *_CHOICES tuples are deliberately NOT hoisted into apps/procurement/models/__init__.py
# (the 6.14/6.15 rule that entity 1 of this sub-module follows too).
# ---------------------------------------------------------------------------------------------

POLICY_TYPE_CHOICES = [
    ("purchasing_rule", "Purchasing Rule"),
    ("approval_limit", "Approval Limit"),
    ("competitive_bidding", "Competitive Bidding"),
    ("sole_source", "Sole Source"),
    ("supplier_code_of_conduct", "Supplier Code of Conduct"),
    ("ethics_conflict", "Ethics & Conflict of Interest"),
    ("sustainability", "Sustainability"),
    ("data_security", "Data Security"),
    ("other", "Other"),
]

STATUS_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
    ("archived", "Archived"),
]

#: WARNING: these describe what a threshold is MEASURED against so a human can read the rule.
#: They are documentation, never a control. No code in 6.19 branches on this value, and none may:
#: the enforceable equivalent is an ``ApprovalRoutingRule`` band in 6.3 Approval Workflow Engine,
#: which is the only thing in this codebase that decides how many signatures a spend needs.
THRESHOLD_BASIS_CHOICES = [
    ("per_line", "Per line"),
    ("per_requisition", "Per requisition"),
    ("per_purchase_order", "Per purchase order"),
    ("per_contract_year", "Per contract year"),
    ("annual_supplier_spend", "Annual spend with one supplier"),
]

#: theme.css ships ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
#: badge-slate (L33) — a semantic badge-success/-warning/-danger renders completely unstyled.
STATUS_CSS = {
    "draft": "badge-muted",
    "published": "badge-green",
    "archived": "badge-slate",
}

#: THE sentence about what a policy does and does not do. ONE constant, printed on the register,
#: the form and the detail page, so the three surfaces cannot disagree about whether a number on
#: this page stops anybody buying anything. (It does not.)
ADVISORY_NOTE = (
    "A policy records the rule for people to read. It enforces nothing on its own: approval "
    "routing is decided by the 6.3 Approval Workflow Engine's routing rules, and any threshold "
    "here is documentation, not a control."
)

#: How many hops the cycle guard will follow before it refuses rather than keeps walking. A
#: version history fifty rows deep is already pathological; walking an unbounded self-FK chain is
#: how a self-referencing table turns one bad row into a hung request.
MAX_CHAIN_DEPTH = 50


def supersession_conflict(policy, candidate):
    """Why ``candidate`` may not become ``policy``'s predecessor, or ``None`` when it may.

    Returns the SENTENCE to show the user, so the model's ``clean()`` has one call and one place
    where the wording lives.

    Three refusals, and every one of them is a loop in the version history:

    * ``candidate is policy`` — a policy superseding itself. The degenerate one-row cycle.
    * ``policy`` already appears somewhere up ``candidate``'s own chain, or that chain repeats a
      row — linking them would close the loop (A -> B -> A). Two saves are enough to build this
      by hand, which is exactly why the check walks rather than only comparing two pks.
    * the walk hits :data:`MAX_CHAIN_DEPTH` without settling the question — refused, not
      allowed. A guard that gives up and says "probably fine" is not a guard.

    One query per hop, capped. It runs on save, not on render, because a cycle must never reach
    the database in the first place: every read surface in 6.19 takes a single hop precisely so
    that a cycle written before this guard existed still cannot hang a page.
    """
    if candidate is None:
        return None

    seen = set()
    node = candidate
    for _hop in range(MAX_CHAIN_DEPTH):
        if node is None:
            return None                     # the chain ends cleanly — no loop
        if policy.pk is not None and node.pk == policy.pk:
            if node.pk == candidate.pk:
                return ("A policy cannot supersede itself. Leave this blank if this is the "
                        "first version.")
            return ("That policy already traces its own history back to this one, so linking "
                    "them would make the version chain loop. Point at an earlier version, or "
                    "leave this blank.")
        if node.pk in seen:
            # A loop that is ALREADY in the data (written before this guard existed, or through
            # the admin or a shell). Refuse to join it rather than walk it forever.
            return ("That policy's own version history already loops, so it cannot be used as a "
                    "predecessor until the loop is broken.")
        seen.add(node.pk)
        node = node.previous_version

    return (f"That policy's version history is longer than {MAX_CHAIN_DEPTH} versions, which is "
            f"further than this check will follow. Point at a recent version instead, or leave "
            f"this blank.")


class ProcurementPolicy(TenantNumbered):
    """One written procurement rule [PPOL-] — advisory by construction, versioned by design."""

    NUMBER_PREFIX = "PPOL"

    # Re-exposed on the class so views, templates and tests reach the vocabulary through the
    # model rather than through a module path.
    POLICY_TYPE_CHOICES = POLICY_TYPE_CHOICES
    STATUS_CHOICES = STATUS_CHOICES
    THRESHOLD_BASIS_CHOICES = THRESHOLD_BASIS_CHOICES
    STATUS_CSS = STATUS_CSS
    ADVISORY_NOTE = ADVISORY_NOTE

    title = models.CharField(max_length=200)
    policy_type = models.CharField(max_length=26, choices=POLICY_TYPE_CHOICES,
                                   default="purchasing_rule")
    summary = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)

    version_number = models.CharField(max_length=20, default="1.0")
    # The one hop back down the version history. SET_NULL, not CASCADE: deleting v1.0 must not
    # take v2.0 with it — the successor simply loses its back-pointer and stays in force.
    previous_version = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="superseded_by",
                                         help_text="The version this one replaces. Blank for a "
                                                   "first version.")

    # Verb-driven and therefore NOT on the form: publish and archive are POST-only actions with
    # their own audit rows, and publish is additionally administrator-gated. A status <select>
    # here would let a form save skip the workflow, the predecessor retirement and the audit
    # trail all at once.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")

    effective_from = models.DateField(null=True, blank=True)
    # Stamped by the publish verb ONLY — never typed, never on a form.
    published_at = models.DateTimeField(null=True, blank=True, editable=False)
    next_review_on = models.DateField(null=True, blank=True)

    # -----------------------------------------------------------------------------------------
    # WARNING: the three threshold columns below are ADVISORY DOCUMENTATION and nothing else.
    # They must never be read to gate, block, route or approve a requisition, an order or a
    # payment. A number rendered beside the word "policy" reads as a control, and treating it as
    # one would give a workspace a spend limit that no code enforces — the worst kind of security
    # control, the sort people believe in. The secure alternative already exists and is the only
    # correct home for it: 6.3 Approval Workflow Engine's ``ApprovalRoutingRule`` rows, which
    # resolve department x commodity x half-open amount band to a required tier count, and which
    # ``RequisitionApproval`` actually enforces under a row lock.
    # -----------------------------------------------------------------------------------------
    threshold_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                           validators=[MinValueValidator(0)],
                                           help_text="Guideline figure quoted in the policy "
                                                     "text. Nothing here enforces it.")
    threshold_basis = models.CharField(max_length=22, choices=THRESHOLD_BASIS_CHOICES, blank=True,
                                       default="",
                                       help_text="What the guideline figure is measured "
                                                 "against.")
    # A DISPLAY LABEL. accounting.Currency is a GLOBAL table with no tenant column, and no
    # conversion, rate lookup or ledger effect happens anywhere in 6.19 (L29) — the column says
    # which currency the written rule quotes, so the page does not print a bare number.
    threshold_currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           related_name="procurement_policies")

    # WARNING: a BARE HOOK for 6.17 Policy Management & Acknowledgment, which owns the
    # acknowledgement ledger. It records an INTENTION ("collect sign-offs for this one"), never a
    # fact ("this user has acknowledged it") — no assignment, no sign-off row and no signature
    # exists in 6.19. Nothing may be authorized on this flag: gating a page or a purchase on it
    # would grant or refuse access on the strength of a sign-off that was never collected. When
    # 6.17 lands, the ledger it builds is what may be read.
    requires_acknowledgment = models.BooleanField(
        default=False,
        help_text="A hook for 6.17 Policy Management & Acknowledgment - no sign-off ledger is "
                  "built here.")

    applies_to = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="procurement_policies",
                                   help_text="Blank = the whole workspace.")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="procurement_policies_owned",
                              help_text="Who is answerable for keeping this policy current")
    # THE FK THAT MAKES 6.19 ONE SUB-MODULE RATHER THAN TWO HALVES: the policy PDF is an ordinary
    # ProcurementDocument, so it inherits the revision chain, the approval step and the text
    # search instead of carrying a second, unversioned copy of the same file. ``related_name`` is
    # ``policies`` because entity 1's detail view already reads that reverse accessor.
    document = models.ForeignKey("procurement.ProcurementDocument", on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="policies",
                                 help_text="The policy PDF in the repository - so it inherits "
                                           "revision control and text search.")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        # Two constraints: the workspace-unique number, and the HRM precedent that one title may
        # exist once per version. v1.0 and v2.0 of "Competitive Bidding" are two rows; a second
        # v2.0 of it is a mistake the database refuses.
        unique_together = (("tenant", "number"), ("tenant", "title", "version_number"))
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_ppol_tnt_status_idx"),
            models.Index(fields=["tenant", "policy_type"], name="prc_ppol_tnt_type_idx"),
            models.Index(fields=["tenant", "next_review_on"], name="prc_ppol_tnt_review_idx"),
        ]
        verbose_name = "Procurement Policy"
        verbose_name_plural = "Procurement Policies"

    def __str__(self):
        return f"{self.title} v{self.version_number}"

    # -- presentation helpers -------------------------------------------------------------

    @property
    def status_css(self):
        return STATUS_CSS.get(self.status, "badge-slate")

    @property
    def threshold_label(self):
        """The guideline figure as one string, or ``""`` when the policy quotes none.

        Exists for the same reason :data:`ADVISORY_NOTE` does: the register and the detail page
        both print this number, and two hand-rolled renderers would eventually disagree about
        what it means. Reads ``threshold_currency_id`` before the object, so an unset currency
        costs no query.
        """
        if self.threshold_amount is None:
            return ""
        code = self.threshold_currency.code if self.threshold_currency_id else ""
        basis = self.get_threshold_basis_display() if self.threshold_basis else ""
        parts = [f"{self.threshold_amount:,.2f}"]
        if code:
            parts.insert(0, code)
        if basis:
            parts.append(basis.lower())
        return " ".join(parts)

    # -- life-cycle questions -------------------------------------------------------------

    @property
    def is_review_due(self):
        """Computed against today rather than stored, so a row cannot go stale in the database.

        The register runs the same comparison in SQL for its ``?review=due`` facet and its stat
        tile, so the badge on a row and the count above it always agree.
        """
        return bool(self.next_review_on and self.next_review_on <= timezone.localdate())

    # -- validation -----------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}

        tenant_id = getattr(self, "tenant_id", None)
        if tenant_id:
            # Cross-tenant backstop on every tenant-scoped link. The narrowed <select> on the
            # form is UX; a crafted POST never goes near it, and each of these FKs would
            # otherwise pull another workspace's org unit, document or policy into this register.
            # ``_id`` is tested FIRST so an unset FK cannot raise RelatedObjectDoesNotExist.
            #
            # ``threshold_currency`` is deliberately absent: accounting.Currency is a GLOBAL
            # table with no tenant column, so comparing its tenant_id would reject every currency
            # anybody ever chose.
            for field in ("applies_to", "document", "previous_version"):
                if not getattr(self, f"{field}_id", None):
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        # Self-supersession and every longer loop, in one call. Skipped when the FK is already
        # flagged as foreign above — walking another workspace's chain would be a second bug.
        if self.previous_version_id and "previous_version" not in errors:
            problem = supersession_conflict(self, self.previous_version)
            if problem:
                errors["previous_version"] = problem

        # The two threshold columns are set together or not at all. An amount with no basis is an
        # unreadable rule ("25,000 of what?"), and a basis with no amount is a measuring stick
        # with no mark on it. The currency stays optional — it is a label on the number, and a
        # policy quoting a workspace's only currency does not need to repeat it.
        has_amount = self.threshold_amount is not None
        has_basis = bool(self.threshold_basis)
        if has_amount and not has_basis:
            errors["threshold_basis"] = ("Say what the guideline figure is measured against - "
                                         "per line, per requisition, per order, and so on.")
        elif has_basis and not has_amount:
            errors["threshold_amount"] = ("Give the guideline figure, or clear the basis. A "
                                          "basis on its own states nothing.")

        if errors:
            raise ValidationError(errors)
