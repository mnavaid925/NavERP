"""HRM 3.20 Continuous Feedback — FeedbackDashboard URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("feedback/dashboard/", views.feedback_dashboard, name="feedback_dashboard"),
    path("feedback/<int:pk>/delete/", views.feedback_delete, name="feedback_delete"),
    path("feedback/<int:pk>/acknowledge/", views.feedback_acknowledge, name="feedback_acknowledge"),
    path("feedback/<int:pk>/respond/", views.feedback_respond, name="feedback_respond"),
]
