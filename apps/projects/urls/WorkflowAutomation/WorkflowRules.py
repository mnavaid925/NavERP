"""Projects 7.17 — ProjectWorkflowRule URL patterns."""
from django.urls import path

from apps.projects.views.WorkflowAutomation import WorkflowRules as views

urlpatterns = [
    path("rules/", views.pwf_list, name="pwf_list"),
    path("rules/create/", views.pwf_create, name="pwf_create"),
    path("rules/<int:pk>/", views.pwf_detail, name="pwf_detail"),
    path("rules/<int:pk>/edit/", views.pwf_edit, name="pwf_edit"),
    path("rules/<int:pk>/delete/", views.pwf_delete, name="pwf_delete"),
    path("rules/<int:pk>/toggle/", views.pwf_toggle_active, name="pwf_toggle_active"),
    path("rules/<int:pk>/test-run/", views.pwf_test_run, name="pwf_test_run"),
    path("rules/<int:pk>/execute/", views.pwf_execute_now, name="pwf_execute_now"),
]
