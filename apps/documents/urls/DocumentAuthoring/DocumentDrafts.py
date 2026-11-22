from django.urls import path

from apps.documents.views.DocumentAuthoring import DocumentDrafts as views

urlpatterns = [
    path("drafts/", views.draft_list, name="draft_list"),
    path("drafts/create/", views.draft_create, name="draft_create"),
    path("drafts/<int:pk>/", views.draft_detail, name="draft_detail"),
    path("drafts/<int:pk>/edit/", views.draft_edit, name="draft_edit"),
    path("drafts/<int:pk>/delete/", views.draft_delete, name="draft_delete"),
    path("drafts/<int:pk>/canvas/", views.draft_canvas, name="draft_canvas"),
    path("drafts/<int:pk>/autosave/", views.draft_autosave, name="draft_autosave"),
    path("drafts/<int:pk>/compare/", views.draft_compare, name="draft_compare"),
    path("drafts/<int:pk>/conflict/", views.draft_resolve_conflict, name="draft_resolve_conflict"),
    path("drafts/<int:pk>/promote/", views.draft_promote, name="draft_promote"),
]
