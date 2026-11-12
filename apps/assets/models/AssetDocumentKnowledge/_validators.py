"""Shared validation and attachment metadata helpers for Module 11.16."""

import hashlib
import os

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

FISHBONE_6M_KEYS = frozenset(
    {"machine", "method", "material", "manpower", "measurement", "environment"}
)
OPEN_CLASSIFICATIONS = ("public_floor", "internal_tech")


def readable_asset_document_q(user, prefix=""):
    """Build a Q filter restricting restricted_eng/confidential AssetDocuments to owner/reviewer/admins."""
    if user is None:
        return Q(**{f"{prefix}access_classification__in": OPEN_CLASSIFICATIONS})
    if not getattr(user, "is_authenticated", False):
        return Q(pk__in=[])
    if getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False):
        return Q()
    return (
        Q(**{f"{prefix}access_classification__in": OPEN_CLASSIFICATIONS})
        | Q(**{f"{prefix}owner_id": user.id})
        | Q(**{f"{prefix}reviewer_id": user.id})
    )


def is_asset_document_readable(doc, user):
    """Return True if ``user`` is permitted to access ``doc`` under its access_classification."""
    if doc is None:
        return False
    if doc.access_classification in OPEN_CLASSIFICATIONS:
        return True
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False):
        return True
    return doc.owner_id == user.id or doc.reviewer_id == user.id


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
    """Verify tenant is present and every populated ForeignKey belongs to the same tenant."""
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


def validate_supersedes_chain(instance, errors, field_name="supersedes", max_depth=25):
    """Prevent self-references, bounded depth overflow, and cycles on revision chains."""
    parent_id = getattr(instance, f"{field_name}_id", None)
    if parent_id is None:
        return
    if instance.pk is not None and parent_id == instance.pk:
        add_field_error(errors, field_name, "A record cannot supersede itself.")
        return

    seen = {instance.pk} if instance.pk is not None else set()
    try:
        current = getattr(instance, field_name)
    except ObjectDoesNotExist:
        add_field_error(errors, field_name, "Superseded revision no longer exists.")
        return

    depth = 0
    while current is not None and depth < max_depth:
        if current.pk in seen:
            add_field_error(
                errors,
                field_name,
                "Revision chain cannot contain a circular reference.",
            )
            return
        seen.add(current.pk)
        next_id = getattr(current, f"{field_name}_id", None)
        if next_id is None:
            return
        current = type(instance).objects.filter(pk=next_id).only("pk", f"{field_name}_id").first()
        depth += 1

    if current is not None:
        add_field_error(
            errors,
            field_name,
            f"Revision chain exceeds maximum supported depth of {max_depth}.",
        )


def compute_uploaded_file_metadata(file_field):
    """Return (original_filename, size_bytes, sha256_hex) for a FileField without consuming stream."""
    if not file_field or not getattr(file_field, "name", ""):
        return "", 0, ""

    base_name = os.path.basename(str(file_field.name)).strip()[:255]
    raw_file = getattr(file_field, "file", None)
    if raw_file is None:
        try:
            size_val = int(getattr(file_field, "size", 0) or 0)
        except (OSError, ValueError, TypeError):
            size_val = 0
        return base_name, size_val, ""

    digest = hashlib.sha256()
    total_size = 0
    seekable = hasattr(raw_file, "seek")
    opened_here = False
    try:
        if getattr(raw_file, "closed", False):
            file_field.open("rb")
            raw_file = file_field.file
            opened_here = True
        if seekable:
            try:
                raw_file.seek(0)
            except (OSError, ValueError):
                pass
        chunks = raw_file.chunks() if hasattr(raw_file, "chunks") else iter(lambda: raw_file.read(65536), b"")
        for chunk in chunks:
            if chunk:
                digest.update(chunk)
                total_size += len(chunk)
        if seekable:
            try:
                raw_file.seek(0)
            except (OSError, ValueError):
                pass
        return base_name, total_size, digest.hexdigest()
    except (OSError, ValueError):
        return base_name, 0, ""
    finally:
        if opened_here:
            try:
                raw_file.close()
            except OSError:
                pass


def validate_dict_list_field(
    value,
    errors,
    field_name,
    *,
    max_items,
    required_keys=(),
    label="Items",
):
    """Validate bounded JSON list-of-dicts fields (procedure steps, LOTO points, 5-Whys)."""
    if value in (None, ""):
        return
    if not isinstance(value, list):
        add_field_error(errors, field_name, f"{label} must be a JSON array of objects.")
        return
    if len(value) > max_items:
        add_field_error(errors, field_name, f"{label} cannot exceed {max_items} entries.")
        return
    for idx, entry in enumerate(value, start=1):
        if not isinstance(entry, dict):
            add_field_error(errors, field_name, f"{label} item #{idx} must be a JSON object.")
            return
        for key in required_keys:
            if key not in entry or str(entry.get(key) or "").strip() == "":
                add_field_error(
                    errors,
                    field_name,
                    f"{label} item #{idx} is missing required '{key}' text.",
                )
                return


def validate_contributing_factors(value, errors, field_name="contributing_factors"):
    """Validate optional Fishbone 6M mapping against allowed keys."""
    if value in (None, ""):
        return
    if not isinstance(value, dict):
        add_field_error(
            errors,
            field_name,
            "Contributing factors must be a JSON object keyed by Fishbone 6M category.",
        )
        return
    unknown = sorted(set(value.keys()) - FISHBONE_6M_KEYS)
    if unknown:
        add_field_error(
            errors,
            field_name,
            f"Unsupported 6M categories: {', '.join(unknown)}. Allowed: {', '.join(sorted(FISHBONE_6M_KEYS))}.",
        )
