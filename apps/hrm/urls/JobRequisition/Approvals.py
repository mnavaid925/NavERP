"""HRM 3.5 Job Requisition — Approvals URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Requisition approval steps (3.5) — inline add/remove from the requisition hub
    path("requisitions/<int:jr_pk>/approval/add/", views.approval_add, name="approval_add"),
    path("requisition-approvals/<int:pk>/delete/", views.approval_delete, name="approval_delete"),
]
