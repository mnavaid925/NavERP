"""HRM 3.3 Employee Onboarding — Templatetask URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Onboarding Template Tasks (3.3)
    path("onboarding-template-tasks/", views.onboardingtemplatetask_list, name="onboardingtemplatetask_list"),
    path("onboarding-template-tasks/add/", views.onboardingtemplatetask_create, name="onboardingtemplatetask_create"),
    path("onboarding-template-tasks/<int:pk>/", views.onboardingtemplatetask_detail, name="onboardingtemplatetask_detail"),
    path("onboarding-template-tasks/<int:pk>/edit/", views.onboardingtemplatetask_edit, name="onboardingtemplatetask_edit"),
    path("onboarding-template-tasks/<int:pk>/delete/", views.onboardingtemplatetask_delete, name="onboardingtemplatetask_delete"),
]
