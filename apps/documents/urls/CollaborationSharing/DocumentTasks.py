from django.urls import path

from apps.documents.views.CollaborationSharing import DocumentTasks as views

urlpatterns = [
    path("tasks/", views.document_task_list, name="document_task_list"),
    path("tasks/create/", views.document_task_create, name="document_task_create"),
    path("tasks/<int:pk>/", views.document_task_detail, name="document_task_detail"),
    path("tasks/<int:pk>/edit/", views.document_task_edit, name="document_task_edit"),
    path("tasks/<int:pk>/delete/", views.document_task_delete, name="document_task_delete"),
    path("tasks/<int:pk>/toggle-complete/", views.document_task_toggle_complete, name="document_task_toggle_complete"),
]
