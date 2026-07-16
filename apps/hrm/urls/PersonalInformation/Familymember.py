"""HRM 3.25 Personal Information — Familymember URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Family Members (admin-gated writes)
    path("family-members/", views.familymember_list, name="familymember_list"),
    path("family-members/add/", views.familymember_create, name="familymember_create"),
    path("family-members/<int:pk>/", views.familymember_detail, name="familymember_detail"),
    path("family-members/<int:pk>/edit/", views.familymember_edit, name="familymember_edit"),
    path("family-members/<int:pk>/delete/", views.familymember_delete, name="familymember_delete"),
]
