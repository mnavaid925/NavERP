"""CRM 1.10 Automation & Workflow Engine — Approvals URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Approval requests (1.10)
    path("approvals/", views.approvalrequest_list, name="approvalrequest_list"),
    path("approvals/add/", views.approvalrequest_create, name="approvalrequest_create"),
    path("approvals/<int:pk>/", views.approvalrequest_detail, name="approvalrequest_detail"),
    path("approvals/<int:pk>/edit/", views.approvalrequest_edit, name="approvalrequest_edit"),
    path("approvals/<int:pk>/delete/", views.approvalrequest_delete, name="approvalrequest_delete"),
    path("approvals/<int:pk>/approve/", views.approvalrequest_approve, name="approvalrequest_approve"),
    path("approvals/<int:pk>/reject/", views.approvalrequest_reject, name="approvalrequest_reject"),
]
