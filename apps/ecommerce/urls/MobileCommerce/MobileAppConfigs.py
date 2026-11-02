from django.urls import path
from apps.ecommerce.views.MobileCommerce import MobileAppConfigs as views

urlpatterns = [
    path("mobile/manifest.json", views.pwa_manifest_json, name="pwa_manifest_json"),
    path("mobile/configs/", views.mobileappconfig_list, name="mobileappconfig_list"),
    path("mobile/configs/new/", views.mobileappconfig_create, name="mobileappconfig_create"),
    path("mobile/configs/<int:pk>/", views.mobileappconfig_detail, name="mobileappconfig_detail"),
    path("mobile/configs/<int:pk>/edit/", views.mobileappconfig_edit, name="mobileappconfig_edit"),
    path("mobile/configs/<int:pk>/delete/", views.mobileappconfig_delete, name="mobileappconfig_delete"),
]
