"""HRM 3.35 Travel Management — Travelpolicy URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.35 Travel Management
    path("travel-policies/", views.travelpolicy_list, name="travelpolicy_list"),
    path("travel-policies/add/", views.travelpolicy_create, name="travelpolicy_create"),
    path("travel-policies/<int:pk>/", views.travelpolicy_detail, name="travelpolicy_detail"),
    path("travel-policies/<int:pk>/edit/", views.travelpolicy_edit, name="travelpolicy_edit"),
    path("travel-policies/<int:pk>/delete/", views.travelpolicy_delete, name="travelpolicy_delete"),
]
