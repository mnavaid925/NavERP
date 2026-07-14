"""CRM 1.4 Customer Service & Support — CustomerPortalAccess forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    CustomerPortalAccess,
)


class CustomerPortalAccessForm(TenantModelForm):
    class Meta:
        model = CustomerPortalAccess
        # accepted_at is system-set when the customer activates — excluded.
        fields = ["customer_party", "portal_user", "can_submit_cases", "is_active"]
