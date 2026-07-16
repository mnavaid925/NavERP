"""core — PartyRole forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    PartyRole,
)


class PartyRoleForm(TenantModelForm):
    class Meta:
        model = PartyRole
        fields = ["party", "role", "status", "start_date"]
