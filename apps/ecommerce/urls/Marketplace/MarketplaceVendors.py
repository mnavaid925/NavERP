from django.urls import path

from apps.ecommerce.views.Marketplace import MarketplaceVendorViews as views

urlpatterns = [
    path("marketplace/vendors/", views.marketplacevendor_list, name="marketplacevendor_list"),
    path("marketplace/vendors/create/", views.marketplacevendor_create, name="marketplacevendor_create"),
    path("marketplace/vendors/<int:pk>/", views.marketplacevendor_detail, name="marketplacevendor_detail"),
    path("marketplace/vendors/<int:pk>/edit/", views.marketplacevendor_edit, name="marketplacevendor_edit"),
    path("marketplace/vendors/<int:pk>/delete/", views.marketplacevendor_delete, name="marketplacevendor_delete"),
    path("marketplace/vendors/<int:pk>/verify-kyc/", views.marketplacevendor_verify_kyc, name="marketplacevendor_verify_kyc"),
    path("marketplace/vendors/<int:pk>/suspend/", views.marketplacevendor_suspend, name="marketplacevendor_suspend"),
]
