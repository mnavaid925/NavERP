"""CRM 1.12 Inventory & Vendor Management — PartnerPortalAccess forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    PartnerPortalAccess,
)


class PartnerPortalAccessForm(TenantModelForm):
    class Meta:
        model = PartnerPortalAccess
        fields = ["partner_party", "portal_user", "access_level", "can_view_stock",
                  "can_register_leads", "is_active"]
