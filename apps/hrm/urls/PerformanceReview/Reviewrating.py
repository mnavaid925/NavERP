"""HRM 3.19 Performance Review — Reviewrating URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Review ratings (per-competency lines) — created nested under a review
    path("reviews/<int:review_pk>/ratings/add/", views.reviewrating_create, name="reviewrating_create"),
    path("ratings/<int:pk>/", views.reviewrating_detail, name="reviewrating_detail"),
    path("ratings/<int:pk>/edit/", views.reviewrating_edit, name="reviewrating_edit"),
    path("ratings/<int:pk>/delete/", views.reviewrating_delete, name="reviewrating_delete"),
]
