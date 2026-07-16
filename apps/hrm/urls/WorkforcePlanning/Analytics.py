"""HRM 3.40 Workforce Planning — Analytics URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("workforce/analytics/", views.workforce_analytics, name="workforce_analytics"),
]
