"""HRM 3.18 Goal Setting — Keyresult URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Key results (the "KR") — created nested under an objective; viewed in its context
    path("objectives/<int:objective_pk>/key-results/add/", views.keyresult_create, name="keyresult_create"),
    path("key-results/<int:pk>/", views.keyresult_detail, name="keyresult_detail"),
    path("key-results/<int:pk>/edit/", views.keyresult_edit, name="keyresult_edit"),
    path("key-results/<int:pk>/delete/", views.keyresult_delete, name="keyresult_delete"),
]
