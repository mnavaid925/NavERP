"""HRM 3.8 Offer Management — Offerapprovals URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("offers/<int:pk>/approvals/add/", views.offerapproval_add, name="offerapproval_add"),
    path("offer-approvals/<int:pk>/delete/", views.offerapproval_delete, name="offerapproval_delete"),
]
