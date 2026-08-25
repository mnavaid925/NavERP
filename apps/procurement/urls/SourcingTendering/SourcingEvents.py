"""Procurement 6.5 Sourcing & Tendering — SourcingEvent urlconf."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal segments first — Django is first-match-wins.
    path("", views.event_list, name="event_list"),
    path("add/", views.event_create, name="event_create"),
    path("<int:pk>/", views.event_detail, name="event_detail"),
    path("<int:pk>/edit/", views.event_edit, name="event_edit"),
    path("<int:pk>/delete/", views.event_delete, name="event_delete"),
    path("<int:pk>/open/", views.event_open, name="event_open"),
    path("<int:pk>/close/", views.event_close, name="event_close"),
    path("<int:pk>/cancel/", views.event_cancel, name="event_cancel"),
    path("<int:pk>/award/", views.event_award, name="event_award"),
]
