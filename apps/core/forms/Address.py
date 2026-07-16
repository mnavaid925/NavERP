"""core — Address forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    Address,
)


class AddressForm(TenantModelForm):
    class Meta:
        model = Address
        fields = ["party", "kind", "line1", "city", "country"]
