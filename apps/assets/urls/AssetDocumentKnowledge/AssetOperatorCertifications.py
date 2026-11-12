"""URL patterns for Asset Operator Training & Certification Records (11.16)."""

from django.urls import path

from apps.assets.views.AssetDocumentKnowledge import AssetOperatorCertifications as views

urlpatterns = [
    path(
        "certifications/",
        views.asset_operator_certification_list,
        name="asset_operator_certification_list",
    ),
    path(
        "certifications/create/",
        views.asset_operator_certification_create,
        name="asset_operator_certification_create",
    ),
    path(
        "certifications/refresh-alerts/",
        views.asset_operator_certification_refresh_alerts,
        name="asset_operator_certification_refresh_alerts",
    ),
    path(
        "certifications/export-csv/",
        views.asset_operator_certification_export_csv,
        name="asset_operator_certification_export_csv",
    ),
    path(
        "certifications/<int:pk>/",
        views.asset_operator_certification_detail,
        name="asset_operator_certification_detail",
    ),
    path(
        "certifications/<int:pk>/edit/",
        views.asset_operator_certification_edit,
        name="asset_operator_certification_edit",
    ),
    path(
        "certifications/<int:pk>/delete/",
        views.asset_operator_certification_delete,
        name="asset_operator_certification_delete",
    ),
    path(
        "certifications/<int:pk>/download/",
        views.asset_operator_certification_download,
        name="asset_operator_certification_download",
    ),
    path(
        "certifications/<int:pk>/verify-activate/",
        views.asset_operator_certification_verify_activate,
        name="asset_operator_certification_verify_activate",
    ),
    path(
        "certifications/<int:pk>/acknowledge-sop/",
        views.asset_operator_certification_acknowledge_sop,
        name="asset_operator_certification_acknowledge_sop",
    ),
    path(
        "certifications/<int:pk>/renew/",
        views.asset_operator_certification_renew,
        name="asset_operator_certification_renew",
    ),
    path(
        "certifications/<int:pk>/revoke/",
        views.asset_operator_certification_revoke,
        name="asset_operator_certification_revoke",
    ),
]
