"""core — 0.10 bullets 1 and 2: settings and feature flags.

`SettingDefinition` is the REGISTRY (what settings exist, their type, their default) and
`SettingValue` is the OVERRIDE (what one tenant set). That split is the whole point of bullet 1's
"system-wide defaults with per-tenant and per-module overrides": a definition carries the default, so
a tenant with no row is not a missing setting — it is a tenant taking the default, and
`get_setting()` can say which of the two it read.

Nothing here is a `django.conf.settings` replacement. These are TENANT-level business settings
(currency display, default payment terms, invoice footer), and the engine deliberately does not
expose them to arbitrary keys: `get_setting()` only resolves keys that exist as a definition.
"""
from apps.core.models._base import *  # noqa: F401,F403


class SettingDefinition(models.Model):
    """One configurable setting: its type, its system-wide default, and where it applies."""

    VALUE_TYPE_CHOICES = [
        ("text", "Text"),
        ("integer", "Integer"),
        ("decimal", "Decimal"),
        ("boolean", "Boolean"),
        ("date", "Date"),
        ("choice", "Choice"),
    ]

    key = models.CharField(max_length=120, unique=True,
                           help_text="Stable identifier, e.g. 'accounting.default_payment_terms'.")
    label = models.CharField(max_length=200)
    module_slug = models.CharField(max_length=40, blank=True,
                                   help_text="Which module owns it; blank means platform-wide.")
    value_type = models.CharField(max_length=10, choices=VALUE_TYPE_CHOICES, default="text")
    default_value = models.CharField(max_length=500, blank=True)
    #: For `choice` only, as a JSON list of [value, label] pairs.
    choices = models.JSONField(default=list, blank=True)
    help_text = models.TextField(blank=True)
    #: A setting an operator may NOT override (a platform invariant). Marked rather than hidden, so
    #: the register shows it and the form disables it.
    is_locked = models.BooleanField(
        default=False, help_text="Locked settings show in the register but cannot be overridden.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["module_slug", "key"]
        indexes = [models.Index(fields=["module_slug", "key"], name="setdef_module_key_idx")]

    def __str__(self):
        return self.key


class SettingValue(models.Model):
    """One tenant's override of one setting. Absence means "taking the default"."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="setting_values", db_index=True)
    definition = models.ForeignKey("core.SettingDefinition", on_delete=models.CASCADE,
                                   related_name="values")
    value = models.CharField(max_length=500, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["definition__module_slug", "definition__key"]
        unique_together = ("tenant", "definition")
        indexes = [models.Index(fields=["tenant", "definition"], name="setval_tenant_def_idx")]

    def __str__(self):
        return f"{self.tenant} · {self.definition.key}"
