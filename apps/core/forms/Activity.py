"""core — Activity forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    Activity,
)


class ActivityForm(TenantModelForm):
    class Meta:
        model = Activity
        fields = ["owner", "party", "kind", "subject", "status", "due_at"]
