from django.urls import path

from apps.bi.views.CollaborationStorytelling import BiSharedWorkspaces as views

urlpatterns = [
    path("workspaces/", views.bi_shared_workspace_list, name="bi_shared_workspace_list"),
    path("workspaces/create/", views.bi_shared_workspace_create, name="bi_shared_workspace_create"),
    path("workspaces/<int:pk>/", views.bi_shared_workspace_detail, name="bi_shared_workspace_detail"),
    path("workspaces/<int:pk>/edit/", views.bi_shared_workspace_edit, name="bi_shared_workspace_edit"),
    path("workspaces/<int:pk>/delete/", views.bi_shared_workspace_delete, name="bi_shared_workspace_delete"),
]
