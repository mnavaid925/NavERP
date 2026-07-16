"""HRM 3.28 HR Reports — Diversity URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/hr/diversity/", views.diversity_report, name="diversity_report"),
]
