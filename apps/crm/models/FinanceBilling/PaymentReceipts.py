"""CRM 1.7 Finance & Billing Management — PaymentReceipts models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ---- 1.7 Payment Tracking — a CRM receipt document over a ledger payment -----------------
class PaymentReceipt(TenantNumbered):
    """A customer receipt for a (partial / milestone) payment against a deal invoice.

    The money movement itself is an ``accounting.Payment`` (optional link); this model is the CRM
    receipt *document* (printable) plus payment-gateway metadata. Real gateway webhooks (Stripe /
    PayPal / Razorpay charge confirmation) are deferred — the gateway fields capture the reference."""

    NUMBER_PREFIX = "RCPT"

    METHOD_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("card", "Card"),
        ("cash", "Cash"),
        ("check", "Check"),
        ("paypal", "PayPal"),
        ("stripe", "Stripe"),
        ("razorpay", "Razorpay"),
        ("ach", "ACH"),
        ("wire", "Wire Transfer"),
        ("other", "Other"),
    ]
    GATEWAY_CHOICES = [
        ("manual", "Manual / Offline"),
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("razorpay", "Razorpay"),
    ]

    deal_invoice = models.ForeignKey("crm.DealInvoice", on_delete=models.CASCADE, related_name="receipts")
    # Optional link to the ledger money movement (Module 2 owns Payment + cash application).
    payment = models.ForeignKey("accounting.Payment", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_receipts")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received_date = models.DateField()
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default="bank_transfer")
    gateway = models.CharField(max_length=12, choices=GATEWAY_CHOICES, default="manual")
    gateway_txn_id = models.CharField(max_length=120, blank=True, help_text="External gateway charge / transaction id.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "received_date"], name="crm_rcpt_tnt_date_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.amount}"
