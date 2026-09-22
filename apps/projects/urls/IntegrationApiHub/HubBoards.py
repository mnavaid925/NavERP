"""Projects 7.18 — integration board URL patterns (hub + monitor)."""
from django.urls import path

from apps.projects.views.IntegrationApiHub import HubBoards as views

urlpatterns = [
    path("integration/hub/", views.integration_hub, name="integration_hub"),
    path("integration/monitor/", views.sync_monitor, name="sync_monitor"),
]
