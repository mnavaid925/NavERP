"""Procurement 6.15 Budget & Cost Management — BudgetMapping.

**What it is.** The configuration row that answers "which ``accounting.Budget`` governs this
department's / project's procurement spend?" ``accounting.BudgetLine`` (2.13) allocates amounts
INSIDE one budget by GL account and org unit; nothing on the spine says which budget a workspace's
requisition flow should default to for a given department or project. That glue is procurement's
to own, and it is exactly the NavERP.md "Budget Allocation & Mapping" bullet.

**What it is NOT.** It is not a budget: amounts, periods and revisions stay in
``accounting.Budget`` / ``BudgetLine`` (L29 — link out, never restate). No column here holds
money, and no view of this sub-module writes to ``accounting.*`` or to the scm document spine.

**Configuration master, not a document.** ``TenantOwned``, not ``TenantNumbered`` — the same shape
as 6.14's ``SpendClassificationRule`` and for the same reasons there is **no unique_together**:
two same-shaped rows at different priorities is a legitimate override, not a mistake, and a
nullable-column unique would not be portable anyway. :meth:`BudgetMapping.resolve` decides which
row wins.

**The commitment vocabulary.** The three status tuples and the three line-window helpers below are
this sub-module's SINGLE definition of "what counts as committed/requested spend" — the checker,
the register and the variance report all read them, so the three pages can never disagree about
the same purchase order. ``OPEN_COMMITMENT_PO_STATUSES`` is copied VERBATIM from
``apps/scm/views/FinanceIntegration/Reports.py:112`` (scm 4.18's "live commitment to a vendor")
and ``COMMITTED_PR_STATUSES`` deliberately EXCLUDES ``converted``: a converted requisition has
become its purchase order, and counting both would double-count one commitment. (``scm``'s own
``PurchaseRequisition.COMMITTED_STATUSES`` includes ``converted`` because ``budget_check()`` looks
at requisitions alone and never at the orders they became — a different question.)

**Import discipline.** Every cross-app FK is a STRING; the scm line models are imported INSIDE the
helpers, mirroring 6.14's rule.
"""
from apps.procurement.models._base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------------------------
# Commitment vocabulary (single source for the whole sub-module)
# ---------------------------------------------------------------------------------------------

#: PO statuses that represent a LIVE commitment to a vendor. ``draft`` / ``pending_approval`` are
#: not commitments yet; ``cancelled`` never was; ``closed`` no longer is (the encumbrance is
#: released even where the money trail is still settling). Copied verbatim from scm 4.18.
OPEN_COMMITMENT_PO_STATUSES = ("approved", "sent", "acknowledged", "partially_received", "received")

#: Requisition status that is an approved-but-not-yet-ordered commitment. NOT ``converted`` — see
#: the module docstring for the double-count this exclusion prevents.
COMMITTED_PR_STATUSES = ("approved",)

#: Requisition status that is money REQUESTED but not yet committed — the pipeline column on the
#: availability checker.
REQUESTED_PR_STATUSES = ("pending_approval",)


def open_po_commitment_lines(tenant):
    """``scm.PurchaseOrderLine`` rows that are a live commitment for this tenant.

    No budget scoping here — callers narrow by budget (via the requisition behind the order), by
    GL account or by org unit depending on which page is asking.
    """
    from apps.scm.models import PurchaseOrderLine

    if tenant is None:
        return PurchaseOrderLine.objects.none()
    return PurchaseOrderLine.objects.filter(
        purchase_order__tenant=tenant,
        purchase_order__status__in=OPEN_COMMITMENT_PO_STATUSES)


def committed_pr_lines(tenant):
    """``scm.PurchaseRequisitionLine`` rows on approved-but-unconverted requisitions."""
    from apps.scm.models import PurchaseRequisitionLine

    if tenant is None:
        return PurchaseRequisitionLine.objects.none()
    return PurchaseRequisitionLine.objects.filter(
        requisition__tenant=tenant,
        requisition__status__in=COMMITTED_PR_STATUSES)


def requested_pr_lines(tenant):
    """``scm.PurchaseRequisitionLine`` rows still awaiting approval (the pipeline)."""
    from apps.scm.models import PurchaseRequisitionLine

    if tenant is None:
        return PurchaseRequisitionLine.objects.none()
    return PurchaseRequisitionLine.objects.filter(
        requisition__tenant=tenant,
        requisition__status__in=REQUESTED_PR_STATUSES)


