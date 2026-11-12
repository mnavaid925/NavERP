"""Shared form helpers for Module 11.17 Space & Facility Asset Management."""

from apps.assets.models.SpaceFacilityAsset._validators import validate_safe_floor_plan_upload

__all__ = ["scope_tenant_querysets", "validate_safe_floor_plan_upload"]


def scope_tenant_querysets(form, tenant_field_models):
    """Scope every tenant-owned and user ForeignKey queryset strictly to ``form.tenant``."""
    tenant = getattr(form, "tenant", None)
    for field_name, model_cls in tenant_field_models.items():
        if field_name not in form.fields:
            continue
        if tenant is None:
            form.fields[field_name].queryset = model_cls.objects.none()
        else:
            qs = model_cls.objects.filter(tenant=tenant)
            if (
                field_name == "parent"
                and getattr(form.instance, "pk", None) is not None
                and isinstance(form.instance, model_cls)
            ):
                qs = qs.exclude(pk=form.instance.pk)
            form.fields[field_name].queryset = qs
