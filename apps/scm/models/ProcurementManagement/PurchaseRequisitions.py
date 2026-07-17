"""SCM 4.1 Procurement Management — PurchaseRequisitions models.

The internal "I need to buy this" request that opens the procure-to-pay chain:
PR -> RFQ -> quote award -> PO -> GRN -> three-way match against ``accounting.Bill``.

Line items are FREE-TEXT (``item_description``/``sku_hint``/``uom_hint``) rather than a FK to a
catalog: ``core.Item`` does not exist yet (it lands with Module 5 Inventory). This mirrors the
CRM 1.12 precedent and is recorded as a future migration (lesson L28) — when ``core.Item`` ships,
these four line tables gain an optional ``item`` FK and the free-text fields become the fallback.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class PurchaseRequisition(TenantNumbered):
    """An internal request to purchase goods/services [PR-]. Approval-routed by amount and
    budget-checked against ``accounting.Budget`` at view time. ``estimated_total`` is recomputed
    from lines and is never hand-edited."""

    NUMBER_PREFIX = "PR"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("converted", "Converted"),
        ("cancelled", "Cancelled"),
    ]
    # Statuses that consume budget — used by budget_check() to total prior commitments.
    COMMITTED_STATUSES = ("approved", "converted")
    # Statuses that still allow editing/deleting the requisition.
    EDITABLE_STATUSES = ("draft", "pending_approval")

    # Multi-tier approval routing: bigger spend needs more senior sign-off. Ordered
    # low->high; the first threshold the estimated total does NOT exceed wins.
    APPROVAL_TIERS = [
        (Decimal("1000"), "standard", "Standard"),
        (Decimal("10000"), "manager", "Manager"),
        (None, "executive", "Executive"),
    ]
    # Tiers above this require a tenant admin to approve (enforced in the view).
    ELEVATED_TIERS = ("manager", "executive")

    title = models.CharField(max_length=255)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="scm_requisitions")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_requisitions",
                                 help_text="Requesting department / cost centre — the budget dimension")
    budget = models.ForeignKey("accounting.Budget", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="scm_requisitions",
                               help_text="Budget this spend is checked against")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_requisitions")
    required_by = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    justification = models.TextField(blank=True, help_text="Why this purchase is needed")
    estimated_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_requisitions_approved", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True, editable=False,
                                     help_text="Approver's rejection reason / approval note")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_pr_tenant_status_idx"),
            models.Index(fields=["tenant", "required_by"], name="scm_pr_tenant_reqby_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    def approval_tier(self):
        """The sign-off tier this requisition's value demands. Returns ``(code, label)``."""
        total = self.estimated_total or ZERO
        for threshold, code, label in self.APPROVAL_TIERS:
            if threshold is None or total <= threshold:
                return code, label
        return self.APPROVAL_TIERS[-1][1], self.APPROVAL_TIERS[-1][2]

    def needs_elevated_approval(self):
        return self.approval_tier()[0] in self.ELEVATED_TIERS

    def recalc_totals(self, save=True):
        self.estimated_total = sum((r.line_total for r in self.lines.all()), ZERO)
        if save:
            self.save(update_fields=["estimated_total", "updated_at"])

    def budget_check(self):
        """Compare this requisition against the matching ``accounting.BudgetLine`` amounts.

        A view-time check, not a stored encumbrance — deliberately: the budget is the accounting
        module's to own, and duplicating a committed-balance field here would be a second source of
        truth that drifts. Returns ``None`` when there is nothing to check against.
        """
        if not self.budget_id:
            return None
        costed_lines = [line for line in self.lines.all() if line.gl_account_id]
        if not costed_lines:
            return None
        account_ids = {line.gl_account_id for line in costed_lines}

        qs = self.budget.lines.filter(gl_account_id__in=account_ids)
        if self.org_unit_id:
            # A budget line with no org_unit is a company-wide line and applies to every unit.
            qs = qs.filter(Q(org_unit_id=self.org_unit_id) | Q(org_unit__isnull=True))
        budgeted = qs.aggregate(s=Sum("amount"))["s"] or ZERO

        # Committed spend is summed at LINE level, restricted to the same GL accounts. Summing other
        # requisitions' whole `estimated_total` would count their spend on accounts this check never
        # budgeted for — on any budget funding more than one account that reads as a phantom overrun
        # (or hides a real one), and the approver is looking straight at this number.
        committed = (
            PurchaseRequisitionLine.objects
            .filter(
                requisition__tenant=self.tenant,
                requisition__budget_id=self.budget_id,
                requisition__status__in=self.COMMITTED_STATUSES,
                gl_account_id__in=account_ids,
            )
            .exclude(requisition_id=self.pk)
            .aggregate(s=Sum("line_total"))["s"] or ZERO
        )
        # Likewise `requested` counts only the lines this check actually covers, so all three
        # figures are like-for-like. Uncosted lines (no GL account) are budgeted by nobody.
        requested = sum((line.line_total for line in costed_lines), ZERO)
        remaining = budgeted - committed - requested
        return {
            "budget": self.budget,
            "budgeted": budgeted,
            "committed": committed,
            "requested": requested,
            "remaining": remaining,
            "over_budget": remaining < ZERO,
        }

    def __str__(self):
        return f"{self.number or 'PR'} · {self.title}"


class PurchaseRequisitionLine(models.Model):
    """One requested item on a requisition. ``line_total`` is derived, never hand-set."""

    requisition = models.ForeignKey("scm.PurchaseRequisition", on_delete=models.CASCADE, related_name="lines")
    item_description = models.CharField(max_length=255, help_text="What is being requested")
    sku_hint = models.CharField(max_length=64, blank=True,
                                help_text="Vendor/catalog code, if known (free-text until core.Item exists)")
    uom_hint = models.CharField(max_length=32, blank=True, help_text="Unit of measure, e.g. each / box / kg")
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1,
                                   validators=[MinValueValidator(Decimal("0.0001"))])
    estimated_unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                               validators=[MinValueValidator(ZERO)])
    line_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="scm_requisition_lines", help_text="Expense account to charge")
    needed_by = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or ZERO) * (self.estimated_unit_price or ZERO)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_description} ×{self.quantity}"
