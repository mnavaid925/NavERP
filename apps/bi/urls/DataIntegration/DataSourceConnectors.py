from django.urls import path

from apps.bi.views.DataIntegration import DataSourceConnectors as views

urlpatterns = [
    path("connectors/", views.data_source_connector_list, name="data_source_connector_list"),
    path("connectors/create/", views.data_source_connector_create, name="data_source_connector_create"),
    path("connectors/<int:pk>/", views.data_source_connector_detail, name="data_source_connector_detail"),
    path("connectors/<int:pk>/edit/", views.data_source_connector_edit, name="data_source_connector_edit"),
    path("connectors/<int:pk>/delete/", views.data_source_connector_delete, name="data_source_connector_delete"),
    path("connectors/<int:pk>/test/", views.data_source_connector_test, name="data_source_connector_test"),
]
