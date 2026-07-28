"""SCM 4.10 Returns Management — ReturnAuthorization [RMA-] + its ReturnLine children.

**OWNERSHIP RULING (L36) — write this down before extending anything here.** Two unbuilt NavERP
sections nominally cover this ground: ``### 5.10 Returns Management (RMA)`` (Return Merchandise
Authorization · Return Inspection · Disposition Routing · Credit/Refund Processing) and
``### 9.5 Order Management System (OMS) → Returns & Exchanges (RMA)`` (self-service return
initiation, label generation, refund routing, restocking logic). **SCM ships first, so SCM OWNS
these tables. 5.10 and 9.5 EXTEND BY FK; neither builds a second RMA, disposition or warranty
table.** The reverse-accessor namespace ``scm_return_*`` / ``scm_warranty_*`` is reserved on
``core.Party`` and ``scm.Item`` so a later module cannot collide.

A **non-posting document** in NetSuite's exact sense: it authorises, and it owns no stock and no
money. The only thing in 4.10 that touches the append-only ledger is ``ReturnDisposition``; the only
thing that touches accounting is ``returnauthorization_draft_credit_note``, which drafts an
``accounting.Invoice(kind="credit_note", status="draft")`` and stops. **SCM posts NO JournalEntry
(L29).**

A portal submission is *this* record at ``status="requested"`` — a status is not a document, so
there is deliberately no separate intake table.

**``return_type`` gates whether a receipt is required at all.** D365's second first-class process is
``credit_only``: the customer keeps (or never had) the goods and we credit them. Such an RMA never
gets a disposition row, so every queue keyed on "received" must branch on ``return_type`` or it will
silently drop perfectly valid work — see :attr:`is_settleable`.

Accepted, documented limitations:

* **One ``credit_note`` FK per RMA.** Epicor supports several against one RMA; a second credit here
  is a manual job in Accounts Receivable.
* **The credit-note direction gap is Module 2's.** ``invoice_post`` does not branch on ``kind``, so
  an ISSUED credit note posts Dr AR / Cr Income (backwards), and while ``sent`` it ADDS to the open
  exposure ``_evaluate_hold`` reads — a returning customer's credit position temporarily worsens.
  4.10 must not compensate by touching the ledger. It is flagged on the refund queue and here.
* **Store credit has no wallet.** No ``StoreCredit`` / ``GiftCard`` / ``CreditBalance`` model exists
  anywhere in the repo. ``resolution="store_credit"`` drafts the SAME credit note and it stays
  unapplied until AR consumes it through ``PaymentAllocation``. The credit note IS the store credit.
* **No cash refund.** ``accounting.Payment(direction="out")`` posts Dr AP-liability / Cr Bank, which
  is the wrong account for a customer refund, and ``Payment.bank_account`` is a non-null PROTECT FK
  SCM has no business choosing. ``refund_method`` is a RECORDED INTENT; AR disburses.
"""
import datetime
import json

from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.ReturnsManagement.ReturnReasons import CREDIT_BEARING_DISPOSITIONS


