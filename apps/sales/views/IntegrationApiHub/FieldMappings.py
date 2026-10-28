"""Sales 8.18 — SalesFieldMapping views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.IntegrationApiHub.FieldMappings import SalesFieldMappingForm
from apps.sales.models.IntegrationApiHub.Connectors import SalesIntegrationConnector
from apps.sales.models.IntegrationApiHub.FieldMappings import (
    DIRECTION_CHOICES,
    TARGET_ENTITY_CHOICES,
    SalesFieldMapping,
)


@login_required
def sfm_list(request):
    tenant = request.tenant
    qs = SalesFieldMapping.objects.filter(tenant=tenant).select_related("connector")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(local_field__icontains=q)
            | Q(remote_field__icontains=q)
            | Q(default_value__icontains=q)
            | Q(connector__name__icontains=q)
        )

    connector_id = request.GET.get("connector", "").strip()
    if connector_id and connector_id.isdigit():
        qs = qs.filter(connector_id=int(connector_id))

    target_entity = request.GET.get("target_entity", "").strip()
    if target_entity:
        qs = qs.filter(target_entity=target_entity)

    direction = request.GET.get("direction", "").strip()
    if direction:
        qs = qs.filter(direction=direction)

    page_obj = paginate(request, qs, per_page=20)
    paginator = page_obj.paginator
    connectors = SalesIntegrationConnector.objects.filter(tenant=tenant)

    context = {
        "mappings": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "connector_id": as_db_int(connector_id),
        "target_entity": target_entity,
        "direction": direction,
        "connectors": connectors,
        "entity_choices": TARGET_ENTITY_CHOICES,
        "direction_choices": DIRECTION_CHOICES,
    }
    return render(request, "sales/integrationapihub/fieldmappings/list.html", context)


@login_required
def sfm_detail(request, pk):
    mapping = get_object_or_404(
        SalesFieldMapping.objects.filter(tenant=request.tenant).select_related("connector"),
        pk=pk,
    )
    context = {"mapping": mapping}
    return render(request, "sales/integrationapihub/fieldmappings/detail.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sfm_create(request):
    tenant = request.tenant
    initial = {}
    conn_param = request.GET.get("connector", "").strip()
    if conn_param and conn_param.isdigit():
        initial["connector"] = int(conn_param)

    if request.method == "POST":
        form = SalesFieldMappingForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=tenant)
            messages.success(request, f"Field mapping '{obj.local_field} → {obj.remote_field}' created.")
            return redirect("sales:sfm_detail", pk=obj.pk)
    else:
        form = SalesFieldMappingForm(tenant=tenant, initial=initial)

    context = {
        "form": form,
        "is_edit": False,
        "mapping": None,
    }
    return render(request, "sales/integrationapihub/fieldmappings/form.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sfm_edit(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesFieldMapping.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = SalesFieldMappingForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=tenant)
            messages.success(request, f"Field mapping '{obj.local_field} → {obj.remote_field}' updated.")
            return redirect("sales:sfm_detail", pk=obj.pk)
    else:
        form = SalesFieldMappingForm(instance=obj, tenant=tenant)

    context = {
        "form": form,
        "is_edit": True,
        "mapping": obj,
    }
    return render(request, "sales/integrationapihub/fieldmappings/form.html", context)


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def sfm_delete(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesFieldMapping.objects.filter(tenant=tenant), pk=pk)
    connector_id = obj.connector_id
    label = f"{obj.local_field} → {obj.remote_field}"
    write_audit_log(request.user, obj, "delete", tenant=tenant)
    obj.delete()
    messages.success(request, f"Field mapping '{label}' deleted.")
    return redirect("sales:sic_detail", pk=connector_id)
