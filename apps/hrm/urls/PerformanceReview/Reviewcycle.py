"""HRM 3.19 Performance Review — Reviewcycle URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ===================== 3.19 Performance Review (Performance Management) =====================
    # Review cycles (catalog + phase machine) + advance-phase workflow
    path("review-cycles/", views.reviewcycle_list, name="reviewcycle_list"),
    path("review-cycles/add/", views.reviewcycle_create, name="reviewcycle_create"),
    path("review-cycles/<int:pk>/", views.reviewcycle_detail, name="reviewcycle_detail"),
    path("review-cycles/<int:pk>/edit/", views.reviewcycle_edit, name="reviewcycle_edit"),
    path("review-cycles/<int:pk>/delete/", views.reviewcycle_delete, name="reviewcycle_delete"),
    path("review-cycles/<int:pk>/advance/", views.reviewcycle_advance_phase, name="reviewcycle_advance_phase"),
]
