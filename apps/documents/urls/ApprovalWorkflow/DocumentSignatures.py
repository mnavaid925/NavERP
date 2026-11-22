from django.urls import path

from apps.documents.views.ApprovalWorkflow import DocumentSignatures as views

urlpatterns = [
    path("signatures/", views.signature_list, name="signature_list"),
    path("signatures/create/", views.signature_create, name="signature_create"),
    path("signatures/verify/", views.signature_verify, name="signature_verify"),
    path("signatures/verify/<str:token>/", views.signature_verify, name="signature_verify"),
    path("signatures/token/<str:token>/", views.signature_verify, name="signature_verify_token"),
    path("signatures/<int:pk>/", views.signature_detail, name="signature_detail"),
    path("signatures/<int:pk>/edit/", views.signature_edit, name="signature_edit"),
    path("signatures/<int:pk>/delete/", views.signature_delete, name="signature_delete"),
    path("signatures/<int:pk>/manifest/", views.signature_manifest, name="signature_manifest"),
]
