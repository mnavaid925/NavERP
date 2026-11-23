from django.urls import path

from apps.documents.views.CollaborationSharing import CoauthorSessions as views

urlpatterns = [
    path("sessions/", views.coauthor_session_list, name="coauthor_session_list"),
    path("sessions/create/", views.coauthor_session_create, name="coauthor_session_create"),
    path("sessions/<int:pk>/", views.coauthor_session_detail, name="coauthor_session_detail"),
    path("sessions/<int:pk>/edit/", views.coauthor_session_edit, name="coauthor_session_edit"),
    path("sessions/<int:pk>/delete/", views.coauthor_session_delete, name="coauthor_session_delete"),
    path("sessions/<str:session_token>/heartbeat/", views.coauthor_session_heartbeat, name="coauthor_session_heartbeat"),
]
