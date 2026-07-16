"""HRM 3.28 HR Reports — Attrition URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/hr/attrition/", views.attrition_report, name="attrition_report"),
]
