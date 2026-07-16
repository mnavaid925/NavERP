"""HRM 3.28 HR Reports — HrIndex URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.28 HR Reports (derived, read-only, admin-only)
    path("reports/hr/", views.hr_reports_index, name="hr_reports_index"),
]
