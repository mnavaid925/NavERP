"""HRM 3.7 Interview Process — Interview URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Interviews (3.7) — CRUD + hub + status machine + panel + invite/reminder actions
    path("interviews/", views.interview_list, name="interview_list"),
    path("interviews/add/", views.interview_create, name="interview_create"),
    path("interviews/<int:pk>/", views.interview_detail, name="interview_detail"),
    path("interviews/<int:pk>/edit/", views.interview_edit, name="interview_edit"),
    path("interviews/<int:pk>/delete/", views.interview_delete, name="interview_delete"),
    path("interviews/<int:pk>/confirm/", views.interview_confirm, name="interview_confirm"),
    path("interviews/<int:pk>/start/", views.interview_start, name="interview_start"),
    path("interviews/<int:pk>/complete/", views.interview_complete, name="interview_complete"),
    path("interviews/<int:pk>/cancel/", views.interview_cancel, name="interview_cancel"),
    path("interviews/<int:pk>/no-show/", views.interview_no_show, name="interview_no_show"),
    path("interviews/<int:pk>/reschedule/", views.interview_reschedule, name="interview_reschedule"),
    path("interviews/<int:pk>/panelists/add/", views.interview_panelist_add, name="interview_panelist_add"),
    path("interviews/<int:pk>/panelists/<int:panelist_pk>/remove/", views.interview_panelist_remove, name="interview_panelist_remove"),
    path("interviews/<int:pk>/panelists/<int:panelist_pk>/rsvp/", views.interview_panelist_rsvp, name="interview_panelist_rsvp"),
    path("interviews/<int:pk>/send-invite/", views.interview_send_invite, name="interview_send_invite"),
    path("interviews/<int:pk>/send-reminder/", views.interview_send_reminder, name="interview_send_reminder"),
    path("interviews/<int:pk>/request-feedback/", views.interview_request_feedback, name="interview_request_feedback"),
]
