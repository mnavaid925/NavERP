"""HRM 3.32 Analytics Dashboard — Executive URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.32 Analytics Dashboard
    path("analytics/executive/", views.executive_dashboard, name="executive_dashboard"),
]
