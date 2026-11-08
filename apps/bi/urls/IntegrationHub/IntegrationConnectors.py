from django.urls import path

from apps.bi.views.IntegrationHub import IntegrationConnectors as views

urlpatterns = [
    path("integrations/connectors/", views.integration_connector_list, name="integration_connector_list"),
    path("integrations/connectors/create/", views.integration_connector_create, name="integration_connector_create"),
    path("integrations/connectors/<int:pk>/", views.integration_connector_detail, name="integration_connector_detail"),
    path("integrations/connectors/<int:pk>/edit/", views.integration_connector_edit, name="integration_connector_edit"),
    path("integrations/connectors/<int:pk>/delete/", views.integration_connector_delete, name="integration_connector_delete"),
    path("integrations/connectors/<int:pk>/ping/", views.integration_connector_ping, name="integration_connector_ping"),
]
