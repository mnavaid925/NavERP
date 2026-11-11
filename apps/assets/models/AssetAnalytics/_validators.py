"""Shared validation and decimal calculation helpers for Asset Analytics & BI (11.14)."""

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ObjectDoesNotExist

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def q2(value):
    """Quantize a numeric value to 2 decimal places using half-up rounding."""
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def cap_decimal(value, max_abs=Decimal("99999.99")):
    """Clamp a quantized Decimal within safe storage bounds for DecimalField(max_digits=7, decimal_places=2)."""
    val = q2(value)
    if val > max_abs:
        return max_abs
    if val < -max_abs:
        return -max_abs
    return val


def add_field_error(errors, field_name, message):
    """Append a validation message to an error dictionary cleanly."""
    existing = errors.get(field_name)
    if existing is None:
        errors[field_name] = [message]
    elif isinstance(existing, list):
        existing.append(message)
    else:
        errors[field_name] = [existing, message]


def validate_tenant_fks(instance, errors, field_names):
    """Ensure workspace tenant is set and every populated tenant-scoped ForeignKey matches it."""
    tenant_id = getattr(instance, "tenant_id", None)
    if not tenant_id:
        add_field_error(errors, "__all__", "Workspace tenant context is required.")
        return
    for field_name in field_names:
        if getattr(instance, f"{field_name}_id", None) is None:
            continue
        try:
            related_obj = getattr(instance, field_name)
        except ObjectDoesNotExist:
            add_field_error(errors, field_name, "Selected record no longer exists.")
            continue
        if related_obj is not None and getattr(related_obj, "tenant_id", None) != tenant_id:
            add_field_error(
                errors,
                field_name,
                "Selected record must belong to the same tenant.",
            )
