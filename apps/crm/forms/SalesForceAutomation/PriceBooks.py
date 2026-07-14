"""CRM 1.2 Sales Force Automation — PriceBooks forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    PriceBook,
)


class PriceBookForm(TenantModelForm):
    class Meta:
        model = PriceBook
        fields = ["name", "currency_code", "region", "tier", "price_adjustment_pct",
                  "is_default", "is_active", "description"]
