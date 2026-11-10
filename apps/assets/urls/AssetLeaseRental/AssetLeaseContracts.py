from django.urls import path

from apps.assets.views.AssetLeaseRental import AssetLeaseContracts as views

urlpatterns = [
    path("leases/", views.asset_lease_contract_list, name="asset_lease_contract_list"),
    path("leases/create/", views.asset_lease_contract_create, name="asset_lease_contract_create"),
    path("leases/<int:pk>/", views.asset_lease_contract_detail, name="asset_lease_contract_detail"),
    path("leases/<int:pk>/edit/", views.asset_lease_contract_edit, name="asset_lease_contract_edit"),
    path("leases/<int:pk>/delete/", views.asset_lease_contract_delete, name="asset_lease_contract_delete"),
    path("leases/<int:pk>/calculate/", views.asset_lease_contract_calculate, name="asset_lease_contract_calculate"),
    path("leases/<int:pk>/activate/", views.asset_lease_contract_activate, name="asset_lease_contract_activate"),
    path("leases/<int:pk>/terminate/", views.asset_lease_contract_terminate, name="asset_lease_contract_terminate"),
]
