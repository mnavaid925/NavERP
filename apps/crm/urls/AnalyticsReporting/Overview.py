"""CRM 1.6 Analytics & Reporting — Overview URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Analytics & Reporting overview (1.6) — module landing page
    path("", views.overview, name="overview"),
]
