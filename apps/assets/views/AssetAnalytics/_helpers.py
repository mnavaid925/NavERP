"""Shared CSV export, filter parsing, and helper utilities for Asset Analytics & BI views."""

import csv
from decimal import Decimal
from itertools import islice

from django.http import HttpResponse

ZERO = Decimal("0.00")
PAGE_SIZE = 15


def parse_pos_int(raw_value):
    """Parse an ASCII non-negative/positive integer query parameter, returning None when invalid."""
    raw = (raw_value or "").strip()
    if not raw or not raw.isascii() or not raw.isdigit():
        return None
    val = int(raw)
    return val if val > 0 else None


def apply_choice_filter(qs, request, param_name, field_name=None, allowed_values=None):
    """Apply an exact GET choice filter to queryset when non-empty and valid."""
    val = request.GET.get(param_name, "").strip()
    if not val:
        return qs
    if allowed_values is not None and val not in allowed_values:
        return qs.none()
    return qs.filter(**{field_name or param_name: val})


def apply_fk_filter(qs, request, param_name, field_name=None):
    """Apply an integer ForeignKey filter cleanly, ignoring malformed non-numeric junk."""
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
