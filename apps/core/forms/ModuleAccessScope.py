"""core — 0.6 module access scope forms."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    ModuleAccessScope,
    SensitiveFieldMask,
)


class ModuleAccessScopeForm(TenantModelForm):
    """`module_number` / `module_slug` / `module_title` are excluded from the EDIT path's spirit but
    kept in `fields` for create — a scope is normally created by the catalog sync, and renaming a
    module's slug by hand would orphan the `LIVE_LINKS` mapping it is keyed against."""

    class Meta:
        model = ModuleAccessScope
        fields = ["module_number", "module_slug", "module_title", "is_enabled", "data_scope",
                  "requires_approval", "mask_sensitive", "period_lock_until", "notes"]

    def clean_module_slug(self):
        slug = (self.cleaned_data.get("module_slug") or "").strip().lower()
        if slug != self.cleaned_data.get("module_slug"):
            raise forms.ValidationError("Use a lowercase slug with no spaces.")
        return slug


class SensitiveFieldMaskForm(TenantModelForm):
    """`exempt_roles` is scoped to the tenant EXPLICITLY.

    `TenantModelForm` narrows `forms.ModelChoiceField` querysets to the tenant, but
    `exempt_roles` is a `ModelMultipleChoiceField`, which is a different class and therefore not
    covered — so without this a tenant admin's picker would list every OTHER workspace's roles and
    let one be attached here. That is a cross-tenant leak in a form, which is exactly the shape the
    project's security lanes hunt for.
    """

    class Meta:
        model = SensitiveFieldMask
        fields = ["scope", "field_name", "mask_style", "exempt_roles", "notes"]
        widgets = {"exempt_roles": forms.CheckboxSelectMultiple()}

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if tenant is not None:
            from apps.accounts.models import Role
            self.fields["exempt_roles"].queryset = Role.objects.filter(tenant=tenant).order_by("name")

    def clean_field_name(self):
        name = (self.cleaned_data.get("field_name") or "").strip()
        if not name.isidentifier():
            raise forms.ValidationError("Enter a single model field name, e.g. bank_account.")
        return name
