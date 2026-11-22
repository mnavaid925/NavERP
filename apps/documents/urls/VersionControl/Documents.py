from django.urls import path

from apps.documents.views.VersionControl import Documents as views

urlpatterns = [
    path("", views.document_list, name="document_list"),
    path("create/", views.document_create, name="document_create"),
    path("<int:pk>/", views.document_detail, name="document_detail"),
    path("<int:pk>/edit/", views.document_edit, name="document_edit"),
    path("<int:pk>/delete/", views.document_delete, name="document_delete"),
]
