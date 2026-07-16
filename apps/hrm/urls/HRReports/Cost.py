"""HRM 3.28 HR Reports — Cost URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/hr/cost/", views.cost_report, name="cost_report"),
]
