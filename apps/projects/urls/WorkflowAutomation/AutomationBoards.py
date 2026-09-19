from django.urls import path
from apps.projects.views.WorkflowAutomation import AutomationBoards as views

urlpatterns = [
    path("automation/overview/", views.automation_overview, name="automation_overview"),
    path("automation/approvals/", views.approval_inbox, name="approval_inbox"),
    path("automation/recurrence-calendar/", views.recurrence_calendar, name="recurrence_calendar"),
    path("automation/webhook-diagnostics/", views.webhook_diagnostics, name="webhook_diagnostics"),
]
