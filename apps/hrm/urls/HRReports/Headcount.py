"""HRM 3.28 HR Reports — Headcount URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/hr/headcount/", views.headcount_report, name="headcount_report"),
]
