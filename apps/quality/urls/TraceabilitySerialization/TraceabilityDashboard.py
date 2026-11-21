from django.urls import path

from apps.quality.views.TraceabilitySerialization import TraceabilityDashboard as views

urlpatterns = [
    path("traceability/", views.traceability_dashboard, name="traceability_dashboard"),
    path("traceability/export/", views.traceability_export_csv, name="traceability_export_csv"),
]
