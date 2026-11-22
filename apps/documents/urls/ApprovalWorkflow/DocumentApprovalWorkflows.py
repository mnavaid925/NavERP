from django.urls import path

from apps.documents.views.ApprovalWorkflow import DocumentApprovalWorkflows as views

urlpatterns = [
    path("workflows/", views.workflow_list, name="workflow_list"),
    path("workflows/create/", views.workflow_create, name="workflow_create"),
    path("workflows/<int:pk>/", views.workflow_detail, name="workflow_detail"),
    path("workflows/<int:pk>/edit/", views.workflow_edit, name="workflow_edit"),
    path("workflows/<int:pk>/delete/", views.workflow_delete, name="workflow_delete"),
    path("workflows/<int:pk>/designer/", views.workflow_designer, name="workflow_designer"),
    path("workflows/<int:pk>/submit/", views.workflow_submit, name="workflow_submit"),
    path("workflows/<int:pk>/bypass/", views.workflow_bypass, name="workflow_bypass"),
    path("workflows/<int:pk>/cancel/", views.workflow_cancel, name="workflow_cancel"),
]
