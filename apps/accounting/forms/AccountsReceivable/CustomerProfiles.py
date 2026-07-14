"""Accounting 2.4 Accounts Receivable — CustomerProfiles forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.forms._common import _active_currencies
from apps.accounting.models import (
    CustomerProfile,
)


class CustomerProfileForm(TenantModelForm):
    class Meta:
        model = CustomerProfile
        fields = ["party", "payment_terms", "credit_limit", "ar_account", "currency",
                  "credit_on_hold", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if self.tenant is not None:
            self.fields["party"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer").distinct()
            )