class ReturnAuthorization(TenantNumbered):
    """A customer's authorisation to send goods back [RMA-]. Posts no stock and no journal."""

    NUMBER_PREFIX = "RMA"

    RETURN_TYPE_CHOICES = [
        ("physical", "Physical return"),
        ("credit_only", "Credit only (no goods coming back)"),
    ]
    SOURCE_CHOICES = [
        ("portal", "Customer portal"),
        ("csr", "Customer service"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("marketplace", "Marketplace"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("awaiting_receipt", "Awaiting receipt"),
        ("partially_received", "Partially received"),
        ("received", "Received"),
        ("settled", "Settled"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    RESOLUTION_CHOICES = [
        ("refund", "Refund"),
        ("store_credit", "Store credit"),
        ("exchange", "Exchange"),
        ("repair", "Repair"),
        ("keep_item", "Keep the item (returnless refund)"),
        ("none", "No resolution yet"),
    ]
    REFUND_METHOD_CHOICES = [
        ("original_tender", "Original tender"),
        ("bank_transfer", "Bank transfer"),
        ("store_credit", "Store credit"),
        ("none", "None"),
    ]
    RETURN_METHOD_CHOICES = [
        ("mail_prepaid", "Mail — prepaid label"),
        ("mail_shopper_paid", "Mail — customer pays"),
        ("drop_off", "Drop-off point"),
        ("in_store", "In store"),
        ("pickup", "Collection from the customer"),
        ("keep_item", "Keep the item"),
    ]

    #: Header states whose fields a CSR may still edit. Once a return is approved it is a promise
    #: made to a customer, so the same posture as ``SalesOrder.EDITABLE_STATUSES``.
    EDITABLE_STATUSES = ("draft", "requested")
    #: States that still count as live work on any queue or roll-up.
    OPEN_STATUSES = ("draft", "requested", "approved", "awaiting_receipt", "partially_received",
                     "received")
    #: Nothing may be posted, received or credited against these.
    TERMINAL_STATUSES = ("settled", "closed", "cancelled", "rejected")
    #: States in which the public token page resolves. Draft and cancelled 404 rather than leak —
    #: the state guard lives in the LOOKUP (the ``kb_public`` pattern), not in a template if-block.
    PUBLIC_STATUSES = ("requested", "approved", "awaiting_receipt", "partially_received",
                       "received", "settled")
    #: Only these may print a return slip — the spirit of ``coa_print`` refusing an unissued
    #: certificate. A slip for an unapproved return is a document that looks real and is not.
    LABEL_STATUSES = ("approved", "awaiting_receipt", "partially_received")

    customer = models.ForeignKey("core.Party", on_delete=models.PROTECT,
                                 related_name="scm_return_authorizations")
    sales_order = models.ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="scm_return_authorizations")
    return_type = models.CharField(max_length=12, choices=RETURN_TYPE_CHOICES, default="physical")
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default="csr")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft",
                              editable=False)

    policy = models.ForeignKey("scm.ReturnPolicy", on_delete=models.PROTECT, null=True, blank=True,
                               related_name="return_authorizations")
    policy_snapshot = models.TextField(
        blank=True, editable=False,
        help_text="The evaluated eligibility verdict, frozen as JSON at approval. Editing the "
                  "policy next month cannot rewrite last month's decision")

    requested_on = models.DateField()
    approved_on = models.DateField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                    editable=False, related_name="scm_return_approvals")
    rejected_reason = models.CharField(max_length=255, blank=True, editable=False)

    resolution = models.CharField(max_length=14, choices=RESOLUTION_CHOICES, default="refund")
    refund_method = models.CharField(
        max_length=16, choices=REFUND_METHOD_CHOICES, default="original_tender",
        help_text="A RECORDED INTENT only — SCM never creates a payment. Accounts Receivable "
                  "disburses against the credit note")

    return_method = models.CharField(max_length=18, choices=RETURN_METHOD_CHOICES,
                                     default="mail_prepaid")
    dropoff_location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="scm_return_dropoffs")
    return_carrier = models.ForeignKey("scm.Carrier", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="scm_return_authorizations",
                                       help_text="The 4.6 carrier master — not free text")
    return_tracking_number = models.CharField(max_length=64, blank=True)
    return_label_url = models.URLField(
        blank=True,
        help_text="Pasted by a human after buying the label elsewhere. There is no carrier API in "
                  "this repo — the 4.6 Shipment.carrier_tracking_number posture")
    label_cost = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                     validators=[MinValueValidator(ZERO)])

    # --- the public token surface (written by the PUBLIC page, never by a form) ------------------
    customer_shipped_on = models.DateField(
        null=True, blank=True, editable=False,
        help_text="Stamped by the customer on the public token page through a conditional UPDATE")
    public_token = models.CharField(max_length=64, unique=True, editable=False, null=True,
                                    blank=True)
    portal_note = models.CharField(max_length=500, blank=True, editable=False,
                                   help_text="Customer free text from the public page, truncated "
                                             "on write")

    counterparty_rma_number = models.CharField(
        max_length=64, blank=True,
        help_text="A marketplace's or a customer's own reference for this return")
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.PROTECT, null=True, blank=True,
        related_name="scm_return_authorizations",
        help_text="Taken from the sales order at creation; the credit-note action refuses without it")

    advance_refund = models.BooleanField(
        default=False,
        help_text="Money went back before the goods came in. There is no card hold and no "
                  "auto-clawback — the exposure report lists these and the claw-back is a manual "
                  "credit-note reversal in Accounting")
    advance_refund_deadline = models.DateField(null=True, blank=True)

    # --- the accounting hand-off: ONE writer each, both editable=False ---------------------------
    credit_note = models.ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False,
                                    related_name="scm_return_authorizations")
    replacement_order = models.ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True,
                                          blank=True, editable=False,
                                          related_name="scm_replacement_for_returns")

    # --- the settlement figures: ONE writer, returnauthorization_draft_credit_note ---------------
    refund_subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                          editable=False)
    fee_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    credit_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                       editable=False)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_on", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_rma_tnt_status_idx"),
            models.Index(fields=["tenant", "customer"], name="scm_rma_tnt_cust_idx"),
            models.Index(fields=["tenant", "requested_on"], name="scm_rma_tnt_reqon_idx"),
            models.Index(fields=["tenant", "return_type"], name="scm_rma_tnt_type_idx"),
            models.Index(fields=["tenant", "source"], name="scm_rma_tnt_source_idx"),
        ]

    def save(self, *args, **kwargs):
        """Mint the unguessable public token ONCE, then hand off to ``TenantNumbered.save``.

        ``secrets.token_urlsafe(32)`` — the ``crm.Case`` / ``crm.KnowledgeArticle`` mechanism, from
        the CSPRNG, because this token is the ONLY credential guarding the public status page.

        **Stated residual risk:** the token never expires, cannot be rotated and cannot be revoked —
        no token in this codebase can. A forwarded link is permanent read access to one RMA.
        """
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(32)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number or 'RMA'} · {self.customer_id and self.customer.name}"

    def clean(self):
        super().clean()
        if self.sales_order_id and self.customer_id and self.sales_order.customer_id != self.customer_id:
            raise ValidationError(
                {"sales_order": f"{self.sales_order.number} belongs to "
                                f"{self.sales_order.customer.name}, not {self.customer.name}."})
        if self.advance_refund and self.advance_refund_deadline is None:
            raise ValidationError(
                {"advance_refund_deadline": "An advance refund needs a deadline — it is the only "
                                            "thing that makes the exposure report actionable."})
        if self.return_type == "credit_only" and self.return_method != "keep_item":
            # Not fatal to the business, but the two fields would then contradict each other on the
            # printed page: "credit only" and "post it back to us".
            raise ValidationError(
                {"return_method": "A credit-only return asks for nothing back — set the return "
                                  "method to 'Keep the item'."})

    # --- derived (nothing below is stored) -------------------------------------------------------
    # NONE of these names may ever be reused as a queryset annotation (§7.3). Every list-page
    # aggregate in 4.10 carries an `_agg` suffix precisely so an annotation can never shadow a
    # property and make a template silently render the wrong number.
    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_terminal(self):
        return self.status in self.TERMINAL_STATUSES

    @property
    def quantity_requested_total(self):
        return sum((line.quantity_requested or ZERO for line in self.lines.all()), ZERO)

    @property
    def quantity_approved_total(self):
        return sum((line.quantity_approved or ZERO for line in self.lines.all()), ZERO)

    @property
    def quantity_received_total(self):
        """Everything physically back, INCLUDING rows still at ``received_pending``.

        Anyone who later "optimises" this to count only decided rows will under-report what came
        back and make the bench look empty while it is full — see ``ReturnLine.quantity_received``.
        """
        return sum((line.quantity_received for line in self.lines.all()), ZERO)

    @property
    def is_fully_received(self):
        approved = self.quantity_approved_total
        return approved > ZERO and self.quantity_received_total >= approved

    @property
    def is_overdue_shipment(self):
        """Approved, the customer said nothing, and the deadline we gave them has passed.

        Uses the policy's own window as the grace period rather than a hard-coded number, so a
        90-day policy does not chase a customer on day 15.
        """
        if self.status not in ("approved", "awaiting_receipt") or self.customer_shipped_on:
            return False
        if self.approved_on is None:
            return False
        grace = self.policy.window_days if self.policy_id else 30
        return timezone.localdate() > self.approved_on + datetime.timedelta(days=grace)

    @property
    def days_open(self):
        return max((timezone.localdate() - self.requested_on).days, 0) if self.requested_on else 0

    @property
    def is_settleable(self):
        """Whether this RMA has something to credit — THE credit-only trap, made executable.

        A ``credit_only`` RMA never gets a disposition row, so a queue keyed on "has received
        goods" would drop it forever: perfectly valid work that looks abandoned. Every queue in
        4.10 (``refund_queue``, ``returndisposition_list``, ``returns_awaiting_disposition``)
        branches on ``return_type`` for exactly this reason, and there is a test that says so.
        """
        if self.status in ("draft", "requested", "rejected", "cancelled"):
            return False
        if self.return_type == "credit_only":
            return self.quantity_approved_total > ZERO
        return any(line.credit_quantity > ZERO for line in self.lines.all())

    @property
    def settlement_figures(self):
        """The (subtotal, fee, tax, total) a credit note WOULD carry, computed live from the rows.

        Read by the refund queue and by the draft-credit-note action; the four stored columns are
        written only when that action actually runs, so the page can show a proposal without
        anything on the record claiming a credit was issued.
        """
        subtotal, fee, tax = ZERO, ZERO, ZERO
        for line in self.lines.all():
            qty = line.credit_quantity
            if qty <= ZERO:
                continue
            line_subtotal = q2(qty * (line.unit_price or ZERO))
            subtotal += line_subtotal
            fee += q2(line.line_fee or ZERO)
            tax += q2(line_subtotal * (line.tax_pct or ZERO) / Decimal("100"))
        return q2(subtotal), q2(fee), q2(tax), q2(subtotal + tax - fee)

    @property
    def snapshot(self):
        """``policy_snapshot`` decoded, or ``{}``. Never raises — it is display data on a page that
        must still render when an old row holds something unparseable."""
        if not self.policy_snapshot:
            return {}
        try:
            value = json.loads(self.policy_snapshot)
        except (ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}


