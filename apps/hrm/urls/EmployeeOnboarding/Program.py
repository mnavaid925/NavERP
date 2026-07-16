"""HRM 3.3 Employee Onboarding — Program URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Onboarding Programs (3.3) — CRUD + workflow actions
    path("onboarding/", views.onboardingprogram_list, name="onboardingprogram_list"),
    path("onboarding/add/", views.onboardingprogram_create, name="onboardingprogram_create"),
    path("onboarding/<int:pk>/", views.onboardingprogram_detail, name="onboardingprogram_detail"),
    path("onboarding/<int:pk>/edit/", views.onboardingprogram_edit, name="onboardingprogram_edit"),
    path("onboarding/<int:pk>/delete/", views.onboardingprogram_delete, name="onboardingprogram_delete"),
    path("onboarding/<int:pk>/activate/", views.onboardingprogram_activate, name="onboardingprogram_activate"),
    path("onboarding/<int:pk>/generate-tasks/", views.onboardingprogram_generate_tasks, name="onboardingprogram_generate_tasks"),
    path("onboarding/<int:pk>/complete/", views.onboardingprogram_complete, name="onboardingprogram_complete"),
    path("onboarding/<int:pk>/cancel/", views.onboardingprogram_cancel, name="onboardingprogram_cancel"),
]
