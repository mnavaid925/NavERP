"""Shared validation and date-arithmetic helpers for Module 11.18 IT Asset Management."""

from calendar import monthrange
from datetime import date

from django.core.exceptions import ValidationError


_TOKEN_PREFIXES = ("AKIA", "ASIA", "sk_", "pk_", "ghp_", "gho_", "glpat-", "xoxb-", "xoxp-")


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


def validate_masked_key_ref(value):
    """Require masked/reference-only strings so raw activation keys or tokens are not stored."""
    raw = (value or "").strip()
    if not raw:
        return ""
    is_masked = "*" in raw or "xxxx" in raw.lower()
    if is_masked:
        return raw

    segments = raw.split("-")
    looks_multi_segment_key = len(segments) >= 3 and all(
        seg.isalnum() and len(seg) >= 3 for seg in segments
    )
    compact = raw.replace("-", "").replace("_", "").replace("+", "").replace("/", "").replace("=", "")
    looks_long_token = len(raw) >= 16 and compact.isalnum()
    has_token_prefix = raw.startswith(_TOKEN_PREFIXES)

    if has_token_prefix or looks_multi_segment_key or looks_long_token:
        raise ValidationError(
            "Enter a masked license key reference only (e.g. MS365-****-9X2K), not a raw unmasked activation key or token."
        )
    return raw
