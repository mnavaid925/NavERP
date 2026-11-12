"""Shared validation and date-arithmetic helpers for Module 11.18 IT Asset Management."""

from calendar import monthrange
from datetime import date


def add_months(base_date, months):
    """Add calendar months to a date while clamping day-of-month safely."""
    if base_date is None:
        return None
    total_months = base_date.month - 1 + int(months)
    year = base_date.year + total_months // 12
    month = total_months % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def add_field_error(errors, field_name, message):
    """Append a ValidationError message under ``field_name`` in an error dict."""
    errors.setdefault(field_name, []).append(message)


def validate_tenant_fks(instance, field_names):
    """Verify every populated tenant-scoped FK belongs to ``instance.tenant_id``."""
    tenant_id = getattr(instance, "tenant_id", None)
    if not tenant_id:
        return {}
    errors = {}
    for field_name in field_names:
        related_obj = getattr(instance, field_name, None)
        if related_obj is not None and getattr(related_obj, "tenant_id", None) != tenant_id:
            add_field_error(errors, field_name, "Selected record belongs to another workspace.")
    return errors
