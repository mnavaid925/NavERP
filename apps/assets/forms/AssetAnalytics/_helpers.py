"""Shared tenant queryset scoping helpers for Asset Analytics & BI forms."""

from decimal import Decimal

ZERO = Decimal("0.00")


def scope_tenant_fields(form, tenant_field_models, global_querysets=None):
    """
    Filter tenant-owned ForeignKey/ModelChoice fields to ``form.tenant`` without
    filtering global reference tables such as ``accounting.Currency``, and return
    empty querysets when ``form.tenant`` is None.
    """
    tenant = getattr(form, "tenant", None)
    for field_name, model_cls in tenant_field_models.items():
        if field_name in form.fields:
            if tenant is not None:
                form.fields[field_name].queryset = model_cls.objects.filter(tenant=tenant)
            else:
                form.fields[field_name].queryset = model_cls.objects.none()
    if global_querysets:
        for field_name, qs in global_querysets.items():
            if field_name in form.fields:
                form.fields[field_name].queryset = qs


def validate_non_negative_fields(form, cleaned, field_names):
    """Attach clean field errors when any Decimal/numeric field is negative."""
    for field_name in field_names:
        val = cleaned.get(field_name)
        if val is not None and val < ZERO:
            form.add_error(field_name, "Amount cannot be negative.")
