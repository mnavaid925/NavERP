from django.urls import path

from apps.quality.views.DocumentControl.DocumentAcknowledgments import (
    document_acknowledgment_create,
    document_acknowledgment_delete,
    document_acknowledgment_detail,
    document_acknowledgment_edit,
    document_acknowledgment_export,
    document_acknowledgment_list,
    document_acknowledgment_sign,
)

urlpatterns = [
    path("acknowledgments/", document_acknowledgment_list, name="document_acknowledgment_list"),
    path("acknowledgments/create/", document_acknowledgment_create, name="document_acknowledgment_create"),
    path("acknowledgments/export/", document_acknowledgment_export, name="document_acknowledgment_export"),
    path("acknowledgments/<int:pk>/", document_acknowledgment_detail, name="document_acknowledgment_detail"),
    path("acknowledgments/<int:pk>/edit/", document_acknowledgment_edit, name="document_acknowledgment_edit"),
    path("acknowledgments/<int:pk>/delete/", document_acknowledgment_delete, name="document_acknowledgment_delete"),
    path("acknowledgments/<int:pk>/sign/", document_acknowledgment_sign, name="document_acknowledgment_sign"),
]
