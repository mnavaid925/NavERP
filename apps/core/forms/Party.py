"""core — Party forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    Party,
)


class PartyForm(TenantModelForm):
    class Meta:
        model = Party
        fields = ["kind", "name", "tax_id"]
