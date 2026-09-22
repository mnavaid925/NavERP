"""Projects 7.18 — ConnectorFieldMapping views."""
from django.core.paginator import Paginator
from django.db.models import Q

from apps.projects.forms.IntegrationApiHub.FieldMappings import ConnectorFieldMappingForm
from apps.projects.models.IntegrationApiHub.Connectors import ProjectIntegrationConnector
from apps.projects.models.IntegrationApiHub.FieldMappings import ConnectorFieldMapping
from apps.projects.views._common import *


@login_required
def ixm_list(request):
    qs = ConnectorFieldMapping.objects.filter(tenant=request.tenant).select_related("connector")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(local_field__icontains=q) | Q(remote_field__icontains=q))
    connector_id = request.GET.get("connector", "").strip()
    if connector_id and connector_id.isdigit():
        qs = qs.filter(connector_id=connector_id)
    direction = request.GET.get("direction", "").strip()
    if direction:
        qs = qs.filter(direction=direction)
    transform = request.GET.get("transform", "").strip()
    if transform:
        qs = qs.filter(transform=transform)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/integrationapihub/mapping/list.html",
        {
            "mappings": page_obj.object_list,
            "page_obj": page_obj,
            "connectors": ProjectIntegrationConnector.objects.filter(tenant=request.tenant),
            "connector_id": connector_id,
            "direction_choices": ConnectorFieldMapping.DIRECTION_CHOICES,
            "transform_choices": ConnectorFieldMapping.TRANSFORM_CHOICES,
            "q": q,
        },
    )


@login_required
def ixm_detail(request, pk):
    mapping = get_object_or_404(
        ConnectorFieldMapping.objects.select_related("connector"), pk=pk, tenant=request.tenant
    )
    return render(request, "projects/integrationapihub/mapping/detail.html", {"mapping": mapping})


def _ixm_save(request, form, action):
    obj = form.save(commit=False)
    obj.tenant = request.tenant
    obj.save()
    form.save_m2m()
    write_audit_log(request.user, obj, action)
    return obj


@login_required
def ixm_create(request):
    form = ConnectorFieldMappingForm(request.POST or None, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        obj = _ixm_save(request, form, "create")
        messages.success(request, "Field mapping created.")
        return redirect("projects:ixm_detail", pk=obj.pk)
    return render(request, "projects/integrationapihub/mapping/form.html", {"form": form})


@login_required
def ixm_edit(request, pk):
    mapping = get_object_or_404(ConnectorFieldMapping, pk=pk, tenant=request.tenant)
    form = ConnectorFieldMappingForm(request.POST or None, instance=mapping, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        obj = _ixm_save(request, form, "update")
        messages.success(request, "Field mapping updated.")
        return redirect("projects:ixm_detail", pk=obj.pk)
    return render(
        request,
        "projects/integrationapihub/mapping/form.html",
        {"form": form, "is_edit": True, "mapping": mapping},
    )


@login_required
@require_POST
@tenant_admin_required
def ixm_delete(request, pk):
    mapping = get_object_or_404(ConnectorFieldMapping, pk=pk, tenant=request.tenant)
    label = f"{mapping.local_field} → {mapping.remote_field}"
    mapping.delete()
    write_audit_log(request.user, None, "delete", changes={"mapping": label}, tenant=request.tenant)
    messages.success(request, "Field mapping deleted.")
    return redirect("projects:ixm_list")
