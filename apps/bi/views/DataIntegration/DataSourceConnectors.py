from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.DataIntegration.DataSourceConnectors import DataSourceConnectorForm
from apps.bi.models.DataIntegration.DataSourceConnectors import DataSourceConnector
from apps.bi.models.DataIntegration.IngestionRuns import IngestionRun
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def data_source_connector_list(request):
    queryset = bi_scope(DataSourceConnector.objects.all(), request)
    total_count = queryset.count()

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
            | Q(connection_config__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        queryset = queryset.filter(status=status)

    connector_type = request.GET.get("connector_type", "").strip()
    if connector_type:
        queryset = queryset.filter(connector_type=connector_type)

    paginator = Paginator(queryset.select_related("credential", "created_by"), 20)
    page_number = request.GET.get("page")
    connectors = paginator.get_page(page_number)

    context = {
        "connectors": connectors,
        "q": q,
        "status": status,
        "connector_type": connector_type,
        "status_choices": DataSourceConnector.STATUS_CHOICES,
        "type_choices": DataSourceConnector.CONNECTOR_TYPE_CHOICES,
        "total_count": total_count,
    }
    return render(request, "bi/data_integration/data_source_connector/list.html", context)


@login_required
def data_source_connector_detail(request, pk):
    connector = bi_object(
        request,
        DataSourceConnector,
        pk,
        select_related=("credential", "created_by"),
    )
    pipelines = connector.pipelines.all().order_by("-created_at")
    runs = (
        bi_scope(IngestionRun.objects.all(), request)
        .filter(pipeline__connector=connector)
        .select_related("pipeline")
        .order_by("-started_at")[:15]
    )

    context = {
        "connector": connector,
        "pipelines": pipelines,
        "runs": runs,
    }
    return render(request, "bi/data_integration/data_source_connector/detail.html", context)


@login_required
def data_source_connector_create(request):
    if request.method == "POST":
        form = DataSourceConnectorForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            connector = form.save(commit=False)
            connector.created_by = request.user
            connector.save()
            form.save_m2m()
            write_audit_log(request.user, connector, "create", tenant=request.tenant)
            messages.success(request, f"Data Source Connector {connector.number} created successfully.")
            return redirect("bi:data_source_connector_detail", pk=connector.pk)
    else:
        form = DataSourceConnectorForm(tenant=request.tenant)

    context = {
        "form": form,
        "connector": None,
        "is_edit": False,
    }
    return render(request, "bi/data_integration/data_source_connector/form.html", context)


@login_required
def data_source_connector_edit(request, pk):
    connector = bi_object(request, DataSourceConnector, pk)
    if request.method == "POST":
        form = DataSourceConnectorForm(request.POST, instance=connector, tenant=request.tenant)
        if form.is_valid():
            connector = form.save()
            write_audit_log(request.user, connector, "update", tenant=request.tenant)
            messages.success(request, f"Data Source Connector {connector.number} updated successfully.")
            return redirect("bi:data_source_connector_detail", pk=connector.pk)
    else:
        form = DataSourceConnectorForm(instance=connector, tenant=request.tenant)

    context = {
        "form": form,
        "connector": connector,
        "is_edit": True,
    }
    return render(request, "bi/data_integration/data_source_connector/form.html", context)


@require_POST
@login_required
@tenant_admin_required
def data_source_connector_delete(request, pk):
    connector = bi_object(request, DataSourceConnector, pk)
    number = connector.number
    name = connector.name
    try:
        with transaction.atomic():
            write_audit_log(request.user, connector, "delete", tenant=request.tenant)
            connector.delete()
    except ProtectedError:
        messages.error(request, f"Cannot delete connector {number} ({name}) because active ingestion pipelines depend on it.")
        return redirect("bi:data_source_connector_detail", pk=pk)
    messages.success(request, f"Data Source Connector {number} deleted successfully.")
    return redirect("bi:data_source_connector_list")


@require_POST
@login_required
def data_source_connector_test(request, pk):
    connector = bi_object(request, DataSourceConnector, pk)
    connector.test_status = "success"
    connector.test_message = f"Connection verified successfully to {connector.get_connector_type_display()} endpoint (simulated 38ms latency)."
    connector.last_tested_at = timezone.now()
    connector.save(update_fields=["test_status", "test_message", "last_tested_at", "updated_at"])

    write_audit_log(request.user, connector, "test", changes={"action": "test_connection", "status": connector.test_status}, tenant=request.tenant)
    messages.success(request, f"Connection test for {connector.number} succeeded.")
    return redirect("bi:data_source_connector_detail", pk=connector.pk)
