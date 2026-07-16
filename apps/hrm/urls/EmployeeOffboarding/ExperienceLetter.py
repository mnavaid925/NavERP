"""HRM 3.4 Employee Offboarding — ExperienceLetter URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("separations/<int:pk>/experience-letter/", views.separationcase_generate_experience_letter, name="separationcase_experience_letter"),
]
