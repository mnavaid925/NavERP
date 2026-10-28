"""Sales 8.18 — SalesIntegrationConnector URL patterns."""
from django.urls import path

from apps.sales.views.IntegrationApiHub.Connectors import (
    sic_create,
    sic_delete,
    sic_detail,
    sic_edit,
    sic_list,
    sic_test,
)

urlpatterns = [
    path("connectors/", sic_list, name="sic_list"),
    path("connectors/create/", sic_create, name="sic_create"),
    path("connectors/<int:pk>/", sic_detail, name="sic_detail"),
    path("connectors/<int:pk>/edit/", sic_edit, name="sic_edit"),
    path("connectors/<int:pk>/delete/", sic_delete, name="sic_delete"),
    path("connectors/<int:pk>/test/", sic_test, name="sic_test"),
]
