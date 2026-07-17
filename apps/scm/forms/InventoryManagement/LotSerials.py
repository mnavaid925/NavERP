"""SCM 4.3 Inventory Management — LotSerial form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import LotSerial


class LotSerialForm(TenantModelForm):
    class Meta:
        model = LotSerial
        fields = ["item", "kind", "number", "expiry_date", "status", "notes"]
        # item is tenant-scoped (scm.Item has a tenant field) so the base class scopes the dropdown.
