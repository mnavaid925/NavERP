from django.urls import path

from apps.assets.views.AssetMaintenance import AssetServiceContracts as views

urlpatterns = [
    path("service-contracts/", views.asset_service_contract_list, name="asset_service_contract_list"),
    path("service-contracts/create/", views.asset_service_contract_create, name="asset_service_contract_create"),
    path("service-contracts/<int:pk>/", views.asset_service_contract_detail, name="asset_service_contract_detail"),
    path("service-contracts/<int:pk>/edit/", views.asset_service_contract_edit, name="asset_service_contract_edit"),
    path("service-contracts/<int:pk>/delete/", views.asset_service_contract_delete, name="asset_service_contract_delete"),
    path("service-contracts/<int:pk>/activate/", views.asset_service_contract_activate, name="asset_service_contract_activate"),
    path("service-contracts/<int:pk>/record-visit/", views.asset_service_contract_record_visit, name="asset_service_contract_record_visit"),
    path("service-contracts/<int:pk>/renew/", views.asset_service_contract_renew, name="asset_service_contract_renew"),
    path("service-contracts/<int:pk>/terminate/", views.asset_service_contract_terminate, name="asset_service_contract_terminate"),
]
