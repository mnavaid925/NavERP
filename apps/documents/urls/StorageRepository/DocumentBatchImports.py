from django.urls import path

from apps.documents.views.StorageRepository import DocumentBatchImports as views

urlpatterns = [
    path("storage/batch-imports/", views.batch_import_list, name="batch_import_list"),
    path("storage/batch-imports/create/", views.batch_import_create, name="batch_import_create"),
    path("storage/batch-imports/<int:pk>/", views.batch_import_detail, name="batch_import_detail"),
    path("storage/batch-imports/<int:pk>/edit/", views.batch_import_edit, name="batch_import_edit"),
    path("storage/batch-imports/<int:pk>/delete/", views.batch_import_delete, name="batch_import_delete"),
    path("storage/batch-imports/<int:pk>/process/", views.batch_import_process, name="batch_import_process"),
]
