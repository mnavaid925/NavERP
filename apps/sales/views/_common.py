from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
