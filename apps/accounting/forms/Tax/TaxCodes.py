"""Accounting 2.11 Tax — TaxCodes forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    TaxCode,
)


class TaxCodeForm(TenantModelForm):
    class Meta:
        model = TaxCode
        fields = ["name", "jurisdiction", "tax_type", "rate_pct", "payable_account", "is_active"]
