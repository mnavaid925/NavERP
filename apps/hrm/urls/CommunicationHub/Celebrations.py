"""HRM 3.27 Communication Hub — Celebrations URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.27 Communication Hub
    path("celebrations/", views.celebrations, name="celebrations"),
]
