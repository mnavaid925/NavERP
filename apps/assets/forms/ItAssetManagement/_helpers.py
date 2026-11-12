"""Shared form helpers for Module 11.18 IT Asset Management."""

from django.core.exceptions import ValidationError


def scope_tenant_querysets(form, tenant_field_models):
    """Scope every tenant-owned and user FK queryset strictly to ``form.tenant``."""
    tenant = getattr(form, "tenant", None)
    for field_name, model_cls in tenant_field_models.items():
        if field_name not in form.fields:
            continue
        if tenant is None:
            form.fields[field_name].queryset = model_cls.objects.none()
            continue
        qs = model_cls.objects.filter(tenant=tenant)
        if model_cls.__name__ == "EmployeeProfile":
            qs = qs.select_related("party")
        elif model_cls.__name__ == "PurchaseOrder":
            qs = qs.select_related("vendor")
        form.fields[field_name].queryset = qs


def normalize_json_dict_value(value):
    """Ensure blank JSONField dict submissions resolve to ``{}`` instead of ``None``."""
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValidationError("Resource tags must be a valid JSON object (e.g. {\"env\": \"prod\"}).")
    return value


def validate_masked_key_ref(value):
    """Require masked/reference-only strings so raw activation keys are not stored."""
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) >= 16 and "*" not in raw and "x" not in raw.lower() and "-" in raw and raw.replace("-", "").isalnum():
        raise ValidationError(
            "Enter a masked license key reference only (e.g. MS365-****-9X2K), not a raw unmasked activation key."
        )
    return raw
