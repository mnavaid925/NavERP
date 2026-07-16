"""core — PartyRelationship forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    PartyRelationship,
)


class PartyRelationshipForm(TenantModelForm):
    class Meta:
        model = PartyRelationship
        fields = ["from_party", "to_party", "kind"]
