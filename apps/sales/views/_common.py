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


def sales_scope(queryset, request, owner_field):
    return apply_data_scope(queryset, request, "sales", owner_field)


def sales_leads(request):
    from apps.crm.models import Lead

    return sales_scope(Lead.objects.filter(tenant=request.tenant), request, "owner")


def sales_object(request, model, owner_field, pk, queryset=None, select_related=()):
    base = queryset if queryset is not None else model.objects.filter(tenant=request.tenant)
    base = sales_scope(base, request, owner_field)
    if select_related:
        base = base.select_related(*select_related)
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


def csv_export_response(request, *, filename, dataset, headers, rows, filters=None):
    bounded_rows = list(islice(rows, 5000))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([csv_safe(value) for value in headers])
    for row in bounded_rows:
        writer.writerow([csv_safe(value) for value in row])
    safe_filters = {
        str(key): csv_safe(value)[:120]
        for key, value in (filters or {}).items()
        if value not in (None, "")
    }
    write_audit_log(
        request.user,
        None,
        "update",
        {"action": "export", "dataset": dataset, "filters": safe_filters, "row_count": len(bounded_rows)},
        tenant=request.tenant,
    )
    return response
