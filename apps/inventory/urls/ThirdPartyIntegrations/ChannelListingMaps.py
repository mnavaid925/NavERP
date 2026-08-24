"""Inventory 5.19 Third-Party Integrations & API — ChannelListingMap URL patterns."""
from django.urls import path

from apps.inventory.views.ThirdPartyIntegrations.ChannelListingMaps import (
    listingmap_create,
    listingmap_delete,
    listingmap_detail,
    listingmap_edit,
    listingmap_list,
)

urlpatterns = [
    path("listings/", listingmap_list, name="listingmap_list"),
    path("listings/add/", listingmap_create, name="listingmap_create"),
    path("listings/<int:pk>/", listingmap_detail, name="listingmap_detail"),
    path("listings/<int:pk>/edit/", listingmap_edit, name="listingmap_edit"),
    path("listings/<int:pk>/delete/", listingmap_delete, name="listingmap_delete"),
]
