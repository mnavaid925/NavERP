"""HRM 3.41 Employee Engagement & Wellbeing — Wellbeingprogram URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("engagement/wellbeing/programs/", views.wellbeingprogram_list, name="wellbeingprogram_list"),
    path("engagement/wellbeing/programs/add/", views.wellbeingprogram_create, name="wellbeingprogram_create"),
    path("engagement/wellbeing/programs/<int:pk>/", views.wellbeingprogram_detail, name="wellbeingprogram_detail"),
    path("engagement/wellbeing/programs/<int:pk>/edit/", views.wellbeingprogram_edit, name="wellbeingprogram_edit"),
    path("engagement/wellbeing/programs/<int:pk>/delete/", views.wellbeingprogram_delete, name="wellbeingprogram_delete"),
]
