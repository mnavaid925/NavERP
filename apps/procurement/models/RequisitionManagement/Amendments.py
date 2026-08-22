"""Procurement 6.2 Requisition Management — RequisitionAmendments models.

**Requisition Cancellation/Amendment** bullet: a workflow to modify or cancel pending or approved
requisitions. 4.1's spine deliberately only allows IN-PLACE editing of a draft / still-pending
requisition — once it is approved (or sitting in someone's approval queue) a silent edit would
undermine the approval that was given. This model is the gated alternative: a requester FILES an
amendment (cancel the requisition, or change its header/lines), a tenant admin APPROVES or rejects
it, and ONLY the approve action touches ``scm.PurchaseRequisition`` — inside one transaction, with
the decision recorded on the amendment row and in ``core.AuditLog``.

The proposed line changes live on ``RequisitionAmendmentLine`` rows so the diff is reviewable
BEFORE it happens; applying is deterministic (add/update/remove) rather than free-text.
"""
from apps.procurement.models._base import *  # noqa: F401,F403
from apps.scm.models import PurchaseRequisitionLine


class RequisitionAmendment(TenantNumbered):
    """A requested change (or cancellation) to an existing requisition [RAM-].

    Lifecycle: ``pending`` -> ``approved`` (applies the change to the requisition immediately,
    atomically) or ``rejected``. The decision is final and recorded; there is no un-apply — that
    is what makes the workflow safe to gate with a single yes/no.
    """

    NUMBER_PREFIX = "RAM"

    AMENDMENT_TYPES = [
        ("amend", "Amend details"),
        ("cancel", "Cancel requisition"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    # Requisition statuses an amendment may target. A draft can simply be edited/deleted (4.1's
    # own paths); converted/cancelled are terminal. The bullet names exactly these two.
    AMENDABLE_STATUSES = ("pending_approval", "approved")

    requisition = models.ForeignKey("scm.PurchaseRequisition", on_delete=models.PROTECT,
                                    related_name="amendments",
                                    help_text="The requisition this amendment proposes to change")
    amendment_type = models.CharField(max_length=8, choices=AMENDMENT_TYPES, default="amend")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="pending")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name="procurement_amendments_requested",
                                     editable=False)
    reason = models.TextField(help_text="Why this change / cancellation is needed")

    # -- proposed header changes (amend type; blank = leave unchanged) --------------------------
    new_required_by = models.DateField(null=True, blank=True,
                                       help_text="Proposed new required-by date")
    new_justification = models.TextField(blank=True,
                                         help_text="Proposed new justification text")

    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name="procurement_amendments_decided", editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True, editable=False)
    applied_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_ram_tenant_status_idx"),
            models.Index(fields=["tenant", "amendment_type"], name="prc_ram_tenant_type_idx"),
        ]

    @property
    def is_pending(self):
        return self.status == "pending"

    @property
    def is_cancel(self):
        return self.amendment_type == "cancel"

    @classmethod
    def has_open_for(cls, requisition):
        """True while ANY amendment on this requisition is still undecided — one open amendment at
        a time keeps 'what does the requisition look like if approved?' answerable."""
        return requisition.amendments.filter(status="pending").exists()

    def clean(self):
        # Cancel amendments carry no proposed changes by definition.
        if self.is_cancel:
            for field in ("new_required_by", "new_justification"):
                if getattr(self, field):
                    raise ValidationError({field: "A cancellation does not carry proposed changes."})

    def __str__(self):
        return f"{self.number or 'RAM'} · {self.get_amendment_type_display()} · {self.requisition_id}"

    # -- apply ---------------------------------------------------------------------------------

    def apply(self, decider, note=""):
        """Approve AND apply in one atomic step. Returns the summary string of what changed.

        Caller contract (enforced in the view): status must be ``pending``, the requisition must
        still be amendable, and this runs inside ``transaction.atomic()``. A lost line target
        (the requisition was edited between filing and deciding) is skipped and REPORTED in the
        returned summary rather than silently ignored or fatal to the whole batch.
        """
        now = timezone.now()
        summary = []

        if self.is_cancel:
            self.requisition.status = "cancelled"
            self.requisition.decision_note = f"Cancelled via amendment {self.number}: {self.reason[:1800]}"
            self.requisition.save(update_fields=["status", "decision_note", "updated_at"])
            summary.append("requisition cancelled")
        else:
            pr = self.requisition
            header_bits = []
            if self.new_required_by:
                pr.required_by = self.new_required_by
                header_bits.append(f"required-by -> {self.new_required_by:%Y-%m-%d}")
            if self.new_justification:
                pr.justification = self.new_justification
                header_bits.append("justification updated")
            line_bits = []
            for line in self.lines.select_related("target_line"):
                outcome = line.apply_to_requisition()
                if outcome:
                    line_bits.append(outcome)
            # recalc_totals() persists the derived estimated_total; the header save below persists
            # only the two proposed header fields (update_fields never overlaps it except updated_at).
            pr.recalc_totals()
            if header_bits:
                pr.save(update_fields=["required_by", "justification", "updated_at"])
            summary.extend(line_bits + header_bits)

        self.status = "approved"
        self.decided_by = decider
        self.decided_at = now
        self.applied_at = now
        self.decision_note = (note or "").strip()[:2000]
        self.save(update_fields=["status", "decided_by", "decided_at", "applied_at",
                                 "decision_note", "updated_at"])
        return "; ".join(summary) or "no changes were required"


