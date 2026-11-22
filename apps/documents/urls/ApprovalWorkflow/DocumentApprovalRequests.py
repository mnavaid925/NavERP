from django.urls import path

from apps.documents.views.ApprovalWorkflow import DocumentApprovalRequests as views

urlpatterns = [
    path("requests/", views.approval_request_list, name="approval_request_list"),
    path("requests/create/", views.approval_request_create, name="approval_request_create"),
    path("requests/<int:pk>/", views.approval_request_detail, name="approval_request_detail"),
    path("requests/<int:pk>/edit/", views.approval_request_edit, name="approval_request_edit"),
    path("requests/<int:pk>/delete/", views.approval_request_delete, name="approval_request_delete"),
    path("requests/<int:pk>/decide/", views.approval_request_decide, name="approval_request_decide"),
    path("requests/<int:pk>/delegate/", views.approval_request_delegate, name="approval_request_delegate"),
    path("requests/<int:pk>/escalate/", views.approval_request_escalate, name="approval_request_escalate"),
]
