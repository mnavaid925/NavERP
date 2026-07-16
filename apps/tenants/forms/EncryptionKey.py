"""tenants — EncryptionKey forms (split from apps/tenants/forms.py)."""
from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    EncryptionKey,
)


class EncryptionKeyForm(TenantModelForm):
    # Only the name is user-set; the secret is generated server-side and shown once (L20/L25).
    class Meta:
        model = EncryptionKey
        fields = ["name"]
