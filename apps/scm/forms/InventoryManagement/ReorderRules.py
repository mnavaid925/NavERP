"""SCM 4.3 Inventory Management — ReorderRule form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import ReorderRule


class ReorderRuleForm(TenantModelForm):
    class Meta:
        model = ReorderRule
        # item + location are tenant-scoped, so the base class scopes both dropdowns.
        fields = ["item", "location", "reorder_point", "safety_stock", "reorder_quantity", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stamp the tenant on the instance up front so Django's own unique(tenant, item, location)
        # validation fires as a friendly form error instead of an IntegrityError at save (the form
        # excludes `tenant`, so without this the uniqueness check would run against tenant=None).
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant
