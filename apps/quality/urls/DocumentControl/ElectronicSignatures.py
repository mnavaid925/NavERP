from django.urls import path

from apps.quality.views.DocumentControl.ElectronicSignatures import (
    controlled_document_sign,
    electronic_signature_detail,
    electronic_signature_export,
    electronic_signature_list,
    electronic_signature_verify,
)

urlpatterns = [
    path("signatures/", electronic_signature_list, name="electronic_signature_list"),
    path("signatures/export/", electronic_signature_export, name="electronic_signature_export"),
    path("signatures/<int:pk>/", electronic_signature_detail, name="electronic_signature_detail"),
    path("signatures/<int:pk>/verify/", electronic_signature_verify, name="electronic_signature_verify"),
    path("documents/<int:pk>/sign/", controlled_document_sign, name="controlled_document_sign"),
]
