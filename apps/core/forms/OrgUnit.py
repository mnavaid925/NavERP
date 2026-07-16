"""core — OrgUnit forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    OrgUnit,
)


class OrgUnitForm(TenantModelForm):
    class Meta:
        model = OrgUnit
        fields = ["kind", "name", "parent"]
