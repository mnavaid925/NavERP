"""Shared filter, pagination, CSV export, and floor-plan download helpers for Module 11.17."""

import csv
from itertools import islice
import os
import re

from django.http import FileResponse, Http404, HttpResponse

PAGE_SIZE = 15
_UNSAFE_FILENAME_RE = re.compile(r'[\r\n"\\/;]+')


def is_tenant_admin_user(user):
    """Return True if user holds tenant admin or superuser privileges."""
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def parse_pos_int(raw_value):
    """Parse a bounded ASCII positive 32-bit integer query parameter, returning None when invalid."""
    raw = (str(raw_value) if raw_value is not None else "").strip()
    if not raw or len(raw) > 10 or not raw.isascii() or not raw.isdigit():
        return None
    val = int(raw)
    return val if 0 < val <= 2_147_483_647 else None


def apply_choice_filter(qs, request, param_name, field_name=None, allowed_values=None):
    """Apply an exact GET choice filter cleanly while ignoring unrecognized choice values."""
    val = (request.GET.get(param_name) or "").strip()
    if not val:
        return qs
    if allowed_values is not None and val not in allowed_values:
        return qs
    return qs.filter(**{field_name or param_name: val})


def apply_fk_filter(qs, request, param_name, field_name=None):
    """Apply an integer ForeignKey filter cleanly while ignoring malformed query values."""
    val = parse_pos_int(request.GET.get(param_name))
    if val is None:
        return qs
    target = field_name or f"{param_name}_id"
    return qs.filter(**{target: val})


def csv_safe(value):
    """Neutralize spreadsheet formula-injection prefixes before writing CSV cells."""
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def csv_export_response(*, filename, headers, rows):
    """Stream up to 10,000 rows as a hardened attachment CSV download."""
    safe_name = "".join(c for c in filename if c.isalnum() or c in ("-", "_", ".")) or "export.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow([csv_safe(h) for h in headers])
    for row in islice(rows, 10000):
        writer.writerow([csv_safe(c) for c in row])
    return response


def serve_protected_floor_plan(
    obj, file_attr="floor_plan_image", original_filename_attr="original_floor_plan_name"
):
    """Stream a stored FileField strictly as a downloadable attachment with nosniff."""
    file_field = getattr(obj, file_attr, None)
    if not file_field or not getattr(file_field, "name", ""):
        raise Http404("No floor plan file uploaded for this space.")
    raw_name = (
        getattr(obj, original_filename_attr, "")
        or os.path.basename(str(file_field.name))
        or "floor-plan"
    )
    clean_name = _UNSAFE_FILENAME_RE.sub("_", os.path.basename(str(raw_name))).strip(". ")
    if not clean_name:
        clean_name = "floor-plan"
    try:
        file_handle = file_field.open("rb")
    except (OSError, ValueError) as exc:
        raise Http404("Stored floor plan file could not be opened.") from exc
    response = FileResponse(file_handle, as_attachment=True, filename=clean_name)
    response["X-Content-Type-Options"] = "nosniff"
    return response
