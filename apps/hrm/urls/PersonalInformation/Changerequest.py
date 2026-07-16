"""HRM 3.25 Personal Information — Changerequest URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Change Requests (maker-checker workflow)
    path("change-requests/", views.changerequest_list, name="changerequest_list"),
    path("change-requests/add/", views.changerequest_create, name="changerequest_create"),
    path("change-requests/<int:pk>/", views.changerequest_detail, name="changerequest_detail"),
    path("change-requests/<int:pk>/edit/", views.changerequest_edit, name="changerequest_edit"),
    path("change-requests/<int:pk>/delete/", views.changerequest_delete, name="changerequest_delete"),
    path("change-requests/<int:pk>/cancel/", views.changerequest_cancel, name="changerequest_cancel"),
    path("change-requests/<int:pk>/approve/", views.changerequest_approve, name="changerequest_approve"),
    path("change-requests/<int:pk>/reject/", views.changerequest_reject, name="changerequest_reject"),
]
