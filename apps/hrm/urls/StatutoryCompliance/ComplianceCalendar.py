"""HRM 3.15 Statutory Compliance — ComplianceCalendar URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Compliance calendar (cross-scheme due-date overview)
    path("statutory-compliance-calendar/", views.statutory_compliance_calendar, name="statutory_compliance_calendar"),
]
