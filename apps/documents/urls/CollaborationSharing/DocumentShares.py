from django.urls import path

from apps.documents.views.CollaborationSharing import DocumentShares as views

urlpatterns = [
    path("shares/", views.document_share_list, name="document_share_list"),
    path("shares/create/", views.document_share_create, name="document_share_create"),
    path("shares/<int:pk>/", views.document_share_detail, name="document_share_detail"),
    path("shares/<int:pk>/edit/", views.document_share_edit, name="document_share_edit"),
    path("shares/<int:pk>/delete/", views.document_share_delete, name="document_share_delete"),
    path("shares/<int:pk>/revoke/", views.document_share_revoke, name="document_share_revoke"),
]
