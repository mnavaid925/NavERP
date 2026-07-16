"""HRM 3.3 Employee Onboarding — Template URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Onboarding Templates (3.3)
    path("onboarding-templates/", views.onboardingtemplate_list, name="onboardingtemplate_list"),
    path("onboarding-templates/add/", views.onboardingtemplate_create, name="onboardingtemplate_create"),
    path("onboarding-templates/<int:pk>/", views.onboardingtemplate_detail, name="onboardingtemplate_detail"),
    path("onboarding-templates/<int:pk>/edit/", views.onboardingtemplate_edit, name="onboardingtemplate_edit"),
    path("onboarding-templates/<int:pk>/delete/", views.onboardingtemplate_delete, name="onboardingtemplate_delete"),
]
