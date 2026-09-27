"""tenants — EntitlementFeature form (0.19, the commercial feature catalog)."""
from django.core.exceptions import ValidationError

from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    EntitlementFeature,
)


class EntitlementFeatureForm(TenantModelForm):
    """`TenantModelForm`, never a plain `ModelForm` ([RULING] 9): `crud_create`/`crud_edit` pass
    `tenant=request.tenant` UNCONDITIONALLY, so a plain ModelForm dies with `TypeError: __init__()
    got an unexpected keyword argument 'tenant'`.

    Excluded from `Meta.fields`:
      * `number` — structurally excluded already, because it is `editable=False` and minted in
        `save()`. Naming it would be belt-and-braces, not load-bearing.
      * `tenant` — set by the view. A user-writable tenant switch is the one field that must never
        be form-writable.

    The `select_options`-required and lowercase-`code` rules are NOT re-implemented here:
    `ModelForm._post_clean()` already calls `instance.full_clean()`, so the model's `clean()` runs,
    and a second copy in the form would only drift.
    """

    class Meta:
        model = EntitlementFeature
        fields = ["code", "name", "description", "privilege_type", "select_options", "status",
                  "is_add_on", "is_active", "notes"]

    def clean(self):
        """The [RULING] 8 duplicate-`code` guard on `(tenant, code)`, on create AND edit.

        The tuple is fully non-nullable, so the DATABASE enforces it — which is exactly why this
        guard exists: without it a duplicate POST raises `IntegrityError` out of `crud_create` /
        `crud_edit` and the operator gets an HTTP 500 instead of a form error.
        """
        super().clean()
        code = (self.cleaned_data.get("code") or "").strip()
        tenant = getattr(self, "tenant", None)
        if not code or tenant is None:
            return self.cleaned_data
        clash = EntitlementFeature.objects.filter(tenant=tenant, code=code)
        # Exclude self on edit, or saving an unchanged record always "clashes" with itself.
        if self.instance and self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise ValidationError({
                "code": "Another feature already uses this code in this workspace.",
            })
        return self.cleaned_data
