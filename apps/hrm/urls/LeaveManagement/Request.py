"""HRM 3.10 Leave Management — Request URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Leave Requests (3.10) — CRUD + workflow actions
    path("leave-requests/", views.leaverequest_list, name="leaverequest_list"),
    path("leave-requests/add/", views.leaverequest_create, name="leaverequest_create"),
    path("leave-requests/<int:pk>/", views.leaverequest_detail, name="leaverequest_detail"),
    path("leave-requests/<int:pk>/edit/", views.leaverequest_edit, name="leaverequest_edit"),
    path("leave-requests/<int:pk>/delete/", views.leaverequest_delete, name="leaverequest_delete"),
    path("leave-requests/<int:pk>/submit/", views.leaverequest_submit, name="leaverequest_submit"),
    path("leave-requests/<int:pk>/approve/", views.leaverequest_approve, name="leaverequest_approve"),
    path("leave-requests/<int:pk>/reject/", views.leaverequest_reject, name="leaverequest_reject"),
    path("leave-requests/<int:pk>/cancel/", views.leaverequest_cancel, name="leaverequest_cancel"),
]
