"""CRM 1.5 Activity & Communication Management — CalendarEvents URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Calendar events (1.5 Calendar Integration — meetings, invite links, ICS)
    path("calendar/", views.calendarevent_list, name="calendarevent_list"),
    path("calendar/add/", views.calendarevent_create, name="calendarevent_create"),
    path("calendar/<int:pk>/", views.calendarevent_detail, name="calendarevent_detail"),
    path("calendar/<int:pk>/edit/", views.calendarevent_edit, name="calendarevent_edit"),
    path("calendar/<int:pk>/delete/", views.calendarevent_delete, name="calendarevent_delete"),
    path("calendar/<int:event_pk>/add-attendee/", views.event_attendee_add, name="event_attendee_add"),
    path("calendar/attendees/<int:pk>/delete/", views.event_attendee_delete, name="event_attendee_delete"),
    path("invite/<str:token>/", views.event_invite, name="event_invite"),     # public RSVP page
    path("invite/<str:token>/ics/", views.event_ics, name="event_ics"),       # public .ics download
]
