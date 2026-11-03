from django.urls import path
from apps.ecommerce.views.IntegrationApi import EcommerceConnectors as views

urlpatterns = [
    path("integration-api/", views.integration_api_hub, name="integration_api_hub"),
    path("integration-api/connectors/", views.ecommerce_connector_list, name="ecommerceconnector_list"),
    path("integration-api/connectors/create/", views.ecommerce_connector_create, name="ecommerceconnector_create"),
    path("integration-api/connectors/<int:pk>/", views.ecommerce_connector_detail, name="ecommerceconnector_detail"),
    path("integration-api/connectors/<int:pk>/edit/", views.ecommerce_connector_edit, name="ecommerceconnector_edit"),
    path("integration-api/connectors/<int:pk>/delete/", views.ecommerce_connector_delete, name="ecommerceconnector_delete"),
    path("integration-api/connectors/<int:pk>/test-connection/", views.ecommerce_connector_test_connection, name="ecommerceconnector_test_connection"),
]
