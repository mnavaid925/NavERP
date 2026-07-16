"""HRM 3.28 HR Reports — Hiring URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/hr/hiring/", views.hiring_report, name="hiring_report"),
]
