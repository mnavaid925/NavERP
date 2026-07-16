"""HRM 3.3 Employee Onboarding — Task URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Onboarding Tasks (3.3) — CRUD + workflow actions
    path("onboarding-tasks/", views.onboardingtask_list, name="onboardingtask_list"),
    path("onboarding-tasks/add/", views.onboardingtask_create, name="onboardingtask_create"),
    path("onboarding-tasks/<int:pk>/", views.onboardingtask_detail, name="onboardingtask_detail"),
    path("onboarding-tasks/<int:pk>/edit/", views.onboardingtask_edit, name="onboardingtask_edit"),
    path("onboarding-tasks/<int:pk>/delete/", views.onboardingtask_delete, name="onboardingtask_delete"),
    path("onboarding-tasks/<int:pk>/complete/", views.onboardingtask_complete, name="onboardingtask_complete"),
    path("onboarding-tasks/<int:pk>/reopen/", views.onboardingtask_reopen, name="onboardingtask_reopen"),
    path("onboarding-tasks/<int:pk>/skip/", views.onboardingtask_skip, name="onboardingtask_skip"),
]
