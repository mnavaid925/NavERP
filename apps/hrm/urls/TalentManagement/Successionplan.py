"""HRM 3.38 Talent Management & Succession — Successionplan URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("talent/succession-plans/", views.successionplan_list, name="successionplan_list"),
    path("talent/succession-plans/add/", views.successionplan_create, name="successionplan_create"),
    path("talent/succession-plans/<int:pk>/", views.successionplan_detail, name="successionplan_detail"),
    path("talent/succession-plans/<int:pk>/edit/", views.successionplan_edit, name="successionplan_edit"),
    path("talent/succession-plans/<int:pk>/delete/", views.successionplan_delete, name="successionplan_delete"),
]
