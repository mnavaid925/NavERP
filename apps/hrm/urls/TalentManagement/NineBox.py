"""HRM 3.38 Talent Management & Succession — NineBox URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("talent/nine-box/", views.talent_nine_box, name="talent_nine_box"),
]
