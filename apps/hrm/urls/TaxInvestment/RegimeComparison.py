"""HRM 3.16 Tax & Investment — RegimeComparison URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("tax-regime-comparison/", views.tax_regime_comparison, name="tax_regime_comparison"),
]
