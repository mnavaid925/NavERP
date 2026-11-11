"""Shared model validation helpers for Integration & API Hub (11.15)."""

import json

from django.core.exceptions import ObjectDoesNotExist, ValidationError


def _reject_json_constant(value):
    raise ValueError(f"Non-standard JSON constant {value!r} is not allowed.")


def validate_json_object(raw_value, field_label="JSON field", max_bytes=65536):
    """Validate optional JSON text: size-bounded, finite numbers, dict root."""
    raw = (raw_value or "").strip()
    if not raw:
        return None
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValidationError(
            f"{field_label} exceeds maximum size of {max_bytes // 1024} KB."
        )
    try:
        parsed = json.loads(raw, parse_constant=_reject_json_constant)
    except (ValueError, RecursionError) as exc:
        raise ValidationError(
            f"{field_label} must be valid standard JSON syntax."
        ) from exc
    if not isinstance(parsed, dict):
        raise ValidationError(f"{field_label} must be a JSON object ({{...}}).")
    return parsed


def add_field_error(errors, field_name, message):
    """Append a validation message to an error dict cleanly."""
    existing = errors.get(field_name)
    if existing is None:
        errors[field_name] = [message]
    elif isinstance(existing, list):
        existing.append(message)
    else:
        errors[field_name] = [existing, message]


def validate_tenant_fks(instance, errors, field_names):
    """Ensure every populated tenant-scoped FK belongs to the instance tenant."""
    tenant_id = getattr(instance, "tenant_id", None)
    if not tenant_id:
        return
    for field_name in field_names:
        if getattr(instance, f"{field_name}_id", None) is None:
            continue
        try:
            related_obj = getattr(instance, field_name)
        except ObjectDoesNotExist:
            add_field_error(
                errors, field_name, "Selected record no longer exists."
            )
            continue
        if (
            related_obj is not None
            and getattr(related_obj, "tenant_id", None) != tenant_id
        ):
            add_field_error(
                errors,
                field_name,
                "Selected record must belong to the same tenant.",
            )
