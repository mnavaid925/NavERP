from django.urls import path

from apps.assets.views.AssetInventoryTracking.AssetAudits import (
    asset_audit_cancel,
    asset_audit_complete,
    asset_audit_create,
    asset_audit_delete,
    asset_audit_detail,
    asset_audit_edit,
    asset_audit_list,
    asset_audit_reconcile,
    asset_audit_start,
)

urlpatterns = [
    path("inventory-tracking/audits/", asset_audit_list, name="asset_audit_list"),
    path("inventory-tracking/audits/create/", asset_audit_create, name="asset_audit_create"),
    path("inventory-tracking/audits/<int:pk>/", asset_audit_detail, name="asset_audit_detail"),
    path("inventory-tracking/audits/<int:pk>/edit/", asset_audit_edit, name="asset_audit_edit"),
    path("inventory-tracking/audits/<int:pk>/delete/", asset_audit_delete, name="asset_audit_delete"),
    path("inventory-tracking/audits/<int:pk>/start/", asset_audit_start, name="asset_audit_start"),
    path("inventory-tracking/audits/<int:pk>/complete/", asset_audit_complete, name="asset_audit_complete"),
    path("inventory-tracking/audits/<int:pk>/reconcile/", asset_audit_reconcile, name="asset_audit_reconcile"),
    path("inventory-tracking/audits/<int:pk>/cancel/", asset_audit_cancel, name="asset_audit_cancel"),
]
