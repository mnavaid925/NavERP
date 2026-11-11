from django.urls import path

from apps.assets.views.IntegrationApiHub import AssetTelemetryStreams as views

urlpatterns = [
    path(
        "integration/telemetry-streams/",
        views.stream_list,
        name="asset_telemetry_stream_list",
    ),
    path(
        "integration/telemetry-streams/create/",
        views.stream_create,
        name="asset_telemetry_stream_create",
    ),
    path(
        "integration/telemetry-streams/<int:pk>/",
        views.stream_detail,
        name="asset_telemetry_stream_detail",
    ),
    path(
        "integration/telemetry-streams/<int:pk>/edit/",
        views.stream_edit,
        name="asset_telemetry_stream_edit",
    ),
    path(
        "integration/telemetry-streams/<int:pk>/delete/",
        views.stream_delete,
        name="asset_telemetry_stream_delete",
    ),
    path(
        "integration/telemetry-streams/<int:pk>/ingest/",
        views.ingest_sample_reading,
        name="asset_telemetry_stream_ingest",
    ),
]
