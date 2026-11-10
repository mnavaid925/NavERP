from django.urls import path

from apps.assets.views.AssetCompliance import AssetComplianceFrameworks as views

urlpatterns = [
    path("compliance/frameworks/", views.asset_compliance_framework_list, name="asset_compliance_framework_list"),
    path("compliance/frameworks/create/", views.asset_compliance_framework_create, name="asset_compliance_framework_create"),
    path("compliance/frameworks/<int:pk>/", views.asset_compliance_framework_detail, name="asset_compliance_framework_detail"),
    path("compliance/frameworks/<int:pk>/edit/", views.asset_compliance_framework_edit, name="asset_compliance_framework_edit"),
    path("compliance/frameworks/<int:pk>/delete/", views.asset_compliance_framework_delete, name="asset_compliance_framework_delete"),
]
