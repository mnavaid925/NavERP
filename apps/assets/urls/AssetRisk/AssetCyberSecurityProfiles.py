from django.urls import path

from apps.assets.views.AssetRisk import AssetCyberSecurityProfiles as views

urlpatterns = [
    path("risk/cybersecurity/", views.asset_cybersecurity_profile_list, name="asset_cybersecurity_profile_list"),
    path("risk/cybersecurity/create/", views.asset_cybersecurity_profile_create, name="asset_cybersecurity_profile_create"),
    path("risk/cybersecurity/<int:pk>/", views.asset_cybersecurity_profile_detail, name="asset_cybersecurity_profile_detail"),
    path("risk/cybersecurity/<int:pk>/edit/", views.asset_cybersecurity_profile_edit, name="asset_cybersecurity_profile_edit"),
    path("risk/cybersecurity/<int:pk>/delete/", views.asset_cybersecurity_profile_delete, name="asset_cybersecurity_profile_delete"),
    path("risk/cybersecurity/<int:pk>/scan/", views.asset_cybersecurity_profile_scan, name="asset_cybersecurity_profile_scan"),
]
