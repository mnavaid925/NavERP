from django.urls import path

from apps.assets.views.AssetReliability import AssetTelemetryReadings as views

urlpatterns = [
    path("reliability/telemetry/", views.asset_telemetry_reading_list, name="asset_telemetry_reading_list"),
    path("reliability/telemetry/create/", views.asset_telemetry_reading_create, name="asset_telemetry_reading_create"),
    path("reliability/telemetry/<int:pk>/", views.asset_telemetry_reading_detail, name="asset_telemetry_reading_detail"),
    path("reliability/telemetry/<int:pk>/edit/", views.asset_telemetry_reading_edit, name="asset_telemetry_reading_edit"),
    path("reliability/telemetry/<int:pk>/delete/", views.asset_telemetry_reading_delete, name="asset_telemetry_reading_delete"),
    path("reliability/telemetry/<int:pk>/trigger-request/", views.asset_telemetry_reading_trigger_request, name="asset_telemetry_reading_trigger_request"),
    path("reliability/telemetry/<int:pk>/flag-anomaly/", views.asset_telemetry_reading_flag_anomaly, name="asset_telemetry_reading_flag_anomaly"),
]
