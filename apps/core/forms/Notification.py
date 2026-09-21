"""core — 0.12 forms (notification & communication)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    NotificationChannel,
    NotificationPreference,
    NotificationRule,
    NotificationTemplate,
    ProviderConfig,
)


class NotificationChannelForm(TenantModelForm):
    class Meta:
        model = NotificationChannel
        fields = ["kind", "label", "is_enabled", "notes"]


class NotificationTemplateForm(TenantModelForm):
    class Meta:
        model = NotificationTemplate
        fields = ["code", "name", "channel_kind", "subject", "body", "locale", "module_slug",
                  "is_active"]
        widgets = {"body": forms.Textarea(attrs={"class": "form-textarea", "rows": 8})}

    def clean_body(self):
        """Refuse a body that will not render.

        A stored template is rendered later, so a syntax error saved now becomes a broken message at
        send time. The engine tolerates a broken template at render (so it cannot 500 a page), which
        makes catching it HERE the only place it can be caught at all.
        """
        from django.template import Template, TemplateSyntaxError
        body = self.cleaned_data.get("body") or ""
        try:
            Template(body)
        except TemplateSyntaxError as exc:
            raise forms.ValidationError("That template does not compile: %s" % exc)
        return body


class NotificationRuleForm(TenantModelForm):
    class Meta:
        model = NotificationRule
        fields = ["name", "event", "module_slug", "channel", "template", "audience_kind",
                  "audience_role", "audience_user", "digest", "priority", "is_active", "notes"]

    def clean(self):
        """Enforce the audience pairing here as well as in `Model.clean()`.

        `ModelForm` DOES run `Model.clean()` for a `ModelForm` — but only through
        `_post_clean`, which skips fields already in `self._errors`. Putting the rule here means the
        error attaches to the field the operator must fix rather than surfacing as a non-field error.
        """
        cleaned = super().clean()
        kind = cleaned.get("audience_kind")
        if kind == "role" and not cleaned.get("audience_role"):
            self.add_error("audience_role", "Choose the role this rule notifies.")
        if kind == "user" and not cleaned.get("audience_user"):
            self.add_error("audience_user", "Choose the user this rule notifies.")
        return cleaned


class NotificationPreferenceForm(TenantModelForm):
    """A member's own opt-out. `user` is set by the view for self-service, or chosen by an admin."""

    class Meta:
        model = NotificationPreference
        fields = ["user", "event", "channel_kind", "is_enabled"]


class ProviderConfigForm(TenantModelForm):
    class Meta:
        model = ProviderConfig
        fields = ["channel_kind", "label", "priority", "host", "port", "from_address",
                  "api_endpoint", "credential_env_var", "is_active", "notes"]

    def clean_credential_env_var(self):
        """Refuse anything that looks like a secret rather than a variable NAME.

        The field exists so a credential can be FOUND at send time without the credential living in
        the database, where it would land in every backup and every admin page. An operator pasting
        the secret itself is the exact mistake this check exists to catch.
        """
        value = (self.cleaned_data.get("credential_env_var") or "").strip()
        if not value:
            return ""
        looks_like_a_name = all(ch.isupper() or ch.isdigit() or ch == "_" for ch in value)
        if not looks_like_a_name:
            raise forms.ValidationError(
                "Enter the NAME of the environment variable (upper case, e.g. SMTP_PASSWORD), "
                "not the secret itself.")
        return value
