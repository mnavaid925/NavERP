"""HRM 3.30 Leave Reports — LeaveRegister URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/leave/register/", views.leave_register_report, name="leave_register_report"),
]
