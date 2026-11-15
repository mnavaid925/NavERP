from django.urls import path

from apps.quality.views.DocumentControl.ControlledDocuments import (
    controlled_document_approve,
    controlled_document_create,
    controlled_document_delete,
    controlled_document_detail,
    controlled_document_edit,
    controlled_document_export,
    controlled_document_list,
    controlled_document_make_effective,
    controlled_document_new_revision,
    controlled_document_obsolete,
    controlled_document_submit,
    document_archive_vault,
)

urlpatterns = [
    path("documents/", controlled_document_list, name="controlled_document_list"),
    path("documents/create/", controlled_document_create, name="controlled_document_create"),
    path("documents/export/", controlled_document_export, name="controlled_document_export"),
    path("documents/vault/", document_archive_vault, name="document_archive_vault"),
    path("documents/<int:pk>/", controlled_document_detail, name="controlled_document_detail"),
    path("documents/<int:pk>/edit/", controlled_document_edit, name="controlled_document_edit"),
    path("documents/<int:pk>/delete/", controlled_document_delete, name="controlled_document_delete"),
    path("documents/<int:pk>/submit/", controlled_document_submit, name="controlled_document_submit"),
    path("documents/<int:pk>/approve/", controlled_document_approve, name="controlled_document_approve"),
    path("documents/<int:pk>/make-effective/", controlled_document_make_effective, name="controlled_document_make_effective"),
    path("documents/<int:pk>/obsolete/", controlled_document_obsolete, name="controlled_document_obsolete"),
    path("documents/<int:pk>/revise/", controlled_document_new_revision, name="controlled_document_new_revision"),
]
