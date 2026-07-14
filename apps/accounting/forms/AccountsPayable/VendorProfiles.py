"""Accounting 2.3 Accounts Payable — VendorProfiles forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.forms._common import _active_currencies
from apps.accounting.models import (
    VendorProfile,
)


class VendorProfileForm(TenantModelForm):
    class Meta:
        model = VendorProfile
        fields = ["party", "payment_terms", "default_expense_account", "currency", "is_1099",
                  "is_active", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if self.tenant is not None:
            self.fields["party"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="vendor").distinct()
            )
