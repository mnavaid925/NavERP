from django.urls import path

from apps.documents.views.CollaborationSharing import CollaborationHub as views

urlpatterns = [
    path("collaboration/", views.collaboration_hub, name="collaboration_hub"),
]
