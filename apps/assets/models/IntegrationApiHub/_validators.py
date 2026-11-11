"""Shared model validation helpers for Integration & API Hub (11.15)."""

from django.core.exceptions import ObjectDoesNotExist


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
