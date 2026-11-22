from django.urls import path

from apps.documents.views.VersionControl import DocumentBranches as views

urlpatterns = [
    path("branches/", views.document_branch_list, name="document_branch_list"),
    path("branches/create/", views.document_branch_create, name="document_branch_create"),
    path("branches/<int:pk>/", views.document_branch_detail, name="document_branch_detail"),
    path("branches/<int:pk>/edit/", views.document_branch_edit, name="document_branch_edit"),
    path("branches/<int:pk>/delete/", views.document_branch_delete, name="document_branch_delete"),
    path("branches/<int:pk>/merge/", views.document_branch_merge, name="document_branch_merge"),
    path("branches/<int:pk>/abandon/", views.document_branch_abandon, name="document_branch_abandon"),
]
