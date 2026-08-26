"""Procurement 6.4 Vendor Management — Vendor Invoice Submission [VIS-].

The **submit invoices** bullet, supplier side: through the vendor portal a supplier files
header-level invoice data against (usually) one of their own purchase orders, and this
register is where procurement staff REVIEW those filings — accept or reject.

NO GL posting happens here, ever. Acceptance is a review decision only; the bill itself is
keyed into Accounting › Accounts Payable afterwards (L29 discipline: this app never writes
the ledger).
"""
from django.conf import settings

from apps.procurement.models._base import *  # noqa: F401,F403


class VendorInvoiceSubmission(TenantNumbered):
    """One supplier-filed invoice awaiting a procurement review decision [VIS-]."""

    NUMBER_PREFIX = "VIS"

    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    supplier = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT,
        related_name="procurement_invoice_submissions",
        help_text="The supplier who filed this invoice")
    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_invoice_submissions",
        help_text="The PO this invoices against, if any")
    invoice_ref = models.CharField(
        max_length=64, help_text="The supplier's own invoice number")
    invoice_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text="Header total as the supplier states it")
    note = models.TextField(blank=True,
                            help_text="The supplier's message to procurement")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="submitted")

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_vis_submitted", editable=False,
        help_text="The portal login that filed it")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_vis_reviewed", editable=False)
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_vis_tnt_status_idx"),
            models.Index(fields=["tenant", "supplier"], name="prc_vis_tnt_supp_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.invoice_ref}"

    def clean(self):
        super().clean()
        errors = {}
        if self.amount is not None and self.amount <= ZERO:
            errors["amount"] = "Enter an amount greater than zero."
        if self.supplier_id and getattr(self.supplier, "tenant_id", None) != self.tenant_id:
            errors["supplier"] = "That record belongs to another workspace."
        if self.purchase_order_id:
            if getattr(self.purchase_order, "tenant_id", None) != self.tenant_id:
                errors["purchase_order"] = "That record belongs to another workspace."
            elif self.supplier_id and self.purchase_order.vendor_id != self.supplier_id:
                errors["purchase_order"] = "That PO belongs to a different supplier."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Clamp BEFORE persisting so a hand-fed oversized Decimal degrades to the column
        # shape instead of dying as a driver DataError.
        self.amount = q2(self.amount or ZERO)
        super().save(*args, **kwargs)