class ReturnLine(models.Model):
    """One item coming back on an RMA. Tenant-less — reached only through its authorisation.

    Three money/quantity fields that look redundant and are not:

    * ``unit_price`` is what the customer PAID. It sizes the credit.
    * ``unit_cost`` is what the unit COST US. It seeds the restock cost. A deliberately separate
      column so that nobody restocks at the sale price — ``_post_stock_move`` calls
      ``item.apply_receipt()`` for ANY positive quantity, which would roll ``Item.average_cost``
      up toward the selling price and overstate ``Item.total_value()`` and the valuation report.
    * ``tax_pct`` is a snapshot of ``SalesOrderLine.tax_pct``. Without it every refund silently
      under-credits the customer by the VAT/GST: ``Invoice.recalc_totals()`` computes tax as
      ``line_total × tax_rate_pct / 100``, so carrying the rate across is all that is required —
      and forgetting it is invisible until a customer counts their money.
    """

    return_authorization = models.ForeignKey("scm.ReturnAuthorization", on_delete=models.CASCADE,
                                             related_name="lines")
    sales_order_line = models.ForeignKey("scm.SalesOrderLine", on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name="scm_return_lines")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="scm_return_lines")
    description = models.CharField(max_length=255, blank=True)
    quantity_requested = models.DecimalField(max_digits=14, decimal_places=4,
                                             validators=[MinValueValidator(Decimal("0.0001"))])
    quantity_approved = models.DecimalField(max_digits=14, decimal_places=4, default=ZERO,
                                            validators=[MinValueValidator(ZERO)])
    reason = models.ForeignKey("scm.ReturnReason", on_delete=models.PROTECT,
                               related_name="return_lines")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                     validators=[MinValueValidator(ZERO)],
                                     help_text="What the customer PAID — sizes the credit")
    tax_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO,
                                  validators=[MinValueValidator(ZERO),
                                              MaxValueValidator(Decimal("100"))],
                                  help_text="Snapshot of the sold line's tax rate — carried onto "
                                            "the credit note so the refund includes the tax")
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=ZERO,
                                    validators=[MinValueValidator(ZERO)],
                                    help_text="What the unit COST us — seeds the restock cost. "
                                              "NEVER restock at unit_price")
    line_fee = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                   validators=[MinValueValidator(ZERO)],
                                   help_text="Restocking / handling fee netted off this line's credit")
    condition_reported = models.CharField(max_length=120, blank=True,
                                          help_text="What the CUSTOMER says the condition is — the "
                                                    "grade on the bench is what we found")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="scm_return_lines")
    photo = models.ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="scm_return_lines",
                              help_text="CSR-attached evidence — makes ReturnReason.requires_photo "
                                        "satisfiable. Customer upload is deferred")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        sku = self.item.sku if self.item_id else (self.description or "line")
        return f"{sku} ×{self.quantity_requested}"

    def clean(self):
        super().clean()
        if (self.quantity_approved or ZERO) > (self.quantity_requested or ZERO):
            raise ValidationError(
                {"quantity_approved": "More is approved than the customer asked to return."})
        if self.lot_serial_id and self.item_id and self.lot_serial.item_id != self.item_id:
            raise ValidationError(
                {"lot_serial": f"{self.lot_serial.number} belongs to {self.lot_serial.item.sku}, "
                               f"not {self.item.sku}."})
        if self.sales_order_line_id and self.item_id and self.sales_order_line.item_id \
                and self.sales_order_line.item_id != self.item_id:
            raise ValidationError(
                {"sales_order_line": "That order line is for a different item."})

    # --- derived (nothing below is stored) -------------------------------------------------------
    @property
    def quantity_received(self):
        """The sum of EVERY disposition row, ``received_pending`` INCLUDED.

        This is a rule, not an oversight. A unit on the bench with no decision yet is a unit that
        physically came back; filtering it out would tell the CSR nothing arrived while it sits in
        front of the grader. There is a test that receives, leaves the row pending, and asserts
        this figure is non-zero.
        """
        return self.dispositions.aggregate(s=Sum("quantity"))["s"] or ZERO

    @property
    def quantity_outstanding(self):
        expected = self.quantity_approved or self.quantity_requested or ZERO
        remaining = expected - self.quantity_received
        return remaining if remaining > ZERO else ZERO

    @property
    def credit_quantity(self):
        """How much of this line the customer gets money back for.

        Derived from the DISPOSITION ROWS, never from ``quantity_approved`` — approving a return
        and actually receiving it are different events, and crediting the approval would refund
        goods that never arrived. The one exception is a ``credit_only`` RMA, which by definition
        has no rows: there its approved quantity IS the credited quantity.
        """
        if self.return_authorization.return_type == "credit_only":
            return self.quantity_approved or ZERO
        return (self.dispositions.filter(disposition__in=CREDIT_BEARING_DISPOSITIONS)
                .aggregate(s=Sum("quantity"))["s"] or ZERO)

    @property
    def line_credit(self):
        """Gross credit minus this line's fee — what a credit note line pair would net to."""
        gross = q2(self.credit_quantity * (self.unit_price or ZERO))
        return q2(gross - (self.line_fee or ZERO))

    @property
    def line_tax(self):
        return q2(self.credit_quantity * (self.unit_price or ZERO) * (self.tax_pct or ZERO)
                  / Decimal("100"))
