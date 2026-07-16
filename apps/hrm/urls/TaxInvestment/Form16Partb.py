"""HRM 3.16 Tax & Investment — Form16Partb URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("tax-computations/<int:pk>/form16-partb/", views.form16_partb, name="form16_partb"),
]
