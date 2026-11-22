from django.urls import path

from apps.documents.views.StorageRepository import DocumentFolders as views

urlpatterns = [
    path("storage/folders/", views.folder_list, name="folder_list"),
    path("storage/folders/tree/", views.folder_tree, name="folder_tree"),
    path("storage/folders/create/", views.folder_create, name="folder_create"),
    path("storage/folders/<int:pk>/", views.folder_detail, name="folder_detail"),
    path("storage/folders/<int:pk>/edit/", views.folder_edit, name="folder_edit"),
    path("storage/folders/<int:pk>/delete/", views.folder_delete, name="folder_delete"),
]
