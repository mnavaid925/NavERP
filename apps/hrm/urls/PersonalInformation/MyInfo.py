"""HRM 3.25 Personal Information — MyInfo URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.25 Personal Information (Self-Service)
    path("my-info/", views.my_info, name="my_info"),
]
