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
        # `owner` is scoped HERE, deliberately, and self-sufficiently.
        #
        # The previous code built `User.objects.filter(is_active=True)` and applied the tenant filter
        # only `if self.tenant is not None`, so a tenant-less form offered EVERY workspace's active
        # users. `User.__str__` returns the email, so the <select> rendered other tenants' addresses.
        # Measured on the dev DB: 28 rows across 6 distinct tenant values. It was reachable --
        # `ixc_create` carries only `@login_required` (no tenant guard), and the superuser `admin`
        # holds `tenant=None` by design.
        #
        # The `else` branch is the fix: "no tenant" means no tenant-owned object is selectable. This is
        # written out in full rather than inherited from `TenantModelForm`, because the base class
        # deliberately leaves the queryset unnarrowed when `tenant is None` so that `_reject_foreign`
        # can return its precise "belongs to another workspace" message (that behaviour is pinned by
        # committed tests in projects/procurement/scm). A form that is reachable WITHOUT a tenant must
        # therefore narrow explicitly, and this is one.
        owner_qs = User.objects.filter(is_active=True)
        if self.tenant is not None:
            owner_qs = owner_qs.filter(tenant=self.tenant)
        else:
            owner_qs = owner_qs.none()
        self.fields["owner"].queryset = owner_qs

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
