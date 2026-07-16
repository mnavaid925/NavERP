"""HRM 3.38 Talent Management & Succession — Successioncandidate URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("talent/succession-plans/<int:plan_pk>/candidates/add/", views.successioncandidate_add, name="successioncandidate_add"),
    path("talent/candidates/<int:pk>/edit/", views.successioncandidate_edit, name="successioncandidate_edit"),
    path("talent/candidates/<int:pk>/delete/", views.successioncandidate_delete, name="successioncandidate_delete"),
]
