"""SCM 4.3 Inventory Management — ReorderRule form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import ReorderRule


class ReorderRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ReorderRule
        # item + location are tenant-scoped, so the base class scopes both dropdowns.
        fields = ["item", "location", "reorder_point", "safety_stock", "reorder_quantity", "is_active"]
