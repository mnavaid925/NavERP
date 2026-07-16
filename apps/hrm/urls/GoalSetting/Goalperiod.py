"""HRM 3.18 Goal Setting — Goalperiod URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ===================== 3.18 Goal Setting (Performance Management) =====================
    # Goal periods (quarterly/annual cycle catalog) + activate/close workflow
    path("goal-periods/", views.goalperiod_list, name="goalperiod_list"),
    path("goal-periods/add/", views.goalperiod_create, name="goalperiod_create"),
    path("goal-periods/<int:pk>/", views.goalperiod_detail, name="goalperiod_detail"),
    path("goal-periods/<int:pk>/edit/", views.goalperiod_edit, name="goalperiod_edit"),
    path("goal-periods/<int:pk>/delete/", views.goalperiod_delete, name="goalperiod_delete"),
    path("goal-periods/<int:pk>/activate/", views.goalperiod_activate, name="goalperiod_activate"),
    path("goal-periods/<int:pk>/close/", views.goalperiod_close, name="goalperiod_close"),
]
