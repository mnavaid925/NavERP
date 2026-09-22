"""Projects 7.18 — ProjectIntegrationConnector URL patterns."""
from django.urls import path

from apps.projects.views.IntegrationApiHub import Connectors as views

urlpatterns = [
    path("integration/connectors/", views.ixc_list, name="ixc_list"),
    path("integration/connectors/add/", views.ixc_create, name="ixc_create"),
    path("integration/connectors/erp/", views.ixc_list, {"domain": "erp"}, name="ixc_erp_list"),
    path("integration/connectors/crm/", views.ixc_list, {"domain": "crm"}, name="ixc_crm_list"),
    path("integration/connectors/hris/", views.ixc_list, {"domain": "hris"}, name="ixc_hris_list"),
    path("integration/connectors/devops/", views.ixc_list, {"domain": "devops"}, name="ixc_devops_list"),
    path("integration/connectors/storage/", views.ixc_list, {"domain": "storage"}, name="ixc_storage_list"),
    path("integration/connectors/<int:pk>/", views.ixc_detail, name="ixc_detail"),
    path("integration/connectors/<int:pk>/edit/", views.ixc_edit, name="ixc_edit"),
    path("integration/connectors/<int:pk>/delete/", views.ixc_delete, name="ixc_delete"),
    path("integration/connectors/<int:pk>/rotate-credential/", views.ixc_rotate_credential, name="ixc_rotate_credential"),
    path("integration/connectors/<int:pk>/test/", views.ixc_test, name="ixc_test"),
    path("integration/connectors/<int:pk>/toggle/", views.ixc_toggle_active, name="ixc_toggle_active"),
    path("integration/connectors/<int:pk>/health/", views.connector_health, name="connector_health"),
]
