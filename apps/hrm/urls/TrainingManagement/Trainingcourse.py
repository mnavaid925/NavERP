"""HRM 3.22 Training Management — Trainingcourse URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ---- 3.22 Training Management ----
    # Training courses (catalog)
    path("training-courses/", views.trainingcourse_list, name="trainingcourse_list"),
    path("training-courses/add/", views.trainingcourse_create, name="trainingcourse_create"),
    path("training-courses/<int:pk>/", views.trainingcourse_detail, name="trainingcourse_detail"),
    path("training-courses/<int:pk>/edit/", views.trainingcourse_edit, name="trainingcourse_edit"),
    path("training-courses/<int:pk>/delete/", views.trainingcourse_delete, name="trainingcourse_delete"),
]
