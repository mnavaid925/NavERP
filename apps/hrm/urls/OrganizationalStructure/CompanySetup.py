"""HRM 3.2 Organizational Structure — CompanySetup URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("company-setup/", views.company_setup, name="company_setup"),
]
