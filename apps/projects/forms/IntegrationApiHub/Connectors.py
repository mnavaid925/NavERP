"""Projects 7.18 — ProjectIntegrationConnector forms."""
from django import forms
from django.contrib.auth import get_user_model

from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.IntegrationApiHub.Connectors import ProjectIntegrationConnector

User = get_user_model()


class ProjectIntegrationConnectorForm(TenantUniqueMixin, TenantModelForm):
    """Form for creating and updating ProjectIntegrationConnector instances.

    ``credential`` is a declared EXTRA field (write-only): the model column is ``editable=False`` and
    is excluded by construction, so a blank value on edit leaves the stored cipher alone; a non-blank
    value is encrypted once by the model's ``save()`` choke point (never in the form).
    """

    credential = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"class": "form-input"}),
        help_text="Paste the provider token/API key. Stored encrypted; leave blank on edit to keep the current one.",
    )

    class Meta:
        model = ProjectIntegrationConnector
        fields = [
            "project",
            "name",
            "domain",
            "provider",
            "direction",
            "auth_method",
            "base_url",
            "remote_scope_ref",
            "trigger_mode",
            "schedule_note",
            "environment",
            "status",
            "is_active",
            "notify_webhook",
            "owner",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # REFINE the base class's scoping -- do not replace it.
        #
        # `TenantModelForm` has already scoped `owner` to this workspace, and has emptied it when there
        # is no tenant at all (C7). The previous code rebuilt the queryset from
        # `User.objects.filter(is_active=True)` and re-applied the tenant filter itself, which threw the
        # base scoping away and re-opened on the `tenant is None` branch exactly the cross-tenant leak the
        # base class had just closed. Measured on the dev DB before this change:
        # `ProjectIntegrationConnectorForm(tenant=None).fields["owner"].queryset` held all 28 active
        # users across 6 distinct tenant values, and `User.__str__` returns the email -- so the dropdown
        # rendered other tenants' addresses. It was reachable: `ixc_create` is only `@login_required`,
        # and the superuser `admin` carries `tenant=None` by design.
        #
        # Filtering the inherited queryset keeps the `is_active` refinement and inherits the scoping,
        # including the empty case (`.none().filter(...)` is still empty).
        self.fields["owner"].queryset = self.fields["owner"].queryset.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "notify_webhook"])
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw = self.cleaned_data.get("credential")
        if raw:  # blank on edit => keep the stored cipher untouched
            instance.set_credential(raw)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ConnectorTestForm(forms.Form):
    """Simulated connection test — no live payload, no outbound HTTP."""

    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-textarea", "placeholder": "Optional note recorded on the simulated test run."}),
    )
