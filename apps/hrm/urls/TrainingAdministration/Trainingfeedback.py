"""HRM 3.24 Training Administration — Trainingfeedback URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Feedback (nested-create under an attendance record)
    path("training-attendance/<int:attendance_pk>/feedback/add/", views.trainingfeedback_create, name="trainingfeedback_create"),
    path("training-feedback/", views.trainingfeedback_list, name="trainingfeedback_list"),
    path("training-feedback/<int:pk>/", views.trainingfeedback_detail, name="trainingfeedback_detail"),
    path("training-feedback/<int:pk>/edit/", views.trainingfeedback_edit, name="trainingfeedback_edit"),
    path("training-feedback/<int:pk>/delete/", views.trainingfeedback_delete, name="trainingfeedback_delete"),
]
