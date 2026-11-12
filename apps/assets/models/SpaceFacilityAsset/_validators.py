"""Shared validation helpers for Module 11.17 Space & Facility Asset Management models."""

from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist


def add_field_error(errors, field_name, message):
    """Append a validation error message cleanly without clobbering existing messages."""
    existing = errors.get(field_name)
    if existing is None:
        errors[field_name] = [message]
    elif isinstance(existing, list):
        existing.append(message)
    else:
        errors[field_name] = [existing, message]


def validate_tenant_fks(instance, errors, field_names):
    """Verify tenant is present and every populated tenant-owned FK belongs to the same tenant."""
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
                "Selected record must belong to the same workspace tenant.",
            )


def validate_space_parent_cycle(instance, errors, field_name="parent", max_depth=25):
    """Prevent self-parenting, cycles, and excessive hierarchy depth on AssetFacilitySpace.parent."""
    parent_id = getattr(instance, f"{field_name}_id", None)
    if parent_id is None:
        return
    if instance.pk is not None and parent_id == instance.pk:
        add_field_error(errors, field_name, "A facility space cannot be its own parent.")
        return

    seen = {instance.pk} if instance.pk is not None else set()
    try:
        current = getattr(instance, field_name)
    except ObjectDoesNotExist:
        add_field_error(errors, field_name, "Selected parent space no longer exists.")
        return

    depth = 0
    while current is not None and depth < max_depth:
        if current.pk in seen:
            add_field_error(
                errors,
                field_name,
                "Space hierarchy cannot contain a circular parent reference.",
            )
            return
        seen.add(current.pk)
        next_id = getattr(current, f"{field_name}_id", None)
        if next_id is None:
            return
        qs = type(instance).objects.filter(pk=next_id)
        tenant_id = getattr(instance, "tenant_id", None)
        if tenant_id is not None:
            qs = qs.filter(tenant_id=tenant_id)
        current = qs.only("pk", f"{field_name}_id").first()
        depth += 1

    if current is not None:
        add_field_error(
            errors,
            field_name,
            f"Space hierarchy exceeds maximum supported depth of {max_depth}.",
        )


def validate_non_negative(value, errors, field_name, label):
    """Ensure a numeric field is >= 0 when populated."""
    if value is not None and value < Decimal("0.00"):
        add_field_error(errors, field_name, f"{label} cannot be negative.")


def validate_pct_range(value, errors, field_name, label, low=Decimal("0.00"), high=Decimal("100.00")):
    """Ensure a percentage/pin-coordinate value is within [low, high] when populated."""
    if value is not None and (value < low or value > high):
        add_field_error(errors, field_name, f"{label} must be between {low} and {high}.")
