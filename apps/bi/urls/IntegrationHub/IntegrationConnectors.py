from django.urls import path

from apps.bi.views.IntegrationHub import IntegrationConnectors as views

urlpatterns = [
    path("connectors/", views.integration_connector_list, name="integration_connector_list"),
    path("connectors/create/", views.integration_connector_create, name="integration_connector_create"),
    path("connectors/<int:pk>/", views.integration_connector_detail, name="integration_connector_detail"),
    path("connectors/<int:pk>/edit/", views.integration_connector_edit, name="integration_connector_edit"),
    path("connectors/<int:pk>/delete/", views.integration_connector_delete, name="integration_connector_delete"),
    path("connectors/<int:pk>/ping/", views.integration_connector_ping, name="integration_connector_ping"),
]
