import csv
from itertools import islice

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.scoping import apply_data_scope
from apps.core.utils import write_audit_log


def ecommerce_scope(queryset, request, owner_field=None):
    if owner_field:
        return apply_data_scope(queryset, request, "ecommerce", owner_field)
    return queryset.filter(tenant=request.tenant)


def ecommerce_object(request, model, pk, queryset=None, select_related=(), prefetch_related=()):
    base = queryset if queryset is not None else model.objects.filter(tenant=request.tenant)
    if select_related:
        base = base.select_related(*select_related)
    if prefetch_related:
        base = base.prefetch_related(*prefetch_related)
    return get_object_or_404(base, pk=pk)


def safe_parse_date(value):
    try:
        return parse_date(value)
    except (TypeError, ValueError):
        return None


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def csv_export_response(request, *, filename, headers, rows):
    bounded_rows = list(islice(rows, 10000))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([csv_safe(h) for h in headers])
    for row in bounded_rows:
        writer.writerow([csv_safe(c) for c in row])
    return response
