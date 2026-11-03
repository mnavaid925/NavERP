from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.bi.models.DataIntegration.CdcSyncConfigs import CdcSyncConfig
from apps.bi.models.DataIntegration.DataSourceConnectors import DataSourceConnector
from apps.bi.models.DataIntegration.IngestionPipelines import IngestionPipeline
from apps.bi.models.DataIntegration.IngestionRuns import IngestionRun
from apps.bi.views._common import bi_scope


@login_required
def data_integration_hub(request):
    connectors_qs = bi_scope(DataSourceConnector.objects.all(), request)
    pipelines_qs = bi_scope(IngestionPipeline.objects.all(), request)
    cdc_qs = bi_scope(CdcSyncConfig.objects.all(), request)
    runs_qs = bi_scope(IngestionRun.objects.all(), request)

    total_connectors = connectors_qs.count()
    active_connectors = connectors_qs.filter(status="active").count()

    total_pipelines = pipelines_qs.count()
    active_pipelines = pipelines_qs.filter(status="active").count()

    cdc_streams_count = cdc_qs.count()
    total_runs = runs_qs.count()

    recent_runs = (
        runs_qs.select_related("pipeline", "pipeline__connector")
        .order_by("-started_at")[:10]
    )
    active_pipelines_list = (
        pipelines_qs.filter(status="active")
        .select_related("connector")
        .order_by("-created_at")[:8]
    )
    connectors = connectors_qs.order_by("-created_at")[:6]

    context = {
        "total_connectors": total_connectors,
        "active_connectors": active_connectors,
        "total_pipelines": total_pipelines,
        "active_pipelines": active_pipelines,
        "cdc_streams_count": cdc_streams_count,
        "total_runs": total_runs,
        "recent_runs": recent_runs,
        "active_pipelines_list": active_pipelines_list,
        "connectors": connectors,
    }
    return render(request, "bi/data_integration/data_integration_hub.html", context)
