from django.urls import path

from apps.assets.views.AssetCompliance import AssetComplianceIncidents as views

urlpatterns = [
    path("compliance/incidents/", views.asset_compliance_incident_list, name="asset_compliance_incident_list"),
    path("compliance/incidents/create/", views.asset_compliance_incident_create, name="asset_compliance_incident_create"),
    path("compliance/incidents/<int:pk>/", views.asset_compliance_incident_detail, name="asset_compliance_incident_detail"),
    path("compliance/incidents/<int:pk>/edit/", views.asset_compliance_incident_edit, name="asset_compliance_incident_edit"),
    path("compliance/incidents/<int:pk>/delete/", views.asset_compliance_incident_delete, name="asset_compliance_incident_delete"),
    path("compliance/incidents/<int:pk>/resolve/", views.asset_compliance_incident_resolve, name="asset_compliance_incident_resolve"),
    path("compliance/incidents/<int:pk>/close/", views.asset_compliance_incident_close, name="asset_compliance_incident_close"),
]
