from django.urls import path

from apps.assets.views.AssetWarrantyInsurance import AssetWarranties as views

urlpatterns = [
    path("warranty-insurance/warranties/", views.asset_warranty_list, name="asset_warranty_list"),
    path("warranty-insurance/warranties/create/", views.asset_warranty_create, name="asset_warranty_create"),
    path("warranty-insurance/warranties/<int:pk>/", views.asset_warranty_detail, name="asset_warranty_detail"),
    path("warranty-insurance/warranties/<int:pk>/edit/", views.asset_warranty_edit, name="asset_warranty_edit"),
    path("warranty-insurance/warranties/<int:pk>/delete/", views.asset_warranty_delete, name="asset_warranty_delete"),
    path("warranty-insurance/warranties/<int:pk>/activate/", views.asset_warranty_activate, name="asset_warranty_activate"),
    path("warranty-insurance/warranties/<int:pk>/renew/", views.asset_warranty_renew, name="asset_warranty_renew"),
    path("warranty-insurance/warranties/<int:pk>/void/", views.asset_warranty_void, name="asset_warranty_void"),
]
