"""HRM 3.3 Employee Onboarding — Document URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Onboarding Documents (3.3) — CRUD + mark-signed
    path("onboarding-documents/", views.onboardingdocument_list, name="onboardingdocument_list"),
    path("onboarding-documents/add/", views.onboardingdocument_create, name="onboardingdocument_create"),
    path("onboarding-documents/<int:pk>/", views.onboardingdocument_detail, name="onboardingdocument_detail"),
    path("onboarding-documents/<int:pk>/edit/", views.onboardingdocument_edit, name="onboardingdocument_edit"),
    path("onboarding-documents/<int:pk>/delete/", views.onboardingdocument_delete, name="onboardingdocument_delete"),
    path("onboarding-documents/<int:pk>/mark-signed/", views.onboardingdocument_mark_signed, name="onboardingdocument_mark_signed"),
]
