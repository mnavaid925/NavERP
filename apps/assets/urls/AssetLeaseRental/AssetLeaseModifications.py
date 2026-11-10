from django.urls import path

from apps.assets.views.AssetLeaseRental import AssetLeaseModifications as views

urlpatterns = [
    path("modifications/", views.asset_lease_modification_list, name="asset_lease_modification_list"),
    path("modifications/create/", views.asset_lease_modification_create, name="asset_lease_modification_create"),
    path("modifications/<int:pk>/", views.asset_lease_modification_detail, name="asset_lease_modification_detail"),
    path("modifications/<int:pk>/edit/", views.asset_lease_modification_edit, name="asset_lease_modification_edit"),
    path("modifications/<int:pk>/delete/", views.asset_lease_modification_delete, name="asset_lease_modification_delete"),
    path("modifications/<int:pk>/approve/", views.asset_lease_modification_approve, name="asset_lease_modification_approve"),
]
