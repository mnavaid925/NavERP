"""SCM 4.10 Returns Management — WarrantyClaim [WTY-] + its typed WarrantyClaimCost children.

**Deliberately NOT an extension of ``scm.NonConformance``.** An NCR is an internal finding register
with one counterparty-less ``cost_of_quality`` figure and a state machine WE advance. A warranty
claim is a two-party negotiation: claimed → approved → credited amounts against a NAMED
``core.Party``, a contractual response deadline, and a state machine THEY advance. Squeezing that
into ``NonConformance.disposition`` would give one row two owners and two meanings.

**Nothing is drafted in accounting for a warranty recovery, and that is a schema fact, not a
choice.** ``accounting.Bill`` has NO ``kind`` field — unlike ``accounting.Invoice``, which does
(``[("invoice", …), ("credit_note", …)]``) and is what the customer-side credit note uses. There is
therefore no vendor-credit document to draft. This model records ``amount_approved`` /
``amount_credited`` / ``credit_reference`` / ``credit_received_on`` and drafts nothing.
**FLAG TO MODULE 2/6: adding ``Bill.kind`` is the change that would unlock a real vendor credit
here.** SCM posts no JournalEntry either way (L29).

``WarrantyClaimCost`` exists because the normal real outcome is a PARTIAL approval that accepts the
part and refuses the labour — SAP's typed claim items (MAT / SUBL / FR) exist for the same reason.
A flat ``claim_value`` column cannot express that, and every recovery-rate figure computed from one
would be a lie.

Deferred, named: multi-round negotiation history (SAP's version stack — a ``WarrantyClaimVersion``
child later, NOT a retrofit onto ``status``), a ``WarrantyRegistration`` master (entitlement is
derived from ``purchase_date`` + the policy window + the serial), and a supplier self-service claim
portal / EDI (``submitted_on`` + ``submission_channel`` are the data hooks).
"""
import datetime

from django.utils.functional import cached_property

from apps.scm.models._base import *  # noqa: F401,F403


