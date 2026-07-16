"""HRM 3.6 Candidate Management — CareersList URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Public career portal (3.6) — UNAUTHENTICATED. WARNING: add rate-limiting in production.
    path("careers/", views.careers_list, name="careers_list"),
]
