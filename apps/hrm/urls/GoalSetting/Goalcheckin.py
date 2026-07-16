"""HRM 3.18 Goal Setting — Goalcheckin URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Goal check-ins (append-only progress log) — created nested under a key result
    path("key-results/<int:keyresult_pk>/check-ins/add/", views.goalcheckin_create, name="goalcheckin_create"),
    path("check-ins/", views.goalcheckin_list, name="goalcheckin_list"),
    path("check-ins/<int:pk>/", views.goalcheckin_detail, name="goalcheckin_detail"),
    path("check-ins/<int:pk>/delete/", views.goalcheckin_delete, name="goalcheckin_delete"),
]
