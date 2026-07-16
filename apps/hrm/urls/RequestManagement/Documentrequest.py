"""HRM 3.26 Request Management — Documentrequest URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Document Requests (experience letter / salary certificate / ...)
    path("document-requests/", views.documentrequest_list, name="documentrequest_list"),
    path("document-requests/add/", views.documentrequest_create, name="documentrequest_create"),
    path("document-requests/<int:pk>/", views.documentrequest_detail, name="documentrequest_detail"),
    path("document-requests/<int:pk>/edit/", views.documentrequest_edit, name="documentrequest_edit"),
    path("document-requests/<int:pk>/delete/", views.documentrequest_delete, name="documentrequest_delete"),
    path("document-requests/<int:pk>/submit/", views.documentrequest_submit, name="documentrequest_submit"),
    path("document-requests/<int:pk>/cancel/", views.documentrequest_cancel, name="documentrequest_cancel"),
    path("document-requests/<int:pk>/approve/", views.documentrequest_approve, name="documentrequest_approve"),
    path("document-requests/<int:pk>/reject/", views.documentrequest_reject, name="documentrequest_reject"),
    path("document-requests/<int:pk>/fulfill/", views.documentrequest_fulfill, name="documentrequest_fulfill"),
]
