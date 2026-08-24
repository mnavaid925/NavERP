"""Inventory 5.19 Third-Party Integrations & API — ApiClient form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.models.ThirdPartyIntegrations.ApiClients import ApiClient


class ApiClientForm(TenantUniqueMixin, TenantModelForm):
    """Create/edit an API client [API-]. Token issue/rotate is a VIEW verb, not a form field, and
    ``status`` moves only via the revoke verb — both stay off this form."""

    class Meta:
        model = ApiClient
        fields = [
            "name",
            "protocol",
            "scopes",
            "description",
            "allowed_ips",
            "rate_limit_note",
        ]

    # No _reject_foreign here: ApiClient declares zero FKs (TENANT_SCOPED_FKS = ()), so there is
    # nothing to cross-tenant re-check — TenantUniqueMixin alone covers the (tenant, name) pair.
