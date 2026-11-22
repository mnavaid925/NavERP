from django.urls import path

from apps.documents.views.ApprovalWorkflow import ApprovalDashboard as views

urlpatterns = [
    path("approvals/dashboard/", views.approval_dashboard, name="approval_dashboard"),
]
