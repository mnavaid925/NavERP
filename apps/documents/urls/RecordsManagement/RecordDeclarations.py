from django.urls import path

from apps.documents.views.RecordsManagement import RecordDeclarations as views

urlpatterns = [
    path("records/declarations/", views.record_declaration_list, name="record_declaration_list"),
    path("records/declarations/create/", views.record_declaration_create, name="record_declaration_create"),
    path("records/declarations/<int:pk>/", views.record_declaration_detail, name="record_declaration_detail"),
    path("records/declarations/<int:pk>/edit/", views.record_declaration_edit, name="record_declaration_edit"),
    path("records/declarations/<int:pk>/delete/", views.record_declaration_delete, name="record_declaration_delete"),
    path("records/declarations/<int:pk>/trigger-cutoff/", views.record_declaration_trigger_cutoff, name="record_declaration_trigger_cutoff"),
]
