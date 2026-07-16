"""HRM 3.4 Employee Offboarding — RelievingLetter URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("separations/<int:pk>/relieving-letter/", views.separationcase_generate_relieving_letter, name="separationcase_relieving_letter"),
]
