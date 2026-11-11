from django.urls import path

from apps.assets.views.IntegrationApiHub import AssetIntegrationConnectors as views

urlpatterns = [
    path(
        "integration/connectors/",
        views.connector_list,
        name="asset_integration_connector_list",
    ),
    path(
        "integration/connectors/create/",
        views.connector_create,
        name="asset_integration_connector_create",
    ),
    path(
        "integration/connectors/<int:pk>/",
        views.connector_detail,
        name="asset_integration_connector_detail",
    ),
    path(
        "integration/connectors/<int:pk>/edit/",
        views.connector_edit,
        name="asset_integration_connector_edit",
    ),
    path(
        "integration/connectors/<int:pk>/delete/",
        views.connector_delete,
        name="asset_integration_connector_delete",
    ),
    path(
        "integration/connectors/<int:pk>/test/",
        views.test_connection,
        name="asset_integration_connector_test",
    ),
    path(
        "integration/connectors/<int:pk>/rotate-secret/",
        views.rotate_secret,
        name="asset_integration_connector_rotate_secret",
    ),
]
