"""CRM 1.2 Sales Force Automation — Forecast URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Forecast dashboard (1.2 Forecasting)
    path("forecast/", views.forecast, name="forecast"),
]
