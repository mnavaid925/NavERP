"""HRM 3.30 Leave Reports — LeaveIndex URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.30 Leave Reports (derived, read-only, admin-only)
    path("reports/leave/", views.leave_reports_index, name="leave_reports_index"),
]
