from django.urls import path

from apps.assets.views.AssetInventoryTracking.AssetIncidentReports import (
    asset_incident_report_authorize_write_off,
    asset_incident_report_close,
    asset_incident_report_create,
    asset_incident_report_delete,
    asset_incident_report_detail,
    asset_incident_report_edit,
    asset_incident_report_investigate,
    asset_incident_report_list,
    asset_incident_report_resolve_recovered,
)

urlpatterns = [
    path("inventory-tracking/incidents/", asset_incident_report_list, name="asset_incident_report_list"),
    path("inventory-tracking/incidents/create/", asset_incident_report_create, name="asset_incident_report_create"),
    path("inventory-tracking/incidents/<int:pk>/", asset_incident_report_detail, name="asset_incident_report_detail"),
    path("inventory-tracking/incidents/<int:pk>/edit/", asset_incident_report_edit, name="asset_incident_report_edit"),
    path("inventory-tracking/incidents/<int:pk>/delete/", asset_incident_report_delete, name="asset_incident_report_delete"),
    path(
        "inventory-tracking/incidents/<int:pk>/investigate/",
        asset_incident_report_investigate,
        name="asset_incident_report_investigate",
    ),
    path(
        "inventory-tracking/incidents/<int:pk>/resolve-recovered/",
        asset_incident_report_resolve_recovered,
        name="asset_incident_report_resolve_recovered",
    ),
    path(
        "inventory-tracking/incidents/<int:pk>/authorize-write-off/",
        asset_incident_report_authorize_write_off,
        name="asset_incident_report_authorize_write_off",
    ),
    path("inventory-tracking/incidents/<int:pk>/close/", asset_incident_report_close, name="asset_incident_report_close"),
]
