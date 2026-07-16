"""tenants — SubscriptionInvoice forms (split from apps/tenants/forms.py)."""
from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    SubscriptionInvoice,
)


class SubscriptionInvoiceForm(TenantModelForm):
    class Meta:
        model = SubscriptionInvoice
        fields = ["subscription", "status", "amount", "issued_on", "due_on"]