class WarrantyClaim(TenantNumbered):
    """A recovery claim against a supplier for a failed unit [WTY-]."""

    NUMBER_PREFIX = "WTY"

    DEFECT_CLASSIFICATION_CHOICES = [
        ("manufacturing", "Manufacturing defect"),
        ("material", "Material defect"),
        ("component", "Bought-in component"),
        ("assembly", "Assembly error"),
        ("workmanship", "Workmanship"),
        ("transit_damage", "Transit damage"),
        ("misuse_excluded", "Misuse — excluded from cover"),
        ("unknown", "Unknown"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("acknowledged", "Acknowledged"),
        ("approved", "Approved"),
        ("partially_approved", "Partially approved"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
        ("credited", "Credited"),
        ("closed", "Closed"),
    ]
    SUBMISSION_CHANNEL_CHOICES = [
        ("email", "Email"),
        ("portal", "Supplier portal"),
        ("edi", "EDI"),
        ("phone", "Phone"),
        ("post", "Post"),
    ]

    #: Statuses whose header and cost lines a user may still edit.
    EDITABLE_STATUSES = ("draft",)
    #: Statuses the supplier has responded to — a response may not be recorded twice.
    RESPONDED_STATUSES = ("approved", "partially_approved", "rejected")
    #: Statuses that still count as outstanding recovery on a roll-up.
    OPEN_STATUSES = ("draft", "submitted", "acknowledged", "approved", "partially_approved")
    TERMINAL_STATUSES = ("rejected", "expired", "credited", "closed")

    supplier = models.ForeignKey("core.Party", on_delete=models.PROTECT,
                                 related_name="scm_warranty_claims")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT,
                             related_name="scm_warranty_claims")
    quantity_claimed = models.DecimalField(max_digits=14, decimal_places=4,
                                           validators=[MinValueValidator(Decimal("0.0001"))])
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="scm_warranty_claims")
    serial_reference = models.CharField(
        max_length=64, blank=True,
        help_text="A customer-supplied serial we never stocked — there is nothing to FK to")

    return_authorization = models.ForeignKey("scm.ReturnAuthorization", on_delete=models.SET_NULL,
                                             null=True, blank=True, related_name="warranty_claims")
    nonconformance = models.ForeignKey("scm.NonConformance", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="scm_warranty_claims")
    goods_receipt = models.ForeignKey("scm.GoodsReceiptNote", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="scm_warranty_claims")

    purchase_date = models.DateField(null=True, blank=True)
    warranty_start = models.DateField(null=True, blank=True)
    warranty_end = models.DateField(null=True, blank=True)
    failure_date = models.DateField(null=True, blank=True)
    usage_context = models.CharField(max_length=255, blank=True,
                                     help_text="How the unit was being used when it failed — the "
                                               "first thing a supplier asks")
    defect_classification = models.CharField(max_length=18,
                                             choices=DEFECT_CLASSIFICATION_CHOICES,
                                             default="unknown")
    supplier_rma_number = models.CharField(
        max_length=64, blank=True,
        help_text="THEIR number for this claim — tracked separately from ours, and the thing that "
                  "makes a duplicate claim detectable")
    description = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft",
                              editable=False)
    submitted_on = models.DateField(null=True, blank=True, editable=False)
    submission_channel = models.CharField(max_length=10, choices=SUBMISSION_CHANNEL_CHOICES,
                                          default="email")
    response_due_on = models.DateField(null=True, blank=True,
                                       help_text="The contractual deadline for their answer")
    responded_on = models.DateField(null=True, blank=True, editable=False)
    supplier_response_notes = models.TextField(blank=True, editable=False)

    amount_approved = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                          editable=False)
    amount_credited = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                          editable=False)
    credit_reference = models.CharField(max_length=64, blank=True, editable=False)
    credit_received_on = models.DateField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_wty_tnt_status_idx"),
            models.Index(fields=["tenant", "supplier"], name="scm_wty_tnt_supp_idx"),
            models.Index(fields=["tenant", "item"], name="scm_wty_tnt_item_idx"),
            models.Index(fields=["tenant", "response_due_on"], name="scm_wty_tnt_due_idx"),
            # Meta.ordering is ["-created_at", "-id"] and the list view re-states it, but nothing
            # indexed created_at — so every page filesorted the tenant's whole claim table and
            # page 20 cost the same as page 1. The ordering column is the paginator's stability
            # key, so it needs the index. Matches the app-wide (tenant, <date>) pattern.
            models.Index(fields=["tenant", "created_at"], name="scm_wty_tnt_created_idx"),
            models.Index(fields=["tenant", "submitted_on"], name="scm_wty_tnt_subon_idx"),        ]

    def __str__(self):
        return f"{self.number or 'WTY'} · {self.item_id and self.item.sku}"

    def clean(self):
        super().clean()
        if self.lot_serial_id and self.item_id and self.lot_serial.item_id != self.item_id:
            raise ValidationError(
                {"lot_serial": f"{self.lot_serial.number} belongs to {self.lot_serial.item.sku}, "
                               f"not {self.item.sku}."})
        if self.warranty_start and self.warranty_end and self.warranty_end < self.warranty_start:
            raise ValidationError({"warranty_end": "The cover ends before it starts."})
        if self.failure_date and self.purchase_date and self.failure_date < self.purchase_date:
            raise ValidationError({"failure_date": "The unit failed before it was bought."})

    # --- derived (nothing below is stored) -------------------------------------------------------
    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @cached_property
    def amount_claimed_total(self):
        """The sum of the typed cost lines — what we are ASKING for."""
        return q2(self.costs.aggregate(s=Sum("amount_claimed"))["s"] or ZERO)

    @cached_property
    def cost_approved_total(self):
        """The sum of the per-line approvals the supplier granted."""
        return q2(self.costs.aggregate(s=Sum("amount_approved"))["s"] or ZERO)

    @property
    def recovery_variance(self):
        """Claimed minus credited — the money still on the table (or written off)."""
        return q2(self.amount_claimed_total - (self.amount_credited or ZERO))

    @property
    def recovery_rate_pct(self):
        """Credited as a percentage of claimed. 0 when nothing was claimed — never a ZeroDivision."""
        claimed = self.amount_claimed_total
        if claimed <= ZERO:
            return ZERO
        return q2((self.amount_credited or ZERO) * Decimal("100") / claimed)

    @property
    def is_in_warranty(self):
        """Was the unit under cover when it failed?

        Entitlement is DERIVED — there is no ``WarrantyRegistration`` master (deferred). Explicit
        ``warranty_start``/``warranty_end`` dates win; otherwise the purchase date plus the
        governing policy's ``warranty_window_days`` is the window.
        """
        failed = self.failure_date or timezone.localdate()
        if self.warranty_start and failed < self.warranty_start:
            return False
        if self.warranty_end:
            return failed <= self.warranty_end
        if self.purchase_date:
            from apps.scm.models.ReturnsManagement.ReturnPolicies import select_policy
            policy = select_policy(self.tenant, self.item if self.item_id else None)
            days = policy.warranty_window_days if policy is not None else 365
            return failed <= self.purchase_date + datetime.timedelta(days=days)
        return False

    @property
    def is_overdue(self):
        """The supplier's contractual deadline has passed and they have not answered."""
        if not self.response_due_on or self.status in self.TERMINAL_STATUSES:
            return False
        if self.responded_on:
            return False
        return self.response_due_on < timezone.localdate()

    @property
    def days_open(self):
        end = self.credit_received_on or timezone.localdate()
        start = self.submitted_on or (self.created_at.date() if self.created_at else None)
        return max((end - start).days, 0) if start else 0

    @property
    def is_possible_duplicate(self):
        """Another live claim on the same supplier carries the same supplier RMA number.

        Duplicate claims are the classic warranty fraud and the classic honest mistake, and this is
        the ``FreightInvoice._has_duplicate()`` precedent applied to the one field that can detect
        it. Advisory — it badges the row, it never refuses a save: a supplier legitimately reusing a
        reference across two units is their filing system's problem, not a reason to lose the claim.
        """
        if not self.supplier_rma_number or self.supplier_id is None:
            return False
        return (WarrantyClaim.objects
                .filter(tenant_id=self.tenant_id, supplier_id=self.supplier_id,
                        supplier_rma_number=self.supplier_rma_number)
                .exclude(pk=self.pk).exclude(status__in=("rejected", "closed")).exists())

    def lot_history(self, limit=50):
        """Where this lot went — the read-only ledger panel on the detail page.

        Copied in shape from ``NonConformance.lot_history()``: every move for the lot, not just the
        ones this claim relates to, so an engineer can see whether the affected batch has already
        been shipped or consumed.
        """
        from apps.scm.models import StockMove
        if self.lot_serial_id is None:
            return StockMove.objects.none()
        return (StockMove.objects
                .filter(tenant_id=self.tenant_id, lot_serial_id=self.lot_serial_id)
                .select_related("item", "location")
                .order_by("-moved_at")[:limit])


