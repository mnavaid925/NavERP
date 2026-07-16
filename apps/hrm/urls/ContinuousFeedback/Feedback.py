"""HRM 3.20 Continuous Feedback — Feedback URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Feedback (real-time kudos/appreciation/constructive + request-pull workflow)
    path("feedback/", views.feedback_list, name="feedback_list"),
    path("feedback/add/", views.feedback_create, name="feedback_create"),
    path("feedback/<int:pk>/", views.feedback_detail, name="feedback_detail"),
    path("feedback/<int:pk>/edit/", views.feedback_edit, name="feedback_edit"),
]
