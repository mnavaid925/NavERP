"""HRM 3.36 Helpdesk — Helpdeskticket URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("helpdesk/tickets/", views.ticket_list, name="ticket_list"),
    path("helpdesk/tickets/add/", views.ticket_create, name="ticket_create"),
    path("helpdesk/tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
    path("helpdesk/tickets/<int:pk>/edit/", views.ticket_edit, name="ticket_edit"),
    path("helpdesk/tickets/<int:pk>/delete/", views.ticket_delete, name="ticket_delete"),
    path("helpdesk/tickets/<int:pk>/assign/", views.ticket_assign, name="ticket_assign"),
    path("helpdesk/tickets/<int:pk>/start/", views.ticket_start, name="ticket_start"),
    path("helpdesk/tickets/<int:pk>/waiting/", views.ticket_waiting, name="ticket_waiting"),
    path("helpdesk/tickets/<int:pk>/resolve/", views.ticket_resolve, name="ticket_resolve"),
    path("helpdesk/tickets/<int:pk>/close/", views.ticket_close, name="ticket_close"),
    path("helpdesk/tickets/<int:pk>/reopen/", views.ticket_reopen, name="ticket_reopen"),
    path("helpdesk/tickets/<int:pk>/cancel/", views.ticket_cancel, name="ticket_cancel"),
    path("helpdesk/tickets/<int:pk>/feedback/", views.ticket_feedback, name="ticket_feedback"),
]
