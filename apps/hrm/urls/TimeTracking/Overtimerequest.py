"""HRM 3.11 Time Tracking — Overtimerequest URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Overtime Requests (3.11) — CRUD + workflow
    path("overtime-requests/", views.overtimerequest_list, name="overtimerequest_list"),
    path("overtime-requests/add/", views.overtimerequest_create, name="overtimerequest_create"),
    path("overtime-requests/<int:pk>/", views.overtimerequest_detail, name="overtimerequest_detail"),
    path("overtime-requests/<int:pk>/edit/", views.overtimerequest_edit, name="overtimerequest_edit"),
    path("overtime-requests/<int:pk>/delete/", views.overtimerequest_delete, name="overtimerequest_delete"),
    path("overtime-requests/<int:pk>/submit/", views.overtimerequest_submit, name="overtimerequest_submit"),
    path("overtime-requests/<int:pk>/approve/", views.overtimerequest_approve, name="overtimerequest_approve"),
    path("overtime-requests/<int:pk>/reject/", views.overtimerequest_reject, name="overtimerequest_reject"),
    path("overtime-requests/<int:pk>/cancel/", views.overtimerequest_cancel, name="overtimerequest_cancel"),
]
