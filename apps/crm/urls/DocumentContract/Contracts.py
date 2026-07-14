"""CRM 1.9 Document & Contract Management — Contracts URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Contract documents + e-signature (1.9)
    path("contracts/", views.contractdocument_list, name="contractdocument_list"),
    path("contracts/add/", views.contractdocument_create, name="contractdocument_create"),
    path("contracts/<int:pk>/", views.contractdocument_detail, name="contractdocument_detail"),
    path("contracts/<int:pk>/edit/", views.contractdocument_edit, name="contractdocument_edit"),
    path("contracts/<int:pk>/delete/", views.contractdocument_delete, name="contractdocument_delete"),
    path("contracts/<int:pk>/add-signer/", views.contractdocument_add_signer, name="contractdocument_add_signer"),
    path("contracts/<int:pk>/remove-signer/<int:signer_pk>/", views.contractdocument_remove_signer, name="contractdocument_remove_signer"),
    path("contracts/<int:pk>/generate/", views.contractdocument_generate, name="contractdocument_generate"),
    path("contracts/<int:pk>/send/", views.contractdocument_send, name="contractdocument_send"),
    path("contracts/<int:pk>/versions/add/", views.contractdocument_version_add, name="contractdocument_version_add"),
    path("sign/<str:token>/", views.sign_document, name="sign_document"),  # public
]
