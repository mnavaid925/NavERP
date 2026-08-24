"""Inventory 5.19 Third-Party Integrations & API — IntegrationChannel form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import _reject_foreign
from apps.inventory.models.ThirdPartyIntegrations.IntegrationChannels import IntegrationChannel
from apps.scm.models import Location


class IntegrationChannelForm(TenantUniqueMixin, TenantModelForm):
    """Register/maintain an external connection [INT-].

    Structurally excluded (never listed): ``tenant``, ``number``, ``api_key_prefix``,
    ``api_key_hash``, ``last_sync_at``, ``last_run_status`` — all non-editable plumbing.
    The API key itself is issued/rotated by the VIEW verb, never a form field. ``status`` is
    ON the form deliberately: a human-maintained marker, no transport observes anything.
    """

    class Meta:
        model = IntegrationChannel
        fields = [
            "name",
            "kind",
            "platform",
            "direction",
            "auth_method",
            "base_url",
            "external_account_ref",
            "environment",
            "status",
            "trigger_mode",
            "schedule_note",
            "rate_limit_note",
            "default_location",
            "is_active",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["default_location"].queryset = Location.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["default_location"])
        return cleaned
