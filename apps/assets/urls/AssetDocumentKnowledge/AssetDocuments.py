"""URL patterns for Controlled Asset Documents & Version Control (11.16)."""

from django.urls import path

from apps.assets.views.AssetDocumentKnowledge import AssetDocuments as views

urlpatterns = [
    path("documents/", views.asset_document_list, name="asset_document_list"),
    path(
        "documents/changes/",
        views.asset_document_change_list,
        name="asset_document_change_list",
    ),
    path(
        "documents/create/",
        views.asset_document_create,
        name="asset_document_create",
    ),
    path(
        "documents/export-csv/",
        views.asset_document_export_csv,
        name="asset_document_export_csv",
    ),
    path(
        "documents/<int:pk>/",
        views.asset_document_detail,
        name="asset_document_detail",
    ),
    path(
        "documents/<int:pk>/edit/",
        views.asset_document_edit,
        name="asset_document_edit",
    ),
    path(
        "documents/<int:pk>/delete/",
        views.asset_document_delete,
        name="asset_document_delete",
    ),
    path(
        "documents/<int:pk>/download/",
        views.asset_document_download,
        name="asset_document_download",
    ),
    path(
        "documents/<int:pk>/submit-review/",
        views.asset_document_submit_review,
        name="asset_document_submit_review",
    ),
    path(
        "documents/<int:pk>/approve-release/",
        views.asset_document_approve_release,
        name="asset_document_approve_release",
    ),
    path(
        "documents/<int:pk>/return-draft/",
        views.asset_document_return_to_draft,
        name="asset_document_return_to_draft",
    ),
    path(
        "documents/<int:pk>/checkout/",
        views.asset_document_checkout,
        name="asset_document_checkout",
    ),
    path(
        "documents/<int:pk>/checkin/",
        views.asset_document_checkin,
        name="asset_document_checkin",
    ),
    path(
        "documents/<int:pk>/create-revision/",
        views.asset_document_create_revision,
        name="asset_document_create_revision",
    ),
    path(
        "documents/<int:pk>/archive/",
        views.asset_document_archive,
        name="asset_document_archive",
    ),
]
