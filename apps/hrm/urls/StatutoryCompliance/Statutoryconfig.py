"""HRM 3.15 Statutory Compliance — Statutoryconfig URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ===================== 3.15 Statutory Compliance =====================
    # Config singleton (detail + edit only — one row per tenant)
    path("statutory-config/", views.statutoryconfig_detail, name="statutoryconfig_detail"),
    path("statutory-config/edit/", views.statutoryconfig_edit, name="statutoryconfig_edit"),
]