class WarrantyClaimCost(models.Model):
    """One typed cost on a claim. Tenant-less — reached only through its claim.

    ``amount_claimed`` is COMPUTED IN ``save()`` from ``quantity × unit_amount`` and is
    ``editable=False``. Shipping quantity, unit amount AND a free-typed total would be three inputs
    for one number and they would disagree the first time somebody edited two of them.
    """

    COST_TYPE_CHOICES = [
        ("part", "Replacement part"),
        ("labour", "Labour"),
        ("freight", "Freight"),
        ("external_service", "External service"),
        ("admin", "Administration"),
        ("other", "Other"),
    ]

    claim = models.ForeignKey("scm.WarrantyClaim", on_delete=models.CASCADE, related_name="costs")
    cost_type = models.CharField(max_length=18, choices=COST_TYPE_CHOICES, default="part")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("1"),
                                   validators=[MinValueValidator(Decimal("0.0001"))])
    unit_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                      validators=[MinValueValidator(ZERO)])
    amount_claimed = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                         editable=False)
    amount_approved = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)],
        help_text="What the supplier accepted on THIS line — the partial approval that a flat "
                  "claim value could never express")

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.amount_claimed = q2((self.quantity or ZERO) * (self.unit_amount or ZERO))
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        claimed = q2((self.quantity or ZERO) * (self.unit_amount or ZERO))
        if (self.amount_approved or ZERO) > claimed:
            raise ValidationError(
                {"amount_approved": f"The supplier cannot approve more ({self.amount_approved}) "
                                    f"than was claimed ({claimed})."})

    def __str__(self):
        return f"{self.get_cost_type_display()} · {self.description}"
