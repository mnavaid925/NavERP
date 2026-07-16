"""HRM 3.30 Leave Reports — CompOff URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/leave/comp-off/", views.comp_off_report, name="comp_off_report"),
]
