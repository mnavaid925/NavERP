"""Shared filter and CSV export helpers for Fleet & Vehicle Management (11.19)."""

import csv

from django.http import HttpResponse

PAGE_SIZE = 15


def is_tenant_admin_user(user):
    """Return True if user holds tenant admin or superuser privileges."""
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def parse_pos_int(raw_value):
    """Parse a bounded positive integer parameter, returning None if invalid."""
    raw = (str(raw_value) if raw_value is not None else "").strip()
    if not raw or len(raw) > 10 or not raw.isascii() or not raw.isdigit():
        return None
    val = int(raw)
    return val if 0 < val <= 2_147_483_647 else None


def apply_choice_filter(qs, request, param_name, field_name=None, allowed_values=None):
    """Apply an exact GET choice filter cleanly while ignoring unrecognized choice values."""
    val = request.GET.get(param_name, "").strip()
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
    return qs.filter(**{field_name or param_name: val})


def csv_safe(val):
    """Neutralize potential CSV formula injection for spreadsheet software."""
    if val is None:
        return ""
    text = str(val).strip()
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def csv_export_response(filename, headers, row_generator):
    """Stream CSV rows with anti-sniff and attachment disposition headers."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow(headers)
    for row in row_generator:
        writer.writerow([csv_safe(cell) for cell in row])
    return response
