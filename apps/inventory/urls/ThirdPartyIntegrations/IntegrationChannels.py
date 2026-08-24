"""Inventory 5.19 Third-Party Integrations & API — IntegrationChannel URL patterns."""
from django.urls import path

from apps.inventory.views.ThirdPartyIntegrations.IntegrationChannels import (
    integrationchannel_create,
    integrationchannel_delete,
    integrationchannel_detail,
    integrationchannel_edit,
    integrationchannel_list,
    integrationchannel_rotate_key,
    integrationchannel_sync,
)

urlpatterns = [
    path("channels/", integrationchannel_list, name="integrationchannel_list"),
    path("channels/add/", integrationchannel_create, name="integrationchannel_create"),
    path("channels/<int:pk>/", integrationchannel_detail, name="integrationchannel_detail"),
    path("channels/<int:pk>/edit/", integrationchannel_edit, name="integrationchannel_edit"),
    path("channels/<int:pk>/delete/", integrationchannel_delete, name="integrationchannel_delete"),
    path("channels/<int:pk>/rotate-key/", integrationchannel_rotate_key, name="integrationchannel_rotate_key"),
    path("channels/<int:pk>/sync/", integrationchannel_sync, name="integrationchannel_sync"),
]
