"""CRM 1.11 Customer Success & Retention — OnboardingPlans URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Onboarding plans + steps (1.11)
    path("onboarding/", views.onboardingplan_list, name="onboardingplan_list"),
    path("onboarding/add/", views.onboardingplan_create, name="onboardingplan_create"),
    path("onboarding/<int:pk>/", views.onboardingplan_detail, name="onboardingplan_detail"),
    path("onboarding/<int:pk>/edit/", views.onboardingplan_edit, name="onboardingplan_edit"),
    path("onboarding/<int:pk>/delete/", views.onboardingplan_delete, name="onboardingplan_delete"),
    path("onboarding/<int:pk>/add-step/", views.onboardingstep_add, name="onboardingstep_add"),
    path("onboarding/steps/<int:step_pk>/complete/", views.onboardingstep_complete, name="onboardingstep_complete"),
    path("onboarding/steps/<int:step_pk>/edit/", views.onboardingstep_edit, name="onboardingstep_edit"),
    path("onboarding/steps/<int:step_pk>/delete/", views.onboardingstep_delete, name="onboardingstep_delete"),
]