class BudgetMapping(TenantOwned):
    """One explicit mapping: procurement spend for this department / project is governed by this
    ``accounting.Budget``. Both dimensions NULL is the legitimate workspace default."""

    # Re-exposed on the class so views/templates/tests reach the vocabulary through the model.
    OPEN_COMMITMENT_PO_STATUSES = OPEN_COMMITMENT_PO_STATUSES
    COMMITTED_PR_STATUSES = COMMITTED_PR_STATUSES
    REQUESTED_PR_STATUSES = REQUESTED_PR_STATUSES

    #: theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
    #: badge-slate (L33) — a semantic badge-success renders unstyled.
    ACTIVE_CSS = {True: "badge-green", False: "badge-muted"}

    # PROTECT, mirroring SpendClassificationRule.category: deleting a budget a mapping still
    # points at would silently un-govern a department's spend. The mapping must be removed or
    # re-pointed first.
    budget = models.ForeignKey(
        "accounting.Budget", on_delete=models.PROTECT,
        related_name="procurement_budget_mappings",
        help_text="The accounting budget this mapping governs spend against")
    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_budget_mappings",
        help_text="Department / cost centre this mapping applies to (blank = any)")
    project = models.ForeignKey(
        "accounting.Project", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_budget_mappings",
        help_text="Project this mapping applies to (blank = any). Project mappings are more "
                  "specific than department ones.")
    default_gl_account = models.ForeignKey(
        "accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_budget_mappings",
        help_text="GL account to pre-fill when raising requisitions under this mapping")

    priority = models.PositiveSmallIntegerField(
        default=100, help_text="Lower numbers win. Ties break on the mapping's id.")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["priority", "id"]
        indexes = [
            # Backs resolve()'s hot query (tenant + is_active in priority order) and the
            # register's default ORDER BY — priority and id included so both orderings are
            # served from the index itself, never a filesort.
            models.Index(fields=["tenant", "is_active", "priority", "id"],
                         name="prc_bmap_tnt_active_idx"),
            models.Index(fields=["tenant", "budget"], name="prc_bmap_tnt_budget_idx"),
        ]
        verbose_name = "Budget Mapping"
        verbose_name_plural = "Budget Mappings"

    def __str__(self):
        # Guarded on the id: on an UNSAVED instance (a ModelForm rendering its own errors)
        # ``self.budget`` raises RelatedObjectDoesNotExist and a validation page must never 500.
        if not self.budget_id:
            return self.dimension_label
        return f"{self.budget} -> {self.dimension_label}"

    @property
    def dimension_label(self):
        """The dimension this mapping governs, as one readable phrase."""
        if self.project_id:
            return str(self.project)
        if self.org_unit_id:
            return str(self.org_unit)
        return "Workspace default"

    @property
    def status_css(self):
        return self.ACTIVE_CSS.get(bool(self.is_active), "badge-muted")

    @property
    def status_label(self):
        return "Active" if self.is_active else "Inactive"

    def clean(self):
        super().clean()
        errors = {}
        tenant_id = getattr(self, "tenant_id", None)

        # Cross-tenant guard on every FK. Same tenant is not the same subject: a narrowed
        # <select> is UX, and this is the model-level backstop behind the form's own re-check.
        # (``budget`` itself is validated too — a crafted POST could point a mapping at another
        # workspace's budget even though the dropdown never offered it.)
        if tenant_id:
            for field in ("budget", "org_unit", "project", "default_gl_account"):
                fk_id = getattr(self, f"{field}_id", None)
                if not fk_id:
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)

    @classmethod
    def resolve(cls, tenant, org_unit=None, project=None):
        """The most specific ACTIVE mapping for this department/project, or ``None``.

        Specificity beats priority, then priority, then id: a project match wins over a
        department match, which wins over the workspace default; inside each tier the rows are
        already in ``(priority, id)`` order. Accepts model instances or raw pks for both
        dimensions.
        """
        if tenant is None:
            return None
        org_unit_id = getattr(org_unit, "pk", org_unit)
        project_id = getattr(project, "pk", project)

        candidates = list(
            cls.objects.filter(tenant=tenant, is_active=True)
            .select_related("budget", "org_unit", "project", "default_gl_account")
            .order_by("priority", "id"))

        if project_id:
            for mapping in candidates:
                if mapping.project_id == project_id:
                    return mapping
        if org_unit_id:
            for mapping in candidates:
                if mapping.org_unit_id == org_unit_id and mapping.project_id is None:
                    return mapping
        for mapping in candidates:
            if mapping.org_unit_id is None and mapping.project_id is None:
                return mapping
        return None
