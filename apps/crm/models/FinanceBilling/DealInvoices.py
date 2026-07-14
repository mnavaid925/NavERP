"""CRM 1.7 Finance & Billing Management — DealInvoices models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ---- 1.7 Invoicing — a CRM wrapper over the ACCOUNTING ledger ----------------------------
# The real AR invoice is an ``accounting.Invoice`` (Module 2 owns the ledger — lesson L29: reuse
# it, never build a second one). ``DealInvoice`` records the *deal context* (opportunity / quote /
# account) of a generated invoice and is created by the one-click quote→invoice conversion
# (``dealinvoice_from_quote``). Issuing / GL-posting + confirmed cash-application stay in
# Accounting (draft hand-off) — CRM only creates the draft and links it.
class DealInvoice(TenantNumbered):
    """Links a CRM deal (Opportunity / Quote) to the ``accounting.Invoice`` it generated."""

    NUMBER_PREFIX = "DINV"

    opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="deal_invoices")
    quote = models.ForeignKey("crm.Quote", on_delete=models.SET_NULL, null=True, blank=True, related_name="deal_invoices")
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_deal_invoices")
    # The generated ledger document (system-of-record). editable=False → set by the view/seeder,
    # never accepted from a form (a user must not re-point a wrapper at an arbitrary invoice).
    invoice = models.ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="crm_deal_invoices")
    # Optional subscription schedule — recurring billing also lives in the ledger.
    recurring_invoice = models.ForeignKey("accounting.RecurringInvoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_deal_invoices")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "opportunity"], name="crm_dinv_tnt_opp_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_dinv_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.invoice_number}"

    # Totals / status / paid amounts are READ THROUGH to the linked ledger invoice — never copied
    # here, so there is a single source of truth. Every accessor guards a missing/unlinked invoice.
    @property
    def invoice_number(self):
        return self.invoice.number if self.invoice_id else "—"

    @property
    def invoice_status(self):
        return self.invoice.status if self.invoice_id else "unlinked"

    @property
    def invoice_status_display(self):
        return self.invoice.get_status_display() if self.invoice_id else "Unlinked"

    @property
    def invoice_total(self):
        return self.invoice.total if self.invoice_id else Decimal("0")

    @property
    def amount_paid(self):
        return self.invoice.amount_paid() if self.invoice_id else Decimal("0")

    @property
    def balance_due(self):
        return self.invoice.balance_due() if self.invoice_id else Decimal("0")
