"""HRM 3.22 Training Management — Trainingsession URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Training sessions (classroom / virtual / external occurrences)
    path("training-sessions/", views.trainingsession_list, name="trainingsession_list"),
    path("training-sessions/add/", views.trainingsession_create, name="trainingsession_create"),
    path("training-sessions/<int:pk>/", views.trainingsession_detail, name="trainingsession_detail"),
    path("training-sessions/<int:pk>/edit/", views.trainingsession_edit, name="trainingsession_edit"),
    path("training-sessions/<int:pk>/delete/", views.trainingsession_delete, name="trainingsession_delete"),
]
