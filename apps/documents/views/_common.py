import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.scoping import apply_data_scope
from apps.core.utils import write_audit_log


def documents_scope(queryset, request, owner_field=None):
    base_qs = queryset.filter(tenant=request.tenant)
    if owner_field:
        return apply_data_scope(base_qs, request, "documents", owner_field)
    return base_qs


def documents_object(request, model, pk, queryset=None, select_related=(), prefetch_related=()):
    base = queryset if queryset is not None else model.objects.all()
    base = base.filter(tenant=request.tenant)
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


def paginate_queryset(queryset, request, per_page=15):
    """Return a Django Page object for queryset using GET 'page' parameter."""
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def parse_int_param(raw):
    """Parse a non-negative integer string, returning (clean_str, int_val|None)."""
    text = (raw or "").strip()
    if text.isdigit():
        return text, int(text)
    return "", None


def _csv_safe(val):
    if val is None:
        return ""
    text = str(val)
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text
