"""CRM 1.2 Sales Force Automation — Products forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Product,
)


class ProductForm(TenantModelForm):
    class Meta:
        model = Product
        fields = ["name", "sku", "product_type", "unit_price", "cost", "tax_pct",
                  "is_active", "description"]
