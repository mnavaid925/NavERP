"""HRM 3.32 Analytics Dashboard — Predictive URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("analytics/predictive/", views.predictive_analytics, name="predictive_analytics"),
]
