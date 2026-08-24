"""Inventory 5.19 Third-Party Integrations & API — ApiClient URL patterns."""
from django.urls import path

from apps.inventory.views.ThirdPartyIntegrations.ApiClients import (
    apiclient_create,
    apiclient_delete,
    apiclient_detail,
    apiclient_edit,
    apiclient_issue_token,
    apiclient_list,
    apiclient_revoke,
)

urlpatterns = [
    path("api-clients/", apiclient_list, name="apiclient_list"),
    path("api-clients/add/", apiclient_create, name="apiclient_create"),
    path("api-clients/<int:pk>/", apiclient_detail, name="apiclient_detail"),
    path("api-clients/<int:pk>/edit/", apiclient_edit, name="apiclient_edit"),
    path("api-clients/<int:pk>/delete/", apiclient_delete, name="apiclient_delete"),
    path("api-clients/<int:pk>/issue-token/", apiclient_issue_token, name="apiclient_issue_token"),
    path("api-clients/<int:pk>/revoke/", apiclient_revoke, name="apiclient_revoke"),
]
