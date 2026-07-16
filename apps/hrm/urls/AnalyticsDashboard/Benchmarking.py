"""HRM 3.32 Analytics Dashboard — Benchmarking URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("analytics/benchmarking/", views.benchmarking, name="benchmarking"),
]
