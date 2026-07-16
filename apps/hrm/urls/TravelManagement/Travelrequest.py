"""HRM 3.35 Travel Management — Travelrequest URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("travel-requests/", views.travelrequest_list, name="travelrequest_list"),
    path("travel-requests/add/", views.travelrequest_create, name="travelrequest_create"),
    path("travel-requests/<int:pk>/", views.travelrequest_detail, name="travelrequest_detail"),
    path("travel-requests/<int:pk>/edit/", views.travelrequest_edit, name="travelrequest_edit"),
    path("travel-requests/<int:pk>/delete/", views.travelrequest_delete, name="travelrequest_delete"),
    path("travel-requests/<int:pk>/submit/", views.travelrequest_submit, name="travelrequest_submit"),
    path("travel-requests/<int:pk>/approve/", views.travelrequest_approve, name="travelrequest_approve"),
    path("travel-requests/<int:pk>/reject/", views.travelrequest_reject, name="travelrequest_reject"),
    path("travel-requests/<int:pk>/cancel/", views.travelrequest_cancel, name="travelrequest_cancel"),
    path("travel-requests/<int:pk>/approve-advance/", views.travelrequest_approve_advance, name="travelrequest_approve_advance"),
    path("travel-requests/<int:pk>/mark-advance-paid/", views.travelrequest_mark_advance_paid, name="travelrequest_mark_advance_paid"),
    path("travel-requests/<int:pk>/generate-settlement/", views.travelrequest_generate_settlement, name="travelrequest_generate_settlement"),
    path("travel-requests/<int:pk>/complete/", views.travelrequest_complete, name="travelrequest_complete"),
]
