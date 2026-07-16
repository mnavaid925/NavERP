"""HRM 3.2 Organizational Structure — OrgChart URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Org Chart & Company Setup (3.2 — derived, no model)
    path("org-chart/", views.org_chart, name="org_chart"),
]
