"""HRM 3.24 Training Administration — Trainingcertificate URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Certificates (+ issue-from-attendance/progress, revoke, print)
    path("training-certificates/", views.trainingcertificate_list, name="trainingcertificate_list"),
    path("training-certificates/add/", views.trainingcertificate_create, name="trainingcertificate_create"),
    path("training-attendance/<int:attendance_pk>/issue-certificate/", views.trainingcertificate_issue_from_attendance, name="trainingcertificate_issue_from_attendance"),
    path("learning-progress/<int:progress_pk>/issue-certificate/", views.trainingcertificate_issue_from_progress, name="trainingcertificate_issue_from_progress"),
    path("training-certificates/<int:pk>/", views.trainingcertificate_detail, name="trainingcertificate_detail"),
    path("training-certificates/<int:pk>/edit/", views.trainingcertificate_edit, name="trainingcertificate_edit"),
    path("training-certificates/<int:pk>/delete/", views.trainingcertificate_delete, name="trainingcertificate_delete"),
    path("training-certificates/<int:pk>/revoke/", views.trainingcertificate_revoke, name="trainingcertificate_revoke"),
    path("training-certificates/<int:pk>/print/", views.trainingcertificate_print, name="trainingcertificate_print"),
]
