from django.urls import path

from apps.documents.views.StorageRepository import StorageVolumes as views

urlpatterns = [
    path("storage/volumes/", views.storage_volume_list, name="storage_volume_list"),
    path("storage/volumes/create/", views.storage_volume_create, name="storage_volume_create"),
    path("storage/volumes/<int:pk>/", views.storage_volume_detail, name="storage_volume_detail"),
    path("storage/volumes/<int:pk>/edit/", views.storage_volume_edit, name="storage_volume_edit"),
    path("storage/volumes/<int:pk>/delete/", views.storage_volume_delete, name="storage_volume_delete"),
]
