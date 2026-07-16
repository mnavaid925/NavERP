"""HRM 3.17 Payout & Reports — Exceptions URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("payout-exceptions/", views.payout_exceptions, name="payout_exceptions"),
]
