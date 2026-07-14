"""CRM 1.10 Automation & Workflow Engine — WorkflowLogs URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Workflow logs (1.10, read-only)
    path("workflow-logs/", views.workflowlog_list, name="workflowlog_list"),
    path("workflow-logs/<int:pk>/", views.workflowlog_detail, name="workflowlog_detail"),
]
