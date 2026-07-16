"""core — ContactMethod forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    ContactMethod,
)


class ContactMethodForm(TenantModelForm):
    class Meta:
        model = ContactMethod
        fields = ["party", "kind", "value"]
