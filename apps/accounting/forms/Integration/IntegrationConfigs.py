"""Accounting 2.15 Integration & API — IntegrationConfigs forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    IntegrationConfig,
)


class IntegrationConfigForm(TenantModelForm):
    class Meta:
        model = IntegrationConfig
        # api_key_prefix/hash are write-once via the rotate action (never on this form, L20/L25).
        fields = ["name", "provider", "category", "status", "is_active", "notes"]
