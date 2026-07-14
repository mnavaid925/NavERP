"""CRM 1.10 Automation & Workflow Engine — WorkflowRules URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Workflow rules (1.10)
    path("workflows/", views.workflowrule_list, name="workflowrule_list"),
    path("workflows/add/", views.workflowrule_create, name="workflowrule_create"),
    path("workflows/<int:pk>/", views.workflowrule_detail, name="workflowrule_detail"),
    path("workflows/<int:pk>/edit/", views.workflowrule_edit, name="workflowrule_edit"),
    path("workflows/<int:pk>/delete/", views.workflowrule_delete, name="workflowrule_delete"),
    path("workflows/<int:pk>/run/", views.workflowrule_run, name="workflowrule_run"),
]