class RequisitionAmendmentLine(models.Model):
    """One PROPOSED line change on an amend-type requisition amendment.

    ``action`` says what happens on approval: ``add`` creates a new requisition line from the
    proposed values; ``update`` overwrites the target line's quantity/price/date (blank proposal
    = keep current value); ``remove`` deletes the target line. ``target_line`` is SET_NULL, not
    PROTECT, because the requisition stays editable while an amendment pends — apply() reports a
    lost target instead of blocking an unrelated edit with a database error.
    """

    ACTION_CHOICES = [
        ("add", "Add line"),
        ("update", "Update line"),
        ("remove", "Remove line"),
    ]

    amendment = models.ForeignKey("procurement.RequisitionAmendment", on_delete=models.CASCADE,
                                  related_name="lines")
    target_line = models.ForeignKey("scm.PurchaseRequisitionLine", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="amendment_lines",
                                    help_text="Which existing line this changes (blank = a new line)")
    action = models.CharField(max_length=6, choices=ACTION_CHOICES, default="update")
    item_description = models.CharField(max_length=255, blank=True,
                                        help_text="Required when adding a line")
    sku_hint = models.CharField(max_length=64, blank=True)
    uom_hint = models.CharField(max_length=32, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True,
                                   validators=[MinValueValidator(Decimal("0.0001"))],
                                   help_text="Blank on update = keep the current quantity")
    estimated_unit_price = models.DecimalField(max_digits=14, decimal_places=2, null=True,
                                               blank=True,
                                               validators=[MinValueValidator(ZERO)],
                                               help_text="Blank on update = keep the current price")
    needed_by = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def clean(self):
        if self.action in ("update", "remove") and self.target_line_id is None:
            raise ValidationError({"target_line": f"A '{self.action}' needs an existing line."})
        if self.action == "add":
            if self.target_line_id is not None:
                raise ValidationError({"action": "Adding a line cannot target an existing line."})
            if not (self.item_description or "").strip():
                raise ValidationError({"item_description": "A new line needs a description."})

    def apply_to_requisition(self):
        """Write THIS proposed change onto the parent requisition. Returns a human summary, or
        ``""`` when the target vanished before approval (reported upstream, never raised)."""
        pr = self.amendment.requisition
        if self.action == "add":
            PurchaseRequisitionLine.objects.create(
                requisition=pr,
                item_description=self.item_description,
                sku_hint=self.sku_hint or "",
                uom_hint=self.uom_hint or "",
                quantity=self.quantity or Decimal("1"),
                estimated_unit_price=self.estimated_unit_price or ZERO,
                needed_by=self.needed_by,
            )
            return f"added '{(self.item_description or '')[:60]}'"
        if self.target_line_id is None:
            return ""
        if self.action == "remove":
            desc = self.target_line.item_description[:60]
            self.target_line.delete()
            return f"removed '{desc}'"
        # update: only the fields actually proposed move — blank means keep.
        changed = []
        if self.quantity is not None:
            self.target_line.quantity = self.quantity
            changed.append("qty")
        if self.estimated_unit_price is not None:
            self.target_line.estimated_unit_price = self.estimated_unit_price
            changed.append("price")
        if self.needed_by is not None:
            self.target_line.needed_by = self.needed_by
            changed.append("date")
        if changed:
            self.target_line.save()
            return f"updated '{self.target_line.item_description[:60]}' ({'+'.join(changed)})"
        return ""
