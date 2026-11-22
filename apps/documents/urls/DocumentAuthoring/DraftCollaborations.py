from django.urls import path

from apps.documents.views.DocumentAuthoring import DraftCollaborations as views

urlpatterns = [
    path("collaborations/", views.collaboration_list, name="collaboration_list"),
    path("collaborations/create/<int:draft_pk>/", views.collaboration_create, name="collaboration_create"),
    path("collaborations/<int:pk>/", views.collaboration_detail, name="collaboration_detail"),
    path("collaborations/<int:pk>/edit/", views.collaboration_edit, name="collaboration_edit"),
    path("collaborations/<int:pk>/delete/", views.collaboration_delete, name="collaboration_delete"),
    path("collaborations/<int:pk>/resolve/", views.collaboration_resolve, name="collaboration_resolve"),
]
