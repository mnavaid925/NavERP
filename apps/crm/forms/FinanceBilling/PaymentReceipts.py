"""CRM 1.7 Finance & Billing Management — PaymentReceipts forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    PaymentReceipt,
)


class PaymentReceiptForm(TenantModelForm):
    """1.7 Payment Tracking. The optional ``payment`` link is scoped to INBOUND ledger payments
    (customer receipts) for this tenant — outbound vendor payments are never a customer receipt."""

    class Meta:
        model = PaymentReceipt
        fields = ["deal_invoice", "payment", "amount", "received_date", "method",
                  "gateway", "gateway_txn_id", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Scope to this tenant's INBOUND payments; safe empty default if tenant is unknown
        # (defense-in-depth — the create/edit views already guard a tenant-less request).
        if self.tenant is not None:
            self.fields["payment"].queryset = Payment.objects.filter(tenant=self.tenant, direction="in")
        else:
            self.fields["payment"].queryset = Payment.objects.none()
        self.fields["payment"].required = False
