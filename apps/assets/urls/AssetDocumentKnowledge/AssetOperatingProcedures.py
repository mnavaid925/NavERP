"""URL patterns for Asset Operating Procedures & LOTO Protocols (11.16)."""

from django.urls import path

from apps.assets.views.AssetDocumentKnowledge import AssetOperatingProcedures as views

urlpatterns = [
    path(
        "procedures/",
        views.asset_operating_procedure_list,
        name="asset_operating_procedure_list",
    ),
    path(
        "procedures/create/",
        views.asset_operating_procedure_create,
        name="asset_operating_procedure_create",
    ),
    path(
        "procedures/export-csv/",
        views.asset_operating_procedure_export_csv,
        name="asset_operating_procedure_export_csv",
    ),
    path(
        "procedures/<int:pk>/",
        views.asset_operating_procedure_detail,
        name="asset_operating_procedure_detail",
    ),
    path(
        "procedures/<int:pk>/print/",
        views.asset_operating_procedure_print,
        name="asset_operating_procedure_print",
    ),
    path(
        "procedures/<int:pk>/edit/",
        views.asset_operating_procedure_edit,
        name="asset_operating_procedure_edit",
    ),
    path(
        "procedures/<int:pk>/delete/",
        views.asset_operating_procedure_delete,
        name="asset_operating_procedure_delete",
    ),
    path(
        "procedures/<int:pk>/download/",
        views.asset_operating_procedure_download,
        name="asset_operating_procedure_download",
    ),
    path(
        "procedures/<int:pk>/submit-review/",
        views.asset_operating_procedure_submit_review,
        name="asset_operating_procedure_submit_review",
    ),
    path(
        "procedures/<int:pk>/activate/",
        views.asset_operating_procedure_activate,
        name="asset_operating_procedure_activate",
    ),
    path(
        "procedures/<int:pk>/clone-revision/",
        views.asset_operating_procedure_clone_revision,
        name="asset_operating_procedure_clone_revision",
    ),
    path(
        "procedures/<int:pk>/retire/",
        views.asset_operating_procedure_retire,
        name="asset_operating_procedure_retire",
    ),
]
