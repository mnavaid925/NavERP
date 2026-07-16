"""HRM 3.4 Employee Offboarding — Letters URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("letters/", views.offboarding_letters, name="offboarding_letters"),
]
