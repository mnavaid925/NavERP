"""HRM 3.22 Training Management — Calendar URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Training calendar (upcoming sessions, date-grouped)
    path("training-calendar/", views.training_calendar, name="training_calendar"),
]
