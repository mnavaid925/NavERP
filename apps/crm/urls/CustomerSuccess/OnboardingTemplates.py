"""CRM 1.11 Customer Success & Retention — OnboardingTemplates URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Onboarding templates (1.11 — reusable blueprints)
    path("onboarding-templates/", views.onboardingtemplate_list, name="onboardingtemplate_list"),
    path("onboarding-templates/add/", views.onboardingtemplate_create, name="onboardingtemplate_create"),
    path("onboarding-templates/<int:pk>/", views.onboardingtemplate_detail, name="onboardingtemplate_detail"),
    path("onboarding-templates/<int:pk>/edit/", views.onboardingtemplate_edit, name="onboardingtemplate_edit"),
    path("onboarding-templates/<int:pk>/delete/", views.onboardingtemplate_delete, name="onboardingtemplate_delete"),
    path("onboarding-templates/<int:pk>/apply/", views.onboardingtemplate_apply, name="onboardingtemplate_apply"),
    path("onboarding-templates/<int:pk>/add-step/", views.onboardingtemplatestep_add, name="onboardingtemplatestep_add"),
    path("onboarding-templates/steps/<int:step_pk>/edit/", views.onboardingtemplatestep_edit, name="onboardingtemplatestep_edit"),
    path("onboarding-templates/steps/<int:step_pk>/delete/", views.onboardingtemplatestep_delete, name="onboardingtemplatestep_delete"),
]
