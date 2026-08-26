"""Procurement 6.9 Catalog Management — PunchOutEndpoint form.

The shared secret is CREATE-ONLY by construction: the field exists on the form for a new
endpoint and is POPPED the moment an instance exists, so a stored secret can never be
rendered back into HTML nor demanded again on edit.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import PunchOutEndpoint


class PunchOutEndpointForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = PunchOutEndpoint
        # EXCLUDED and why: ``number`` is assigned once by TenantNumbered.save();
        # ``last_session_at`` moves only through record_session().
        fields = ["party", "name", "protocol", "punchout_url", "username",
                  "shared_secret", "enabled", "notes"]
        widgets = {
            # Password input AND never echoed back into the rendered value attribute.
            "shared_secret": forms.PasswordInput(render_value=False),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # WARNING: on EDIT the secret field is removed entirely — it is NEVER rendered nor
            # re-required. This demo build stores the secret verbatim (see the model comment);
            # production must keep only a SHA-256 hash per the tenants.EncryptionKey pattern,
            # at which point "enter a replacement to rotate" becomes the only possible flow.
            self.fields.pop("shared_secret")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["party"])
        return cleaned
