"""SCM 4.6 Transportation Management System — FreightInvoice + FreightInvoiceLine models.

The **freight audit**: a carrier's invoice, broken into charge-type lines (linehaul / fuel /
accessorial / detention …), each with the amount BILLED and the amount the contract EXPECTED. The
audit compares the two within a tolerance and sets ``match_status`` — mirroring the three-way-match
``GoodsReceiptNote.MATCH_STATUS_CHOICES`` precedent already in this app.

Payment is NOT posted here (L29 — ``apps.accounting`` owns the ledger). Once approved, the hand-off
drafts an ``accounting.Bill`` for the carrier's ``party`` and links it by nullable FK; the AP team
approves/pays the Bill in accounting, which is where the journal entry is posted. This model records
the audit + approval and stops at the draft.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class FreightInvoice(TenantNumbered):
    """A carrier freight bill under audit [FRT-]. Amounts are derived from its lines."""

    NUMBER_PREFIX = "FRT"

    # Mirrors GoodsReceiptNote.MATCH_STATUS_CHOICES (the three-way-match precedent).
    MATCH_STATUS_CHOICES = [
        ("not_matched", "Not Matched"),
        ("matched", "Matched"),
        ("price_variance", "Price Variance"),
        ("duplicate", "Duplicate"),
        ("disputed", "Disputed"),
    ]
    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    carrier = models.ForeignKey("scm.Carrier", on_delete=models.PROTECT, related_name="freight_invoices")
    load = models.ForeignKey("scm.Load", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="freight_invoices", help_text="Most carriers bill per trip/load")
    shipment = models.ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="freight_invoices", help_text="For direct/parcel shipments")
    carrier_invoice_number = models.CharField(max_length=64, blank=True,
                                              help_text="The carrier's own invoice reference")
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_freight_invoices")
    # The audit tolerance a variance is judged against — user-editable; default 2%.
    match_tolerance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.00"),
                                              validators=[MinValueValidator(0), MaxValueValidator(100)])
    # All derived — billed/contract summed from lines, variance + statuses set by the audit action.
    billed_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0, editable=False)
    contract_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0, editable=False)
    variance_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0, editable=False)
    variance_pct = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, editable=False)
    match_status = models.CharField(max_length=16, choices=MATCH_STATUS_CHOICES, default="not_matched",
                                    editable=False)
    approval_status = models.CharField(max_length=12, choices=APPROVAL_STATUS_CHOICES, default="pending",
                                       editable=False)
    dispute_reason = models.TextField(blank=True, editable=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_freight_approvals", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    # The hand-off point — a draft accounting.Bill. Nullable, editable=False (set by the action).
    bill = models.ForeignKey("accounting.Bill", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="scm_freight_invoices", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "match_status"], name="scm_frt_tnt_match_idx"),
            models.Index(fields=["tenant", "approval_status"], name="scm_frt_tnt_appr_idx"),
        ]

    def recalc_amounts(self, save=True):
        """Sum billed + contract from the lines, in Python (never an F() expression — the SQLite
        integer-division trap the rest of scm avoids)."""
        billed, contract = ZERO, ZERO
        for line in self.lines.all():
            billed += line.billed_amount or ZERO
            contract += line.contract_amount or ZERO
        self.billed_amount = billed
        self.contract_amount = contract
        self.variance_amount = billed - contract
        self.variance_pct = ((self.variance_amount * 100 / contract).quantize(Decimal("0.01"))
                             if contract > ZERO else None)
        if save:
            self.save(update_fields=["billed_amount", "contract_amount", "variance_amount",
                                     "variance_pct", "updated_at"])

    def run_audit(self, save=True):
        """Set ``match_status`` from the billed-vs-contract variance against the tolerance.

        A same-carrier invoice sharing a non-blank ``carrier_invoice_number`` is flagged ``duplicate``
        (never silently paid twice). Otherwise: within tolerance → ``matched``; outside → the
        ``price_variance`` exception queue. A ``disputed`` invoice is left disputed — the audit does
        not overturn a human's dispute.
        """
        self.recalc_amounts(save=False)
        if self.match_status == "disputed":
            new_status = "disputed"
        elif self.carrier_invoice_number and self._has_duplicate():
            new_status = "duplicate"
        elif self.contract_amount <= ZERO:
            new_status = "not_matched"
        else:
            within = abs(self.variance_pct or ZERO) <= (self.match_tolerance_pct or ZERO)
            new_status = "matched" if within else "price_variance"
        self.match_status = new_status
        if save:
            self.save(update_fields=["billed_amount", "contract_amount", "variance_amount",
                                     "variance_pct", "match_status", "updated_at"])
        return new_status

    def _has_duplicate(self):
        return (FreightInvoice.objects
                .filter(tenant=self.tenant, carrier=self.carrier,
                        carrier_invoice_number=self.carrier_invoice_number)
                .exclude(pk=self.pk)
                .exists())

    @property
    def is_editable(self):
        """Editable until it has been approved/rejected or handed off to a bill."""
        return self.approval_status == "pending" and self.bill_id is None

    @property
    def is_over_billed(self):
        return (self.variance_amount or ZERO) > ZERO

    def __str__(self):
        who = self.carrier.name if self.carrier_id else "?"
        return f"{self.number or 'FRT'} · {who}"


class FreightInvoiceLine(models.Model):
    """One charge line on a freight invoice. Tenant-less child, reached via
    ``freight_invoice.tenant``."""

    CHARGE_TYPE_CHOICES = [
        ("linehaul", "Linehaul"),
        ("fuel_surcharge", "Fuel Surcharge"),
        ("accessorial", "Accessorial"),
        ("detention", "Detention"),
        ("demurrage", "Demurrage"),
        ("tolls", "Tolls"),
        ("other", "Other"),
    ]

    freight_invoice = models.ForeignKey("scm.FreightInvoice", on_delete=models.CASCADE, related_name="lines")
    charge_type = models.CharField(max_length=16, choices=CHARGE_TYPE_CHOICES, default="linehaul")
    description = models.CharField(max_length=255, blank=True)
    billed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                        validators=[MinValueValidator(ZERO)],
                                        help_text="What the carrier billed")
    contract_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                          validators=[MinValueValidator(ZERO)],
                                          help_text="What the rate card expected")

    class Meta:
        ordering = ["id"]

    @property
    def variance_amount(self):
        return (self.billed_amount or ZERO) - (self.contract_amount or ZERO)

    def __str__(self):
        return f"{self.get_charge_type_display()} · {self.billed_amount}"
