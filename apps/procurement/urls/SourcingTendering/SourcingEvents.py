"""Procurement 6.5 Sourcing & Tendering — SourcingEvent urlconf.

Every route carries the ``events/`` first segment: these patterns concatenate into one flat
app-level list where Django is first-match-wins, so an unprefixed ``add/`` here would shadow
every later sub-module's ``add/``.
"""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal segments first — Django is first-match-wins.
    path("events/", views.event_list, name="event_list"),
    path("events/add/", views.event_create, name="event_create"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/<int:pk>/edit/", views.event_edit, name="event_edit"),
    path("events/<int:pk>/delete/", views.event_delete, name="event_delete"),
    path("events/<int:pk>/open/", views.event_open, name="event_open"),
    path("events/<int:pk>/close/", views.event_close, name="event_close"),
    path("events/<int:pk>/cancel/", views.event_cancel, name="event_cancel"),
    path("events/<int:pk>/award/", views.event_award, name="event_award"),
]
