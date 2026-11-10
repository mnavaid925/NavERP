from django.urls import path

from apps.assets.views.AssetCompliance import AssetComplianceAudits as views

urlpatterns = [
    path("compliance/audits/", views.asset_compliance_audit_list, name="asset_compliance_audit_list"),
    path("compliance/audits/create/", views.asset_compliance_audit_create, name="asset_compliance_audit_create"),
    path("compliance/audits/<int:pk>/", views.asset_compliance_audit_detail, name="asset_compliance_audit_detail"),
    path("compliance/audits/<int:pk>/edit/", views.asset_compliance_audit_edit, name="asset_compliance_audit_edit"),
    path("compliance/audits/<int:pk>/delete/", views.asset_compliance_audit_delete, name="asset_compliance_audit_delete"),
    path("compliance/audits/<int:pk>/start/", views.asset_compliance_audit_start, name="asset_compliance_audit_start"),
    path("compliance/audits/<int:pk>/complete/", views.asset_compliance_audit_complete, name="asset_compliance_audit_complete"),
]
