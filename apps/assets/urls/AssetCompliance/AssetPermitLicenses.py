from django.urls import path

from apps.assets.views.AssetCompliance import AssetPermitLicenses as views

urlpatterns = [
    path("compliance/permits/", views.asset_permit_license_list, name="asset_permit_license_list"),
    path("compliance/permits/create/", views.asset_permit_license_create, name="asset_permit_license_create"),
    path("compliance/permits/<int:pk>/", views.asset_permit_license_detail, name="asset_permit_license_detail"),
    path("compliance/permits/<int:pk>/edit/", views.asset_permit_license_edit, name="asset_permit_license_edit"),
    path("compliance/permits/<int:pk>/delete/", views.asset_permit_license_delete, name="asset_permit_license_delete"),
    path("compliance/permits/<int:pk>/renew/", views.asset_permit_license_renew, name="asset_permit_license_renew"),
]
