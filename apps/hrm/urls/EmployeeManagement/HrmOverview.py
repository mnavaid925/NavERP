"""HRM 3.1 Employee Management — HrmOverview URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Overview / landing (3.1)
    path("", views.hrm_overview, name="hrm_overview"),
]
