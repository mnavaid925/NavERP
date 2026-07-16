"""HRM 3.38 Talent Management & Succession — Talentpoolmembership URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("talent/memberships/", views.talentpoolmembership_list, name="talentpoolmembership_list"),
    path("talent/memberships/add/", views.talentpoolmembership_create, name="talentpoolmembership_create"),
    path("talent/memberships/<int:pk>/", views.talentpoolmembership_detail, name="talentpoolmembership_detail"),
    path("talent/memberships/<int:pk>/edit/", views.talentpoolmembership_edit, name="talentpoolmembership_edit"),
    path("talent/memberships/<int:pk>/delete/", views.talentpoolmembership_delete, name="talentpoolmembership_delete"),
]
